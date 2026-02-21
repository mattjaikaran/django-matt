"""
llama.cpp provider implementation via llama-cpp-python.

Provides direct bindings to llama.cpp for running GGUF models locally
with full control over sampling parameters, GPU acceleration, and
memory management.

Requires: uv add llama-cpp-python

For GPU acceleration:
- macOS: uv add llama-cpp-python (Metal enabled by default on Apple Silicon)
- NVIDIA: CMAKE_ARGS="-DLLAMA_CUDA=on" uv add llama-cpp-python
- AMD: CMAKE_ARGS="-DLLAMA_HIPBLAS=on" uv add llama-cpp-python
"""

from __future__ import annotations

import os
import re
import threading
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

# Import base classes from AI module for compatibility
try:
    from django_matt.ai.base import (
        CompletionResponse,
        EmbeddingProvider,
        EmbeddingResponse,
        LLMProvider,
        Message,
        Role,
        StreamChunk,
        StructuredOutputProvider,
        Usage,
    )
except ImportError:
    # Fallback definitions if AI module not available
    from abc import ABC, abstractmethod
    from dataclasses import dataclass as dc

    class Role(str, Enum):
        SYSTEM = "system"
        USER = "user"
        ASSISTANT = "assistant"
        TOOL = "tool"

    @dc
    class Message:
        role: Role
        content: str

        @classmethod
        def system(cls, content: str) -> Message:
            return cls(role=Role.SYSTEM, content=content)

        @classmethod
        def user(cls, content: str) -> Message:
            return cls(role=Role.USER, content=content)

        @classmethod
        def assistant(cls, content: str) -> Message:
            return cls(role=Role.ASSISTANT, content=content)

    @dc
    class Usage:
        prompt_tokens: int = 0
        completion_tokens: int = 0
        total_tokens: int = 0

    @dc
    class CompletionResponse:
        content: str
        role: Role = Role.ASSISTANT
        model: str = ""
        finish_reason: str | None = None
        usage: Usage | None = None
        raw_response: Any = None

    @dc
    class StreamChunk:
        content: str = ""
        role: Role | None = None
        finish_reason: str | None = None

    @dc
    class EmbeddingResponse:
        embeddings: list[list[float]]
        model: str = ""
        usage: Usage | None = None

    class LLMProvider(ABC):
        @abstractmethod
        async def complete(self, messages: list[Message], **kwargs) -> CompletionResponse:
            pass

        @abstractmethod
        async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[StreamChunk]:
            pass

    class EmbeddingProvider(ABC):
        @abstractmethod
        async def embed(self, texts: list[str], **kwargs) -> EmbeddingResponse:
            pass

    class StructuredOutputProvider(ABC):
        pass


T = TypeVar("T", bound=BaseModel)

# Check for llama-cpp-python availability
LLAMA_CPP_AVAILABLE = False
try:
    from llama_cpp import Llama, LlamaGrammar

    LLAMA_CPP_AVAILABLE = True
except ImportError:
    Llama = None
    LlamaGrammar = None


# =============================================================================
# Enums and Constants
# =============================================================================


class QuantizationLevel(str, Enum):
    """Quantization levels for GGUF models."""

    Q2_K = "Q2_K"
    Q3_K_S = "Q3_K_S"
    Q3_K_M = "Q3_K_M"
    Q3_K_L = "Q3_K_L"
    Q4_0 = "Q4_0"
    Q4_1 = "Q4_1"
    Q4_K_S = "Q4_K_S"
    Q4_K_M = "Q4_K_M"
    Q5_0 = "Q5_0"
    Q5_1 = "Q5_1"
    Q5_K_S = "Q5_K_S"
    Q5_K_M = "Q5_K_M"
    Q6_K = "Q6_K"
    Q8_0 = "Q8_0"
    F16 = "F16"
    F32 = "F32"
    UNKNOWN = "UNKNOWN"


class GPUBackend(str, Enum):
    """Available GPU acceleration backends."""

    NONE = "none"
    METAL = "metal"
    CUDA = "cuda"
    ROCM = "rocm"
    VULKAN = "vulkan"


class ChatTemplate(str, Enum):
    """Built-in chat templates."""

    LLAMA = "llama"
    LLAMA3 = "llama3"
    CHATML = "chatml"
    ALPACA = "alpaca"
    VICUNA = "vicuna"
    MISTRAL = "mistral"
    ZEPHYR = "zephyr"
    PHI = "phi"
    GEMMA = "gemma"
    CUSTOM = "custom"


# =============================================================================
# Chat Templates
# =============================================================================


CHAT_TEMPLATES = {
    ChatTemplate.LLAMA: {
        "system_prefix": "<<SYS>>\n",
        "system_suffix": "\n<</SYS>>\n\n",
        "user_prefix": "[INST] ",
        "user_suffix": " [/INST]",
        "assistant_prefix": "",
        "assistant_suffix": "</s>",
        "bos": "<s>",
        "eos": "</s>",
    },
    ChatTemplate.LLAMA3: {
        "system_prefix": "<|start_header_id|>system<|end_header_id|>\n\n",
        "system_suffix": "<|eot_id|>",
        "user_prefix": "<|start_header_id|>user<|end_header_id|>\n\n",
        "user_suffix": "<|eot_id|>",
        "assistant_prefix": "<|start_header_id|>assistant<|end_header_id|>\n\n",
        "assistant_suffix": "<|eot_id|>",
        "bos": "<|begin_of_text|>",
        "eos": "<|end_of_text|>",
    },
    ChatTemplate.CHATML: {
        "system_prefix": "<|im_start|>system\n",
        "system_suffix": "<|im_end|>\n",
        "user_prefix": "<|im_start|>user\n",
        "user_suffix": "<|im_end|>\n",
        "assistant_prefix": "<|im_start|>assistant\n",
        "assistant_suffix": "<|im_end|>\n",
        "bos": "",
        "eos": "",
    },
    ChatTemplate.ALPACA: {
        "system_prefix": "### System:\n",
        "system_suffix": "\n\n",
        "user_prefix": "### Instruction:\n",
        "user_suffix": "\n\n",
        "assistant_prefix": "### Response:\n",
        "assistant_suffix": "\n\n",
        "bos": "",
        "eos": "",
    },
    ChatTemplate.VICUNA: {
        "system_prefix": "SYSTEM: ",
        "system_suffix": "\n",
        "user_prefix": "USER: ",
        "user_suffix": "\n",
        "assistant_prefix": "ASSISTANT: ",
        "assistant_suffix": "</s>\n",
        "bos": "",
        "eos": "</s>",
    },
    ChatTemplate.MISTRAL: {
        "system_prefix": "",
        "system_suffix": "",
        "user_prefix": "[INST] ",
        "user_suffix": " [/INST]",
        "assistant_prefix": "",
        "assistant_suffix": "</s>",
        "bos": "<s>",
        "eos": "</s>",
    },
    ChatTemplate.ZEPHYR: {
        "system_prefix": "<|system|>\n",
        "system_suffix": "</s>\n",
        "user_prefix": "<|user|>\n",
        "user_suffix": "</s>\n",
        "assistant_prefix": "<|assistant|>\n",
        "assistant_suffix": "</s>\n",
        "bos": "",
        "eos": "</s>",
    },
    ChatTemplate.PHI: {
        "system_prefix": "<|system|>\n",
        "system_suffix": "<|end|>\n",
        "user_prefix": "<|user|>\n",
        "user_suffix": "<|end|>\n",
        "assistant_prefix": "<|assistant|>\n",
        "assistant_suffix": "<|end|>\n",
        "bos": "",
        "eos": "<|endoftext|>",
    },
    ChatTemplate.GEMMA: {
        "system_prefix": "",
        "system_suffix": "",
        "user_prefix": "<start_of_turn>user\n",
        "user_suffix": "<end_of_turn>\n",
        "assistant_prefix": "<start_of_turn>model\n",
        "assistant_suffix": "<end_of_turn>\n",
        "bos": "<bos>",
        "eos": "<eos>",
    },
}


def apply_chat_template(
    messages: list[Message],
    template: ChatTemplate | str = ChatTemplate.CHATML,
    custom_template: dict[str, str] | None = None,
    add_generation_prompt: bool = True,
) -> str:
    """
    Apply a chat template to messages.

    Args:
        messages: List of messages to format
        template: Built-in template name or ChatTemplate enum
        custom_template: Custom template dict (overrides template if provided)
        add_generation_prompt: Whether to add assistant prefix at the end

    Returns:
        Formatted prompt string
    """
    if custom_template:
        tmpl = custom_template
    elif isinstance(template, str):
        template = ChatTemplate(template.lower())
        tmpl = CHAT_TEMPLATES.get(template, CHAT_TEMPLATES[ChatTemplate.CHATML])
    else:
        tmpl = CHAT_TEMPLATES.get(template, CHAT_TEMPLATES[ChatTemplate.CHATML])

    parts = []

    # Add BOS token if specified
    if tmpl.get("bos"):
        parts.append(tmpl["bos"])

    system_content = None

    for msg in messages:
        role = msg.role if isinstance(msg.role, Role) else Role(msg.role)

        if role == Role.SYSTEM:
            system_content = msg.content
        elif role == Role.USER:
            # For some templates, system goes with first user message
            if system_content and template in (ChatTemplate.LLAMA, ChatTemplate.MISTRAL):
                parts.append(tmpl["user_prefix"])
                parts.append(tmpl["system_prefix"] + system_content + tmpl["system_suffix"])
                parts.append(msg.content)
                parts.append(tmpl["user_suffix"])
                system_content = None
            else:
                if system_content:
                    parts.append(tmpl["system_prefix"] + system_content + tmpl["system_suffix"])
                    system_content = None
                parts.append(tmpl["user_prefix"] + msg.content + tmpl["user_suffix"])
        elif role == Role.ASSISTANT:
            parts.append(tmpl["assistant_prefix"] + msg.content + tmpl["assistant_suffix"])

    # Handle remaining system message for templates that didn't use it
    if system_content:
        parts.insert(
            1 if tmpl.get("bos") else 0,
            tmpl["system_prefix"] + system_content + tmpl["system_suffix"],
        )

    # Add generation prompt
    if add_generation_prompt:
        parts.append(tmpl["assistant_prefix"])

    return "".join(parts)


# =============================================================================
# GBNF Grammar Support
# =============================================================================


# Common GBNF grammar patterns
GBNF_GRAMMARS = {
    "json": r"""
root ::= object
value ::= object | array | string | number | ("true" | "false" | "null") ws

object ::=
  "{" ws (
            string ":" ws value
    ("," ws string ":" ws value)*
  )? "}" ws

array ::=
  "[" ws (
            value
    ("," ws value)*
  )? "]" ws

string ::=
  "\"" (
    [^"\\] |
    "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])
  )* "\"" ws

number ::= ("-"? ([0-9] | [1-9] [0-9]*)) ("." [0-9]+)? ([eE] [-+]? [0-9]+)? ws

ws ::= ([ \t\n] ws)?
""",
    "json_object": r"""
root ::= "{" ws members "}" ws
members ::= pair ("," ws pair)*
pair ::= string ":" ws value
value ::= string | number | "true" | "false" | "null" | object | array
object ::= "{" ws (members)? "}" ws
array ::= "[" ws (value ("," ws value)*)? "]" ws
string ::= "\"" ([^"\\] | "\\" .)* "\""
number ::= "-"? [0-9]+ ("." [0-9]+)?
ws ::= [ \t\n]*
""",
    "list": r"""
root ::= "[" ws (item ("," ws item)*)? "]" ws
item ::= string
string ::= "\"" [a-zA-Z0-9 ]* "\""
ws ::= [ \t\n]*
""",
    "yes_no": r"""
root ::= ("yes" | "no")
""",
    "integer": r"""
root ::= "-"? [0-9]+
""",
    "float": r"""
root ::= "-"? [0-9]+ ("." [0-9]+)?
""",
}


def create_grammar(grammar_str: str) -> LlamaGrammar | None:
    """
    Create a LlamaGrammar from a GBNF grammar string.

    Args:
        grammar_str: GBNF grammar string or name of built-in grammar

    Returns:
        LlamaGrammar instance or None if llama-cpp-python not available
    """
    if not LLAMA_CPP_AVAILABLE:
        return None

    # Check if it's a built-in grammar name
    if grammar_str in GBNF_GRAMMARS:
        grammar_str = GBNF_GRAMMARS[grammar_str]

    return LlamaGrammar.from_string(grammar_str)


def pydantic_to_gbnf(model: type[BaseModel]) -> str:
    """
    Convert a Pydantic model to GBNF grammar.

    Args:
        model: Pydantic model class

    Returns:
        GBNF grammar string that enforces the model's schema
    """
    schema = model.model_json_schema()
    return _json_schema_to_gbnf(schema)


def _json_schema_to_gbnf(schema: dict[str, Any], root_name: str = "root") -> str:
    """Convert JSON Schema to GBNF grammar."""
    rules = []
    rules.append("ws ::= ([ \\t\\n] ws)?")
    rules.append('string ::= "\\"" ([^"\\\\] | "\\\\" .)* "\\""')
    rules.append('number ::= "-"? [0-9]+ ("." [0-9]+)?')
    rules.append('integer ::= "-"? [0-9]+')
    rules.append('boolean ::= ("true" | "false")')
    rules.append('null ::= "null"')

    def process_schema(s: dict, name: str) -> str:
        schema_type = s.get("type", "string")

        if schema_type == "object":
            props = s.get("properties", {})
            required = set(s.get("required", []))

            if not props:
                return f'{name} ::= "{{" ws "}}"'

            parts = []
            for i, (prop_name, prop_schema) in enumerate(props.items()):
                prop_rule_name = f"{name}_{prop_name}"
                rules.append(process_schema(prop_schema, prop_rule_name))

                prop_str = f'"\\"" "{prop_name}" "\\"" ws ":" ws {prop_rule_name}'
                if prop_name not in required:
                    prop_str = f"({prop_str})?"

                if i > 0:
                    parts.append(f'"," ws {prop_str}')
                else:
                    parts.append(prop_str)

            return f'{name} ::= "{{" ws {" ".join(parts)} "}}" ws'

        if schema_type == "array":
            items = s.get("items", {"type": "string"})
            item_rule = f"{name}_item"
            rules.append(process_schema(items, item_rule))
            return f'{name} ::= "[" ws ({item_rule} ("," ws {item_rule})*)? "]" ws'

        if schema_type == "string":
            if "enum" in s:
                enum_vals = " | ".join(f'"\\""{v}"\\""' for v in s["enum"])
                return f"{name} ::= ({enum_vals})"
            return f"{name} ::= string ws"

        if schema_type == "integer":
            return f"{name} ::= integer ws"

        if schema_type == "number":
            return f"{name} ::= number ws"

        if schema_type == "boolean":
            return f"{name} ::= boolean ws"

        if schema_type == "null":
            return f"{name} ::= null ws"

        # Default to string
        return f"{name} ::= string ws"

    main_rule = process_schema(schema, root_name)
    rules.insert(0, main_rule)

    return "\n".join(rules)


# =============================================================================
# Model Configuration
# =============================================================================


@dataclass
class LlamaCppModelConfig:
    """Configuration for loading a llama.cpp model."""

    # Model path
    model_path: str

    # Context and generation
    n_ctx: int = 4096  # Context window size
    n_batch: int = 512  # Batch size for prompt processing
    n_threads: int | None = None  # CPU threads (None = auto)
    n_threads_batch: int | None = None  # Threads for batch processing

    # GPU acceleration
    n_gpu_layers: int = -1  # Layers to offload to GPU (-1 = all)
    main_gpu: int = 0  # Main GPU for multi-GPU
    tensor_split: list[float] | None = None  # GPU split ratios

    # Memory
    use_mmap: bool = True  # Memory-mapped model loading
    use_mlock: bool = False  # Lock model in RAM
    rope_scaling_type: int = -1  # RoPE scaling type
    rope_freq_base: float = 0.0  # RoPE frequency base
    rope_freq_scale: float = 0.0  # RoPE frequency scale

    # Chat
    chat_format: str | None = None  # Chat format (auto-detected if None)
    chat_template: ChatTemplate | str = ChatTemplate.CHATML

    # Embedding mode
    embedding: bool = False  # Enable embedding mode

    # Verbosity
    verbose: bool = False

    def to_llama_kwargs(self) -> dict[str, Any]:
        """Convert to kwargs for Llama constructor."""
        kwargs = {
            "model_path": self.model_path,
            "n_ctx": self.n_ctx,
            "n_batch": self.n_batch,
            "n_gpu_layers": self.n_gpu_layers,
            "main_gpu": self.main_gpu,
            "use_mmap": self.use_mmap,
            "use_mlock": self.use_mlock,
            "embedding": self.embedding,
            "verbose": self.verbose,
        }

        if self.n_threads is not None:
            kwargs["n_threads"] = self.n_threads
        if self.n_threads_batch is not None:
            kwargs["n_threads_batch"] = self.n_threads_batch
        if self.tensor_split is not None:
            kwargs["tensor_split"] = self.tensor_split
        if self.rope_freq_base > 0:
            kwargs["rope_freq_base"] = self.rope_freq_base
        if self.rope_freq_scale > 0:
            kwargs["rope_freq_scale"] = self.rope_freq_scale
        if self.chat_format:
            kwargs["chat_format"] = self.chat_format

        return kwargs


@dataclass
class SamplingParams:
    """Sampling parameters for text generation."""

    # Basic sampling
    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 40
    min_p: float = 0.05

    # Generation limits
    max_tokens: int = 512
    stop: list[str] = field(default_factory=list)

    # Repetition control
    repeat_penalty: float = 1.1
    repeat_last_n: int = 64
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

    # Mirostat sampling
    mirostat_mode: int = 0  # 0=disabled, 1=mirostat, 2=mirostat 2.0
    mirostat_tau: float = 5.0
    mirostat_eta: float = 0.1

    # Other
    seed: int = -1  # -1 for random
    grammar: str | None = None  # GBNF grammar or grammar name

    def to_llama_kwargs(self) -> dict[str, Any]:
        """Convert to kwargs for Llama generation methods."""
        kwargs = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "min_p": self.min_p,
            "max_tokens": self.max_tokens,
            "repeat_penalty": self.repeat_penalty,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
        }

        if self.stop:
            kwargs["stop"] = self.stop

        if self.mirostat_mode > 0:
            kwargs["mirostat_mode"] = self.mirostat_mode
            kwargs["mirostat_tau"] = self.mirostat_tau
            kwargs["mirostat_eta"] = self.mirostat_eta

        if self.seed >= 0:
            kwargs["seed"] = self.seed

        return kwargs


# =============================================================================
# LlamaCppModel - Model Instance Manager
# =============================================================================


class LlamaCppModel:
    """
    Manages a loaded llama.cpp model instance.

    Provides model information, memory estimation, and lifecycle management.

    Usage:
        from django_matt.ml import LlamaCppModel

        model = LlamaCppModel.from_file("path/to/model.gguf")

        # Model info
        print(f"Context window: {model.context_length}")
        print(f"Quantization: {model.quantization}")
        print(f"Estimated VRAM: {model.estimate_vram_mb()} MB")

        # Generate
        output = model.generate("Hello, how are you?")
        print(output)

        # Cleanup
        model.unload()
    """

    def __init__(
        self,
        llama: Llama,
        config: LlamaCppModelConfig,
        model_path: str,
    ):
        self._llama = llama
        self._config = config
        self._model_path = model_path
        self._lock = threading.Lock()

    @classmethod
    def from_file(
        cls,
        model_path: str,
        *,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        n_batch: int = 512,
        n_threads: int | None = None,
        use_mmap: bool = True,
        verbose: bool = False,
        **kwargs,
    ) -> LlamaCppModel:
        """
        Load a model from a GGUF file.

        Args:
            model_path: Path to the GGUF model file
            n_ctx: Context window size
            n_gpu_layers: Number of layers to offload to GPU (-1 = all)
            n_batch: Batch size for prompt processing
            n_threads: Number of CPU threads (None = auto)
            use_mmap: Use memory-mapped file loading
            verbose: Enable verbose logging
            **kwargs: Additional Llama constructor arguments

        Returns:
            LlamaCppModel instance
        """
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError(
                "llama-cpp-python is required. Install with: uv add llama-cpp-python\n"
                "For GPU support:\n"
                "  macOS: uv add llama-cpp-python (Metal auto-enabled)\n"
                "  NVIDIA: CMAKE_ARGS='-DLLAMA_CUDA=on' uv add llama-cpp-python\n"
                "  AMD: CMAKE_ARGS='-DLLAMA_HIPBLAS=on' uv add llama-cpp-python"
            )

        config = LlamaCppModelConfig(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            n_threads=n_threads,
            use_mmap=use_mmap,
            verbose=verbose,
        )

        llama_kwargs = config.to_llama_kwargs()
        llama_kwargs.update(kwargs)

        llama = Llama(**llama_kwargs)

        return cls(llama, config, model_path)

    @classmethod
    def from_huggingface(
        cls,
        repo_id: str,
        filename: str,
        *,
        cache_dir: str | None = None,
        **kwargs,
    ) -> LlamaCppModel:
        """
        Load a model from Hugging Face Hub.

        Args:
            repo_id: Repository ID (e.g., "TheBloke/Llama-2-7B-GGUF")
            filename: Model filename (e.g., "llama-2-7b.Q4_K_M.gguf")
            cache_dir: Cache directory for downloaded files
            **kwargs: Additional arguments for from_file()

        Returns:
            LlamaCppModel instance
        """
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError("llama-cpp-python is required.")

        try:
            from huggingface_hub import hf_hub_download
        except ImportError:
            raise ImportError(
                "huggingface_hub is required for downloading models. "
                "Install with: uv add huggingface_hub"
            )

        model_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            cache_dir=cache_dir,
        )

        return cls.from_file(model_path, **kwargs)

    @property
    def llama(self) -> Llama:
        """Get the underlying Llama instance."""
        return self._llama

    @property
    def config(self) -> LlamaCppModelConfig:
        """Get the model configuration."""
        return self._config

    @property
    def model_path(self) -> str:
        """Get the model file path."""
        return self._model_path

    @property
    def context_length(self) -> int:
        """Get the context window size."""
        return self._config.n_ctx

    @property
    def vocab_size(self) -> int:
        """Get the vocabulary size."""
        return self._llama.n_vocab()

    @property
    def model_size(self) -> int:
        """Get the model file size in bytes."""
        return Path(self._model_path).stat().st_size

    @property
    def quantization(self) -> QuantizationLevel:
        """Detect quantization level from filename."""
        return detect_quantization(self._model_path)

    def estimate_vram_mb(self, context_length: int | None = None) -> float:
        """
        Estimate VRAM usage in MB.

        Args:
            context_length: Context length to estimate for (uses model's n_ctx if None)

        Returns:
            Estimated VRAM usage in megabytes
        """
        ctx = context_length or self._config.n_ctx
        return estimate_memory_usage(
            self._model_path,
            context_length=ctx,
            n_gpu_layers=self._config.n_gpu_layers,
        )

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        top_k: int = 40,
        repeat_penalty: float = 1.1,
        stop: list[str] | None = None,
        grammar: str | None = None,
        seed: int = -1,
        **kwargs,
    ) -> str:
        """
        Generate text from a prompt.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling
            repeat_penalty: Repetition penalty
            stop: Stop sequences
            grammar: GBNF grammar string or built-in grammar name
            seed: Random seed (-1 for random)
            **kwargs: Additional generation parameters

        Returns:
            Generated text
        """
        with self._lock:
            llama_grammar = None
            if grammar:
                llama_grammar = create_grammar(grammar)

            output = self._llama(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repeat_penalty=repeat_penalty,
                stop=stop or [],
                grammar=llama_grammar,
                seed=seed if seed >= 0 else None,
                **kwargs,
            )

            return output["choices"][0]["text"]

    def generate_stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs,
    ) -> Iterator[str]:
        """
        Stream generated text token by token.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional generation parameters

        Yields:
            Generated tokens
        """
        with self._lock:
            for output in self._llama(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                **kwargs,
            ):
                token = output["choices"][0]["text"]
                if token:
                    yield token

    def chat(
        self,
        messages: list[dict[str, str]] | list[Message],
        *,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """
        Generate a chat completion.

        Args:
            messages: List of messages (dicts with 'role' and 'content')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional generation parameters

        Returns:
            Assistant's response
        """
        # Convert Message objects to dicts
        msg_list = []
        for msg in messages:
            if isinstance(msg, Message):
                role = msg.role.value if isinstance(msg.role, Role) else msg.role
                msg_list.append({"role": role, "content": msg.content})
            else:
                msg_list.append(msg)

        with self._lock:
            output = self._llama.create_chat_completion(
                messages=msg_list,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

            return output["choices"][0]["message"]["content"]

    def embed(self, text: str | list[str]) -> list[list[float]]:
        """
        Generate embeddings for text.

        Args:
            text: Single text or list of texts

        Returns:
            List of embedding vectors
        """
        if not self._config.embedding:
            raise ValueError("Model not loaded in embedding mode. Reload with embedding=True")

        texts = [text] if isinstance(text, str) else text

        with self._lock:
            embeddings = []
            for t in texts:
                emb = self._llama.embed(t)
                embeddings.append(emb)
            return embeddings

    def tokenize(self, text: str, add_bos: bool = True) -> list[int]:
        """Tokenize text to token IDs."""
        return self._llama.tokenize(text.encode("utf-8"), add_bos=add_bos)

    def detokenize(self, tokens: list[int]) -> str:
        """Convert token IDs back to text."""
        return self._llama.detokenize(tokens).decode("utf-8")

    def reset(self) -> None:
        """Reset the model's KV cache."""
        self._llama.reset()

    def unload(self) -> None:
        """Unload the model and free resources."""
        if self._llama is not None:
            del self._llama
            self._llama = None

    def __del__(self):
        self.unload()


# =============================================================================
# LlamaCppProvider - LLM Provider Implementation
# =============================================================================


class LlamaCppProvider(LLMProvider, StructuredOutputProvider):
    """
    llama.cpp LLM provider for running GGUF models locally.

    Provides direct access to llama.cpp via llama-cpp-python bindings
    with full control over sampling parameters and GPU acceleration.

    Usage:
        from django_matt.ml import LlamaCppProvider, Message

        # Load a model
        llm = LlamaCppProvider(
            model_path="/path/to/model.gguf",
            n_ctx=4096,
            n_gpu_layers=-1,  # Use all GPU layers
        )

        # Simple completion
        response = await llm.complete([
            Message.system("You are helpful."),
            Message.user("What is Python?"),
        ])
        print(response.content)

        # Streaming
        async for chunk in llm.stream([Message.user("Tell a story")]):
            print(chunk.content, end="", flush=True)

        # Text generation (raw prompt)
        text = await llm.generate("Once upon a time")

        # Grammar-constrained output
        response = await llm.complete(
            [Message.user("List 3 colors")],
            grammar="json",  # Force JSON output
        )

        # Structured output
        from pydantic import BaseModel

        class Colors(BaseModel):
            colors: list[str]

        colors = await llm.complete_structured(
            [Message.user("List 3 colors")],
            response_model=Colors,
        )
    """

    def __init__(
        self,
        model_path: str | None = None,
        *,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        n_batch: int = 512,
        n_threads: int | None = None,
        use_mmap: bool = True,
        chat_template: ChatTemplate | str = ChatTemplate.CHATML,
        verbose: bool = False,
        model: LlamaCppModel | None = None,
        **kwargs,
    ):
        """
        Initialize the llama.cpp provider.

        Args:
            model_path: Path to GGUF model file (or set LLAMA_MODEL_PATH env var)
            n_ctx: Context window size
            n_gpu_layers: Layers to offload to GPU (-1 = all, 0 = CPU only)
            n_batch: Batch size for prompt processing
            n_threads: CPU threads (None = auto)
            use_mmap: Use memory-mapped loading
            chat_template: Chat template to use
            verbose: Enable verbose logging
            model: Pre-loaded LlamaCppModel instance
            **kwargs: Additional Llama constructor arguments
        """
        super().__init__(
            api_key=None,
            model=model_path,
            timeout=600.0,  # Local models can be slow
            **kwargs,
        )

        self._model_path = model_path or os.environ.get("LLAMA_MODEL_PATH")
        self._n_ctx = n_ctx
        self._n_gpu_layers = n_gpu_layers
        self._n_batch = n_batch
        self._n_threads = n_threads
        self._use_mmap = use_mmap
        self._chat_template = chat_template
        self._verbose = verbose
        self._extra_kwargs = kwargs

        self._model: LlamaCppModel | None = model
        self._lock = threading.Lock()

    @property
    def default_model(self) -> str:
        return self._model_path or "local-llama"

    @property
    def provider_name(self) -> str:
        return "llamacpp"

    def _ensure_model(self) -> LlamaCppModel:
        """Ensure the model is loaded."""
        if self._model is None:
            if not self._model_path:
                raise ValueError(
                    "No model path specified. Set model_path in constructor "
                    "or LLAMA_MODEL_PATH environment variable."
                )

            self._model = LlamaCppModel.from_file(
                self._model_path,
                n_ctx=self._n_ctx,
                n_gpu_layers=self._n_gpu_layers,
                n_batch=self._n_batch,
                n_threads=self._n_threads,
                use_mmap=self._use_mmap,
                verbose=self._verbose,
                **self._extra_kwargs,
            )

        return self._model

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        tools: list | None = None,
        tool_choice: str | None = None,
        top_p: float = 0.95,
        top_k: int = 40,
        min_p: float = 0.05,
        repeat_penalty: float = 1.1,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        mirostat_mode: int = 0,
        mirostat_tau: float = 5.0,
        mirostat_eta: float = 0.1,
        grammar: str | None = None,
        seed: int = -1,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate a chat completion.

        Args:
            messages: Conversation messages
            model: Ignored (uses loaded model)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            tools: Not supported for llama.cpp
            tool_choice: Not supported for llama.cpp
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling
            min_p: Minimum probability threshold
            repeat_penalty: Repetition penalty
            frequency_penalty: Frequency-based penalty
            presence_penalty: Presence-based penalty
            mirostat_mode: Mirostat sampling (0=off, 1=v1, 2=v2)
            mirostat_tau: Mirostat target entropy
            mirostat_eta: Mirostat learning rate
            grammar: GBNF grammar for constrained output
            seed: Random seed (-1 for random)
            **kwargs: Additional generation parameters

        Returns:
            CompletionResponse with generated content
        """
        import asyncio

        llm_model = self._ensure_model()

        # Convert messages to chat format
        msg_list = []
        for msg in messages:
            role = msg.role.value if isinstance(msg.role, Role) else msg.role
            msg_list.append({"role": role, "content": msg.content})

        # Build kwargs
        gen_kwargs = {
            "max_tokens": max_tokens or 512,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "min_p": min_p,
            "repeat_penalty": repeat_penalty,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
        }

        if stop:
            gen_kwargs["stop"] = stop

        if mirostat_mode > 0:
            gen_kwargs["mirostat_mode"] = mirostat_mode
            gen_kwargs["mirostat_tau"] = mirostat_tau
            gen_kwargs["mirostat_eta"] = mirostat_eta

        if seed >= 0:
            gen_kwargs["seed"] = seed

        if grammar:
            llama_grammar = create_grammar(grammar)
            if llama_grammar:
                gen_kwargs["grammar"] = llama_grammar

        gen_kwargs.update(kwargs)

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(
            None,
            lambda: llm_model.llama.create_chat_completion(
                messages=msg_list,
                **gen_kwargs,
            ),
        )

        choice = output["choices"][0]
        content = choice["message"]["content"]

        usage = None
        if "usage" in output:
            usage = Usage(
                prompt_tokens=output["usage"].get("prompt_tokens", 0),
                completion_tokens=output["usage"].get("completion_tokens", 0),
                total_tokens=output["usage"].get("total_tokens", 0),
            )

        return CompletionResponse(
            content=content,
            role=Role.ASSISTANT,
            model=self._model_path or "local-llama",
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            raw_response=output,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a chat completion.

        Args:
            messages: Conversation messages
            model: Ignored (uses loaded model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            **kwargs: Additional generation parameters

        Yields:
            StreamChunk with generated tokens
        """
        import asyncio

        llm_model = self._ensure_model()

        msg_list = []
        for msg in messages:
            role = msg.role.value if isinstance(msg.role, Role) else msg.role
            msg_list.append({"role": role, "content": msg.content})

        gen_kwargs = {
            "max_tokens": max_tokens or 512,
            "temperature": temperature,
            "stream": True,
        }

        if stop:
            gen_kwargs["stop"] = stop

        gen_kwargs.update(kwargs)

        # Run generation in executor
        loop = asyncio.get_event_loop()

        def generate():
            return list(
                llm_model.llama.create_chat_completion(
                    messages=msg_list,
                    **gen_kwargs,
                )
            )

        chunks = await loop.run_in_executor(None, generate)

        for chunk in chunks:
            choice = chunk["choices"][0]
            delta = choice.get("delta", {})
            content = delta.get("content", "")

            if content:
                yield StreamChunk(
                    content=content,
                    finish_reason=choice.get("finish_reason"),
                )

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop: list[str] | None = None,
        grammar: str | None = None,
        seed: int = -1,
        **kwargs,
    ) -> str:
        """
        Generate text from a raw prompt (non-chat).

        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop: Stop sequences
            grammar: GBNF grammar for constrained output
            seed: Random seed
            **kwargs: Additional generation parameters

        Returns:
            Generated text
        """
        import asyncio

        llm_model = self._ensure_model()

        gen_kwargs = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": stop or [],
        }

        if grammar:
            llama_grammar = create_grammar(grammar)
            if llama_grammar:
                gen_kwargs["grammar"] = llama_grammar

        if seed >= 0:
            gen_kwargs["seed"] = seed

        gen_kwargs.update(kwargs)

        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(
            None,
            lambda: llm_model.llama(prompt, **gen_kwargs),
        )

        return output["choices"][0]["text"]

    async def chat(
        self,
        messages: list[Message],
        *,
        template: ChatTemplate | str | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate a chat completion with explicit template control.

        Args:
            messages: Conversation messages
            template: Chat template to use (overrides default)
            **kwargs: Additional generation parameters

        Returns:
            CompletionResponse with generated content
        """
        # Use custom template if specified
        if template:
            import asyncio

            llm_model = self._ensure_model()

            prompt = apply_chat_template(
                messages,
                template=template,
                add_generation_prompt=True,
            )

            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(
                None,
                lambda: llm_model.llama(
                    prompt,
                    max_tokens=kwargs.get("max_tokens", 512),
                    temperature=kwargs.get("temperature", 0.7),
                    stop=kwargs.get("stop", []),
                ),
            )

            content = output["choices"][0]["text"]

            return CompletionResponse(
                content=content,
                role=Role.ASSISTANT,
                model=self._model_path or "local-llama",
                finish_reason=output["choices"][0].get("finish_reason"),
                raw_response=output,
            )

        # Default to standard complete
        return await self.complete(messages, **kwargs)

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_retries: int = 3,
        **kwargs,
    ) -> T:
        """
        Generate a structured response matching a Pydantic model.

        Uses GBNF grammar to constrain output to valid JSON matching the schema.

        Args:
            messages: Conversation messages
            response_model: Pydantic model for response
            model: Ignored
            temperature: Sampling temperature (lower = more deterministic)
            max_retries: Retries on validation failure
            **kwargs: Additional generation parameters

        Returns:
            Instance of response_model
        """
        import orjson

        # Generate GBNF grammar from Pydantic model
        grammar_str = pydantic_to_gbnf(response_model)

        # Add schema description to system prompt
        schema = response_model.model_json_schema()
        schema_str = orjson.dumps(schema, option=orjson.OPT_INDENT_2).decode()

        system_msg = Message.system(
            f"You must respond with valid JSON matching this schema:\n{schema_str}\n"
            "Only output the JSON object, nothing else."
        )

        augmented = [system_msg] + list(messages)

        for attempt in range(max_retries):
            try:
                response = await self.complete(
                    augmented,
                    temperature=temperature,
                    grammar=grammar_str,
                    **kwargs,
                )

                data = orjson.loads(response.content)
                return response_model.model_validate(data)

            except (orjson.JSONDecodeError, Exception) as e:
                if attempt == max_retries - 1:
                    raise ValueError(
                        f"Failed to get valid structured response after {max_retries} attempts: {e}"
                    )

        raise ValueError("Failed to generate structured response")

    def get_model(self) -> LlamaCppModel:
        """Get the underlying LlamaCppModel instance."""
        return self._ensure_model()

    def unload(self) -> None:
        """Unload the model and free resources."""
        if self._model is not None:
            self._model.unload()
            self._model = None

    def __del__(self):
        self.unload()


# =============================================================================
# LlamaCppEmbeddings - Embedding Provider
# =============================================================================


class LlamaCppEmbeddings(EmbeddingProvider):
    """
    llama.cpp embedding provider.

    Uses models in embedding mode to generate vector embeddings.

    Usage:
        from django_matt.ml import LlamaCppEmbeddings

        embedder = LlamaCppEmbeddings(
            model_path="/path/to/embedding-model.gguf"
        )

        # Single text
        vector = await embedder.embed_single("Hello world")

        # Multiple texts
        response = await embedder.embed(["Hello", "World"])
        vectors = response.embeddings
    """

    def __init__(
        self,
        model_path: str | None = None,
        *,
        n_ctx: int = 512,
        n_gpu_layers: int = -1,
        n_batch: int = 512,
        verbose: bool = False,
        **kwargs,
    ):
        """
        Initialize the embedding provider.

        Args:
            model_path: Path to GGUF embedding model
            n_ctx: Context size (can be smaller for embeddings)
            n_gpu_layers: GPU layers to use
            n_batch: Batch size
            verbose: Enable verbose logging
            **kwargs: Additional Llama constructor arguments
        """
        super().__init__(api_key=None, model=model_path, **kwargs)

        self._model_path = model_path or os.environ.get("LLAMA_EMBEDDING_MODEL_PATH")
        self._n_ctx = n_ctx
        self._n_gpu_layers = n_gpu_layers
        self._n_batch = n_batch
        self._verbose = verbose
        self._extra_kwargs = kwargs

        self._llama: Llama | None = None
        self._dimensions: int | None = None
        self._lock = threading.Lock()

    @property
    def default_model(self) -> str:
        return self._model_path or "local-embedding"

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions (requires model to be loaded)."""
        if self._dimensions is None:
            # Load model to get dimensions
            self._ensure_model()
        return self._dimensions or 4096  # Default fallback

    def _ensure_model(self) -> Llama:
        """Ensure the embedding model is loaded."""
        if self._llama is None:
            if not LLAMA_CPP_AVAILABLE:
                raise ImportError(
                    "llama-cpp-python is required. Install with: uv add llama-cpp-python"
                )

            if not self._model_path:
                raise ValueError(
                    "No model path specified. Set model_path in constructor "
                    "or LLAMA_EMBEDDING_MODEL_PATH environment variable."
                )

            self._llama = Llama(
                model_path=self._model_path,
                n_ctx=self._n_ctx,
                n_gpu_layers=self._n_gpu_layers,
                n_batch=self._n_batch,
                embedding=True,  # Enable embedding mode
                verbose=self._verbose,
                **self._extra_kwargs,
            )

            # Get dimensions from first embedding
            test_emb = self._llama.embed("test")
            self._dimensions = len(test_emb)

        return self._llama

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        **kwargs,
    ) -> EmbeddingResponse:
        """
        Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            model: Ignored (uses loaded model)
            **kwargs: Additional parameters

        Returns:
            EmbeddingResponse with embedding vectors
        """
        import asyncio

        llama = self._ensure_model()

        loop = asyncio.get_event_loop()

        def generate_embeddings():
            embeddings = []
            for text in texts:
                with self._lock:
                    emb = llama.embed(text)
                    embeddings.append(emb)
            return embeddings

        embeddings = await loop.run_in_executor(None, generate_embeddings)

        return EmbeddingResponse(
            embeddings=embeddings,
            model=self._model_path or "local-embedding",
            usage=Usage(
                prompt_tokens=sum(len(t.split()) for t in texts),  # Approximate
                total_tokens=sum(len(t.split()) for t in texts),
            ),
        )

    async def embed_batch(
        self,
        texts: list[str],
        *,
        batch_size: int = 32,
        **kwargs,
    ) -> EmbeddingResponse:
        """
        Generate embeddings in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch
            **kwargs: Additional parameters

        Returns:
            EmbeddingResponse with all embeddings
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self.embed(batch, **kwargs)
            all_embeddings.extend(response.embeddings)

        return EmbeddingResponse(
            embeddings=all_embeddings,
            model=self._model_path or "local-embedding",
        )

    def unload(self) -> None:
        """Unload the model and free resources."""
        if self._llama is not None:
            del self._llama
            self._llama = None

    def __del__(self):
        self.unload()


# =============================================================================
# Utilities
# =============================================================================


def detect_quantization(model_path: str) -> QuantizationLevel:
    """
    Detect quantization level from model filename.

    Args:
        model_path: Path to the GGUF model file

    Returns:
        QuantizationLevel enum value
    """
    filename = Path(model_path).name.upper()

    patterns = [
        (r"Q2_K", QuantizationLevel.Q2_K),
        (r"Q3_K_S", QuantizationLevel.Q3_K_S),
        (r"Q3_K_M", QuantizationLevel.Q3_K_M),
        (r"Q3_K_L", QuantizationLevel.Q3_K_L),
        (r"Q4_0", QuantizationLevel.Q4_0),
        (r"Q4_1", QuantizationLevel.Q4_1),
        (r"Q4_K_S", QuantizationLevel.Q4_K_S),
        (r"Q4_K_M", QuantizationLevel.Q4_K_M),
        (r"Q5_0", QuantizationLevel.Q5_0),
        (r"Q5_1", QuantizationLevel.Q5_1),
        (r"Q5_K_S", QuantizationLevel.Q5_K_S),
        (r"Q5_K_M", QuantizationLevel.Q5_K_M),
        (r"Q6_K", QuantizationLevel.Q6_K),
        (r"Q8_0", QuantizationLevel.Q8_0),
        (r"F16", QuantizationLevel.F16),
        (r"F32", QuantizationLevel.F32),
    ]

    for pattern, level in patterns:
        if re.search(pattern, filename):
            return level

    return QuantizationLevel.UNKNOWN


def estimate_memory_usage(
    model_path: str,
    *,
    context_length: int = 4096,
    n_gpu_layers: int = -1,
) -> float:
    """
    Estimate memory usage for a model in MB.

    Args:
        model_path: Path to the GGUF model file
        context_length: Context window size
        n_gpu_layers: Number of GPU layers (-1 = all)

    Returns:
        Estimated memory usage in MB
    """
    # Get file size as base
    file_size_mb = Path(model_path).stat().st_size / (1024 * 1024)

    # KV cache estimation (rough)
    # ~2 bytes per token per layer for FP16 KV cache
    # Assume 32 layers as a rough average
    num_layers = 32
    kv_cache_mb = (context_length * num_layers * 2 * 2) / (1024 * 1024)

    # Working memory overhead (~10-20% of model size)
    overhead_mb = file_size_mb * 0.15

    total = file_size_mb + kv_cache_mb + overhead_mb

    return round(total, 2)


def get_optimal_threads() -> int:
    """
    Get optimal number of threads for the current system.

    Returns:
        Recommended thread count
    """
    import os

    # Use physical cores, not logical (hyperthreaded)
    try:
        # Try to get physical core count
        import subprocess

        if os.uname().sysname == "Darwin":  # macOS
            result = subprocess.run(
                ["sysctl", "-n", "hw.physicalcpu"],
                capture_output=True,
                text=True,
            )
            return int(result.stdout.strip())
    except Exception:
        pass

    # Fallback to logical cores / 2
    return max(1, os.cpu_count() // 2)


def detect_gpu_backend() -> GPUBackend:
    """
    Detect available GPU acceleration backend.

    Returns:
        GPUBackend enum value
    """
    import platform

    # Check for Apple Silicon
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return GPUBackend.METAL

    # Check for CUDA
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return GPUBackend.CUDA
    except Exception:
        pass

    # Check for ROCm (AMD)
    try:
        import subprocess

        result = subprocess.run(
            ["rocm-smi"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return GPUBackend.ROCM
    except Exception:
        pass

    return GPUBackend.NONE


def list_available_models(directory: str) -> list[dict[str, Any]]:
    """
    List GGUF models in a directory.

    Args:
        directory: Directory to scan

    Returns:
        List of model info dicts with path, name, size, quantization
    """
    models = []
    dir_path = Path(directory)

    if not dir_path.exists():
        return models

    for path in dir_path.glob("**/*.gguf"):
        size_mb = path.stat().st_size / (1024 * 1024)
        models.append(
            {
                "path": str(path),
                "name": path.name,
                "size_mb": round(size_mb, 2),
                "quantization": detect_quantization(str(path)).value,
            }
        )

    return sorted(models, key=lambda x: x["name"])


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # Main classes
    "LlamaCppProvider",
    "LlamaCppEmbeddings",
    "LlamaCppModel",
    # Configuration
    "LlamaCppModelConfig",
    "SamplingParams",
    # Enums
    "QuantizationLevel",
    "GPUBackend",
    "ChatTemplate",
    # Chat templates
    "CHAT_TEMPLATES",
    "apply_chat_template",
    # Grammar
    "GBNF_GRAMMARS",
    "create_grammar",
    "pydantic_to_gbnf",
    # Utilities
    "detect_quantization",
    "estimate_memory_usage",
    "get_optimal_threads",
    "detect_gpu_backend",
    "list_available_models",
    # Availability flag
    "LLAMA_CPP_AVAILABLE",
]
