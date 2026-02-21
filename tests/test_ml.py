"""
Tests for django_matt.ml module.

Covers:
- llamacpp.py — LlamaCpp provider (enums, data classes, utilities, provider, embeddings)
- vllm.py     — vLLM provider (data classes, client, provider)
- localai.py  — LocalAI provider (data classes, client, provider, embeddings)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Import the modules under test (optional deps guarded)
# ---------------------------------------------------------------------------

from django_matt.ai.base import (
    CompletionResponse,
    EmbeddingResponse,
    Message,
    Role,
    StreamChunk,
    Usage,
)

# llamacpp requires llama_cpp
from django_matt.ml import llamacpp
from django_matt.ml import vllm as vllm_mod
from django_matt.ml import localai as localai_mod


# =============================================================================
# Pydantic models for structured-output tests
# =============================================================================


class PersonSchema(BaseModel):
    name: str
    age: int


class ColorsSchema(BaseModel):
    colors: list[str]


# =============================================================================
# llamacpp — Enums and Constants
# =============================================================================


class TestLlamaCppEnums:
    """Test LlamaCpp enums have expected members."""

    def test_quantization_level_values(self):
        assert llamacpp.QuantizationLevel.Q4_K_M.value == "Q4_K_M"
        assert llamacpp.QuantizationLevel.F16.value == "F16"
        assert llamacpp.QuantizationLevel.UNKNOWN.value == "UNKNOWN"

    def test_gpu_backend_values(self):
        assert llamacpp.GPUBackend.NONE.value == "none"
        assert llamacpp.GPUBackend.METAL.value == "metal"
        assert llamacpp.GPUBackend.CUDA.value == "cuda"

    def test_chat_template_values(self):
        assert llamacpp.ChatTemplate.CHATML.value == "chatml"
        assert llamacpp.ChatTemplate.LLAMA3.value == "llama3"
        assert llamacpp.ChatTemplate.MISTRAL.value == "mistral"

    def test_chat_templates_dict_keys(self):
        """CHAT_TEMPLATES should have entries for the main template enums."""
        templates = llamacpp.CHAT_TEMPLATES
        assert llamacpp.ChatTemplate.CHATML in templates
        assert llamacpp.ChatTemplate.LLAMA in templates
        assert llamacpp.ChatTemplate.LLAMA3 in templates
        assert llamacpp.ChatTemplate.ALPACA in templates

    def test_chat_template_structure(self):
        """Each template dict must have the required keys."""
        required = {
            "system_prefix",
            "system_suffix",
            "user_prefix",
            "user_suffix",
            "assistant_prefix",
            "assistant_suffix",
            "bos",
            "eos",
        }
        for name, tmpl in llamacpp.CHAT_TEMPLATES.items():
            assert required.issubset(tmpl.keys()), f"Template {name} missing keys"

    def test_gbnf_grammars_keys(self):
        assert "json" in llamacpp.GBNF_GRAMMARS
        assert "yes_no" in llamacpp.GBNF_GRAMMARS
        assert "integer" in llamacpp.GBNF_GRAMMARS
        assert "float" in llamacpp.GBNF_GRAMMARS


# =============================================================================
# llamacpp — Utility Functions
# =============================================================================


class TestDetectQuantization:
    def test_q4_k_m(self):
        result = llamacpp.detect_quantization("/models/llama-7b.Q4_K_M.gguf")
        assert result == llamacpp.QuantizationLevel.Q4_K_M

    def test_q8_0(self):
        result = llamacpp.detect_quantization("/models/model.Q8_0.gguf")
        assert result == llamacpp.QuantizationLevel.Q8_0

    def test_f16(self):
        result = llamacpp.detect_quantization("/models/model.F16.gguf")
        assert result == llamacpp.QuantizationLevel.F16

    def test_unknown_quantization(self):
        result = llamacpp.detect_quantization("/models/model.gguf")
        assert result == llamacpp.QuantizationLevel.UNKNOWN

    def test_case_insensitive(self):
        """Filename is uppercased internally so mixed-case should still match."""
        result = llamacpp.detect_quantization("/models/model.q4_k_m.gguf")
        assert result == llamacpp.QuantizationLevel.Q4_K_M


class TestApplyChatTemplate:
    def test_chatml_template(self):
        messages = [
            Message.system("You are helpful."),
            Message.user("Hello"),
        ]
        result = llamacpp.apply_chat_template(messages, template=llamacpp.ChatTemplate.CHATML)
        assert "<|im_start|>system" in result
        assert "You are helpful." in result
        assert "<|im_start|>user" in result
        assert "Hello" in result
        # Generation prompt
        assert "<|im_start|>assistant" in result

    def test_chatml_no_generation_prompt(self):
        messages = [Message.user("Hi")]
        result = llamacpp.apply_chat_template(
            messages,
            template=llamacpp.ChatTemplate.CHATML,
            add_generation_prompt=False,
        )
        assert result.endswith("<|im_end|>\n")

    def test_alpaca_template(self):
        messages = [Message.user("Explain Python")]
        result = llamacpp.apply_chat_template(messages, template=llamacpp.ChatTemplate.ALPACA)
        assert "### Instruction:" in result
        assert "### Response:" in result

    def test_custom_template(self):
        custom = {
            "system_prefix": "[SYS]",
            "system_suffix": "[/SYS]",
            "user_prefix": "[U]",
            "user_suffix": "[/U]",
            "assistant_prefix": "[A]",
            "assistant_suffix": "[/A]",
            "bos": "",
            "eos": "",
        }
        messages = [Message.user("Hi")]
        result = llamacpp.apply_chat_template(messages, custom_template=custom)
        assert "[U]Hi[/U]" in result
        assert "[A]" in result

    def test_string_template_name(self):
        messages = [Message.user("Hi")]
        result = llamacpp.apply_chat_template(messages, template="chatml")
        assert "<|im_start|>user" in result

    def test_llama_system_inline(self):
        """Llama template inlines system message with first user message."""
        messages = [
            Message.system("You are a bot."),
            Message.user("Hello"),
        ]
        result = llamacpp.apply_chat_template(messages, template=llamacpp.ChatTemplate.LLAMA)
        assert "<<SYS>>" in result
        assert "[INST]" in result


class TestPydanticToGbnf:
    def test_simple_model(self):
        grammar = llamacpp.pydantic_to_gbnf(PersonSchema)
        assert "root" in grammar
        assert "string" in grammar
        # Should mention the property names in some form
        assert "name" in grammar
        assert "age" in grammar

    def test_list_model(self):
        grammar = llamacpp.pydantic_to_gbnf(ColorsSchema)
        assert "root" in grammar
        assert "colors" in grammar


class TestGetOptimalThreads:
    def test_returns_positive_int(self):
        result = llamacpp.get_optimal_threads()
        assert isinstance(result, int)
        assert result >= 1


# =============================================================================
# llamacpp — Dataclasses
# =============================================================================


class TestLlamaCppModelConfig:
    def test_to_llama_kwargs_defaults(self):
        cfg = llamacpp.LlamaCppModelConfig(model_path="/m.gguf")
        kwargs = cfg.to_llama_kwargs()
        assert kwargs["model_path"] == "/m.gguf"
        assert kwargs["n_ctx"] == 4096
        assert "n_threads" not in kwargs  # None → omitted

    def test_to_llama_kwargs_with_threads(self):
        cfg = llamacpp.LlamaCppModelConfig(model_path="/m.gguf", n_threads=8)
        kwargs = cfg.to_llama_kwargs()
        assert kwargs["n_threads"] == 8

    def test_to_llama_kwargs_with_rope(self):
        cfg = llamacpp.LlamaCppModelConfig(
            model_path="/m.gguf",
            rope_freq_base=10000.0,
            rope_freq_scale=1.0,
        )
        kwargs = cfg.to_llama_kwargs()
        assert kwargs["rope_freq_base"] == 10000.0
        assert kwargs["rope_freq_scale"] == 1.0


class TestSamplingParamsLlamaCpp:
    def test_to_llama_kwargs_defaults(self):
        p = llamacpp.SamplingParams()
        kwargs = p.to_llama_kwargs()
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 512
        assert "stop" not in kwargs
        assert "seed" not in kwargs

    def test_to_llama_kwargs_with_stop(self):
        p = llamacpp.SamplingParams(stop=["<end>"])
        kwargs = p.to_llama_kwargs()
        assert kwargs["stop"] == ["<end>"]

    def test_to_llama_kwargs_with_mirostat(self):
        p = llamacpp.SamplingParams(mirostat_mode=2, mirostat_tau=3.0)
        kwargs = p.to_llama_kwargs()
        assert kwargs["mirostat_mode"] == 2
        assert kwargs["mirostat_tau"] == 3.0

    def test_to_llama_kwargs_with_seed(self):
        p = llamacpp.SamplingParams(seed=42)
        kwargs = p.to_llama_kwargs()
        assert kwargs["seed"] == 42


# =============================================================================
# llamacpp — LlamaCppProvider (mocked)
# =============================================================================


class TestLlamaCppProvider:
    """Test LlamaCppProvider with mocked Llama instance."""

    def _make_provider(self) -> tuple[llamacpp.LlamaCppProvider, MagicMock]:
        """Create a provider with a pre-loaded mock model."""
        mock_llama = MagicMock()
        mock_model = MagicMock(spec=llamacpp.LlamaCppModel)
        mock_model.llama = mock_llama
        provider = llamacpp.LlamaCppProvider(model_path="/m.gguf", model=mock_model)
        return provider, mock_llama

    @pytest.mark.asyncio
    async def test_complete(self):
        provider, mock_llama = self._make_provider()
        mock_llama.create_chat_completion.return_value = {
            "choices": [
                {
                    "message": {"content": "Hello back!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        messages = [Message.user("Hello")]
        resp = await provider.complete(messages)

        assert isinstance(resp, CompletionResponse)
        assert resp.content == "Hello back!"
        assert resp.usage.total_tokens == 15
        mock_llama.create_chat_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate(self):
        provider, mock_llama = self._make_provider()
        mock_llama.return_value = {
            "choices": [{"text": "once upon a time"}],
        }

        result = await provider.generate("Once")
        assert result == "once upon a time"
        mock_llama.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream(self):
        provider, mock_llama = self._make_provider()
        mock_llama.create_chat_completion.return_value = [
            {"choices": [{"delta": {"content": "Hello"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}]},
        ]

        messages = [Message.user("Hi")]
        chunks = []
        async for chunk in provider.stream(messages):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].content == "Hello"
        assert chunks[1].content == " world"

    @pytest.mark.asyncio
    async def test_chat_with_template(self):
        provider, mock_llama = self._make_provider()
        mock_llama.return_value = {
            "choices": [{"text": "answer", "finish_reason": "stop"}],
        }

        messages = [Message.user("Hi")]
        resp = await provider.chat(messages, template=llamacpp.ChatTemplate.CHATML)

        assert isinstance(resp, CompletionResponse)
        assert resp.content == "answer"

    @pytest.mark.asyncio
    async def test_chat_without_template_delegates_to_complete(self):
        provider, mock_llama = self._make_provider()
        mock_llama.create_chat_completion.return_value = {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        messages = [Message.user("Hi")]
        resp = await provider.chat(messages)
        assert resp.content == "ok"

    def test_provider_name(self):
        provider, _ = self._make_provider()
        assert provider.provider_name == "llamacpp"

    def test_default_model(self):
        provider, _ = self._make_provider()
        assert provider.default_model == "/m.gguf"

    def test_ensure_model_no_path_raises(self):
        provider = llamacpp.LlamaCppProvider.__new__(llamacpp.LlamaCppProvider)
        provider._model = None
        provider._model_path = None
        with pytest.raises(ValueError, match="No model path"):
            provider._ensure_model()

    def test_unload(self):
        provider, _ = self._make_provider()
        assert provider._model is not None
        provider.unload()
        assert provider._model is None


# =============================================================================
# llamacpp — LlamaCppEmbeddings (mocked)
# =============================================================================


class TestLlamaCppEmbeddings:
    def _make_embeddings(self) -> tuple[llamacpp.LlamaCppEmbeddings, MagicMock]:
        mock_llama = MagicMock()
        mock_llama.embed.return_value = [0.1, 0.2, 0.3]

        with patch.object(llamacpp, "LLAMA_CPP_AVAILABLE", True), patch.object(
            llamacpp, "Llama", return_value=mock_llama
        ):
            emb = llamacpp.LlamaCppEmbeddings(model_path="/emb.gguf")
            # Force load
            emb._llama = mock_llama
            emb._dimensions = 3
        return emb, mock_llama

    @pytest.mark.asyncio
    async def test_embed(self):
        emb, mock_llama = self._make_embeddings()
        resp = await emb.embed(["hello", "world"])
        assert isinstance(resp, EmbeddingResponse)
        assert len(resp.embeddings) == 2

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        emb, mock_llama = self._make_embeddings()
        resp = await emb.embed_batch(["a", "b", "c", "d"], batch_size=2)
        assert len(resp.embeddings) == 4

    def test_default_model(self):
        emb, _ = self._make_embeddings()
        assert emb.default_model == "/emb.gguf"

    def test_dimensions(self):
        emb, _ = self._make_embeddings()
        assert emb.dimensions == 3

    def test_unload(self):
        emb, _ = self._make_embeddings()
        emb.unload()
        assert emb._llama is None

    def test_ensure_model_no_path_raises(self):
        emb = llamacpp.LlamaCppEmbeddings.__new__(llamacpp.LlamaCppEmbeddings)
        emb._llama = None
        emb._model_path = None
        emb._dimensions = None
        with pytest.raises((ValueError, ImportError)):
            emb._ensure_model()


# =============================================================================
# vllm — Data classes
# =============================================================================


class TestVLLMSamplingParams:
    def test_to_dict_defaults_empty(self):
        """Default params should produce an empty dict (all defaults)."""
        p = vllm_mod.SamplingParams()
        d = p.to_dict()
        assert isinstance(d, dict)
        # All values match defaults, so dict should be empty
        assert d == {}

    def test_to_dict_custom_values(self):
        p = vllm_mod.SamplingParams(temperature=0.5, top_p=0.9, max_tokens=100)
        d = p.to_dict()
        assert d["temperature"] == 0.5
        assert d["top_p"] == 0.9
        assert d["max_tokens"] == 100

    def test_to_dict_seed(self):
        p = vllm_mod.SamplingParams(seed=42)
        d = p.to_dict()
        assert d["seed"] == 42


class TestGuidedDecodingParams:
    def test_to_dict_json(self):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        p = vllm_mod.GuidedDecodingParams(json_schema=schema)
        d = p.to_dict()
        assert d["guided_json"] == schema

    def test_to_dict_regex(self):
        p = vllm_mod.GuidedDecodingParams(regex=r"[0-9]+")
        d = p.to_dict()
        assert d["guided_regex"] == r"[0-9]+"

    def test_to_dict_choice(self):
        p = vllm_mod.GuidedDecodingParams(choice=["yes", "no"])
        d = p.to_dict()
        assert d["guided_choice"] == ["yes", "no"]

    def test_to_dict_json_object(self):
        p = vllm_mod.GuidedDecodingParams(json_object=True)
        d = p.to_dict()
        assert d["response_format"] == {"type": "json_object"}

    def test_to_dict_empty(self):
        p = vllm_mod.GuidedDecodingParams()
        assert p.to_dict() == {}


class TestLoRAConfig:
    def test_to_dict_with_path(self):
        cfg = vllm_mod.LoRAConfig(lora_path="/adapters/lora1")
        d = cfg.to_dict()
        assert d["lora_path"] == "/adapters/lora1"

    def test_to_dict_empty(self):
        cfg = vllm_mod.LoRAConfig()
        assert cfg.to_dict() == {}


class TestVLLMDataclasses:
    def test_batch_request(self):
        req = vllm_mod.BatchRequest(id="r1", prompt="Hello", priority=5)
        assert req.id == "r1"
        assert req.priority == 5

    def test_batch_result(self):
        res = vllm_mod.BatchResult(id="r1", error="oops", latency_ms=42.0)
        assert res.error == "oops"
        assert res.latency_ms == 42.0

    def test_server_metrics_defaults(self):
        m = vllm_mod.ServerMetrics()
        assert m.num_requests_running == 0
        assert m.gpu_cache_usage_perc == 0.0

    def test_model_info(self):
        info = vllm_mod.ModelInfo(id="llama-8b", tensor_parallel_size=4, dtype="bfloat16")
        assert info.id == "llama-8b"
        assert info.tensor_parallel_size == 4

    def test_guided_decoding_type_enum(self):
        assert vllm_mod.GuidedDecodingType.JSON.value == "json"
        assert vllm_mod.GuidedDecodingType.REGEX.value == "regex"


# =============================================================================
# vllm — VLLMClient (mocked httpx)
# =============================================================================


class TestVLLMClient:
    def _make_client(self):
        return vllm_mod.VLLMClient(base_url="http://localhost:8000")

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        client._client = mock_http

        result = await client.health_check()
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        client._client = mock_http

        result = await client.health_check()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        client = self._make_client()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=ConnectionError("refused"))
        client._client = mock_http

        result = await client.health_check()
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_list_models(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "model-1"}]}
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        client._client = mock_http

        result = await client.list_models()
        assert result["data"][0]["id"] == "model-1"

    @pytest.mark.asyncio
    async def test_completions(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"text": "hello", "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        client._client = mock_http

        result = await client.completions({"model": "m", "prompt": "hi"})
        assert result["choices"][0]["text"] == "hello"

    @pytest.mark.asyncio
    async def test_chat_completions(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hi!"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        }
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        client._client = mock_http

        result = await client.chat_completions({"model": "m", "messages": []})
        assert result["choices"][0]["message"]["content"] == "hi!"

    @pytest.mark.asyncio
    async def test_close(self):
        client = self._make_client()
        mock_http = AsyncMock()
        mock_http.aclose = AsyncMock()
        client._client = mock_http

        await client.close()
        mock_http.aclose.assert_awaited_once()
        assert client._client is None


# =============================================================================
# vllm — VLLMProvider (mocked)
# =============================================================================


class TestVLLMProvider:
    def _make_provider(self) -> tuple[vllm_mod.VLLMProvider, AsyncMock]:
        provider = vllm_mod.VLLMProvider(
            base_url="http://localhost:8000",
            model="test-model",
        )
        mock_client = AsyncMock(spec=vllm_mod.VLLMClient)
        provider._client = mock_client
        return provider, mock_client

    def test_provider_name(self):
        provider, _ = self._make_provider()
        assert provider.provider_name == "vllm"

    def test_default_model(self):
        provider, _ = self._make_provider()
        assert provider.default_model == "test-model"

    def test_usage_tracking(self):
        provider, _ = self._make_provider()
        provider._track_usage({"prompt_tokens": 10, "completion_tokens": 5})
        provider._track_usage({"prompt_tokens": 3, "completion_tokens": 2})

        stats = provider.get_usage_stats()
        assert stats["total_prompt_tokens"] == 13
        assert stats["total_completion_tokens"] == 7
        assert stats["total_tokens"] == 20

    def test_reset_usage_stats(self):
        provider, _ = self._make_provider()
        provider._track_usage({"prompt_tokens": 10, "completion_tokens": 5})
        provider.reset_usage_stats()
        assert provider.get_usage_stats()["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_generate(self):
        provider, mock_client = self._make_provider()
        mock_client.completions = AsyncMock(
            return_value={
                "choices": [{"text": "generated text", "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
                "model": "test-model",
            }
        )

        resp = await provider.generate("Hello")
        assert isinstance(resp, CompletionResponse)
        assert resp.content == "generated text"
        assert resp.usage.total_tokens == 15

    @pytest.mark.asyncio
    async def test_complete(self):
        provider, mock_client = self._make_provider()
        mock_client.chat_completions = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {"content": "response text"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
                "model": "test-model",
            }
        )

        messages = [Message.user("Hi")]
        resp = await provider.complete(messages)
        assert resp.content == "response text"
        assert resp.usage.total_tokens == 8

    @pytest.mark.asyncio
    async def test_chat_delegates_to_complete(self):
        provider, mock_client = self._make_provider()
        mock_client.chat_completions = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "model": "test-model",
            }
        )

        resp = await provider.chat([Message.user("Hi")])
        assert resp.content == "ok"

    @pytest.mark.asyncio
    async def test_close(self):
        provider, mock_client = self._make_provider()
        await provider.close()
        mock_client.close.assert_awaited_once()


# =============================================================================
# localai — Enums and Data Classes
# =============================================================================


class TestLocalAIEnums:
    def test_backend_values(self):
        assert localai_mod.LocalAIBackend.LLAMA_CPP.value == "llama-cpp"
        assert localai_mod.LocalAIBackend.WHISPER.value == "whisper"
        assert localai_mod.LocalAIBackend.DIFFUSERS.value == "diffusers"

    def test_image_size_values(self):
        assert localai_mod.ImageSize.SMALL.value == "256x256"
        assert localai_mod.ImageSize.MEDIUM.value == "512x512"
        assert localai_mod.ImageSize.LARGE.value == "1024x1024"


class TestLocalAIDataclasses:
    def test_model_info(self):
        info = localai_mod.ModelInfo(id="llama-3-8b", backend="llama-cpp")
        assert info.id == "llama-3-8b"
        assert info.owned_by == "localai"

    def test_image_generation_response(self):
        resp = localai_mod.ImageGenerationResponse(
            images=["base64data"], model="sd", created=123
        )
        assert len(resp.images) == 1

    def test_transcription_response(self):
        resp = localai_mod.TranscriptionResponse(text="Hello world", language="en")
        assert resp.text == "Hello world"

    def test_speech_response(self):
        resp = localai_mod.SpeechResponse(audio=b"\x00\x01", format="wav")
        assert len(resp.audio) == 2

    def test_vision_response(self):
        resp = localai_mod.VisionResponse(content="A cat", model="llava")
        assert resp.content == "A cat"


# =============================================================================
# localai — LocalAIClient (mocked)
# =============================================================================


class TestLocalAIClient:
    def _make_client(self):
        return localai_mod.LocalAIClient(base_url="http://localhost:8080")

    @pytest.mark.asyncio
    async def test_get(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        client._client = mock_http

        result = await client.get("/v1/models")
        assert result == {"data": []}

    @pytest.mark.asyncio
    async def test_post(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": []}
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        client._client = mock_http

        result = await client.post("/v1/completions", json={})
        assert result == {"choices": []}

    @pytest.mark.asyncio
    async def test_post_raw(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.content = b"\x00\x01\x02"
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        client._client = mock_http

        result = await client.post_raw("/v1/audio/speech", json={})
        assert result == b"\x00\x01\x02"

    @pytest.mark.asyncio
    async def test_close(self):
        client = self._make_client()
        mock_http = AsyncMock()
        mock_http.aclose = AsyncMock()
        client._client = mock_http

        await client.close()
        mock_http.aclose.assert_awaited_once()
        assert client._client is None

    def test_base_url_strips_trailing_slash(self):
        client = localai_mod.LocalAIClient(base_url="http://localhost:8080/")
        assert client.base_url == "http://localhost:8080"


# =============================================================================
# localai — LocalAIProvider (mocked)
# =============================================================================


class TestLocalAIProvider:
    def _make_provider(self) -> tuple[localai_mod.LocalAIProvider, AsyncMock]:
        provider = localai_mod.LocalAIProvider(
            base_url="http://localhost:8080",
            model="test-model",
        )
        mock_client = AsyncMock(spec=localai_mod.LocalAIClient)
        provider._client = mock_client
        return provider, mock_client

    def test_provider_name(self):
        provider, _ = self._make_provider()
        assert provider.provider_name == "localai"

    def test_default_model(self):
        p = localai_mod.LocalAIProvider(base_url="http://localhost:8080")
        assert p.default_model == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_complete(self):
        provider, mock_client = self._make_provider()
        mock_client.post = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {"content": "Hello!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                "model": "test-model",
            }
        )

        messages = [Message.user("Hi")]
        resp = await provider.complete(messages)
        assert resp.content == "Hello!"
        assert resp.usage.total_tokens == 5

    @pytest.mark.asyncio
    async def test_complete_with_tool_calls(self):
        provider, mock_client = self._make_provider()
        mock_client.post = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "tc1",
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": '{"city": "NYC"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "model": "test-model",
            }
        )

        resp = await provider.complete([Message.user("Weather?")])
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "get_weather"

    @pytest.mark.asyncio
    async def test_chat_delegates(self):
        provider, mock_client = self._make_provider()
        mock_client.post = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "model": "test-model",
            }
        )

        resp = await provider.chat([Message.user("Hi")])
        assert resp.content == "ok"

    @pytest.mark.asyncio
    async def test_generate(self):
        provider, mock_client = self._make_provider()
        mock_client.post = AsyncMock(
            return_value={
                "choices": [{"text": "generated", "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
                "model": "test-model",
            }
        )

        resp = await provider.generate("Once upon")
        assert resp.content == "generated"

    @pytest.mark.asyncio
    async def test_list_models(self):
        provider, mock_client = self._make_provider()
        mock_client.get = AsyncMock(
            return_value={
                "data": [
                    {"id": "llama-3-8b", "object": "model", "backend": "llama-cpp"},
                ]
            }
        )

        models = await provider.list_models()
        assert len(models) == 1
        assert models[0].id == "llama-3-8b"

    @pytest.mark.asyncio
    async def test_load_model(self):
        provider, mock_client = self._make_provider()
        mock_client.post = AsyncMock(return_value={})

        result = await provider.load_model("llama-3-8b")
        assert result is True

    @pytest.mark.asyncio
    async def test_load_model_failure(self):
        provider, mock_client = self._make_provider()
        mock_client.post = AsyncMock(side_effect=Exception("fail"))

        result = await provider.load_model("bad-model")
        assert result is False

    @pytest.mark.asyncio
    async def test_close(self):
        provider, mock_client = self._make_provider()
        await provider.close()
        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_image(self):
        provider, mock_client = self._make_provider()
        mock_client.post = AsyncMock(
            return_value={
                "data": [{"b64_json": "abc123"}],
                "created": 1234,
            }
        )

        resp = await provider.generate_image("A sunset")
        assert isinstance(resp, localai_mod.ImageGenerationResponse)
        assert resp.images == ["abc123"]

    @pytest.mark.asyncio
    async def test_speak(self):
        provider, mock_client = self._make_provider()
        mock_client.post_raw = AsyncMock(return_value=b"\x00\x01")

        resp = await provider.speak("Hello")
        assert isinstance(resp, localai_mod.SpeechResponse)
        assert resp.audio == b"\x00\x01"


# =============================================================================
# localai — LocalAIEmbeddings (mocked)
# =============================================================================


class TestLocalAIEmbeddings:
    def _make_embeddings(self) -> tuple[localai_mod.LocalAIEmbeddings, AsyncMock]:
        emb = localai_mod.LocalAIEmbeddings(
            base_url="http://localhost:8080",
            model="text-embedding-ada-002",
        )
        mock_client = AsyncMock(spec=localai_mod.LocalAIClient)
        emb._client = mock_client
        return emb, mock_client

    def test_default_model(self):
        emb, _ = self._make_embeddings()
        assert emb.default_model == "text-embedding-ada-002"

    def test_dimensions_known_model(self):
        emb, _ = self._make_embeddings()
        assert emb.dimensions == 1536

    def test_dimensions_unknown_model(self):
        emb = localai_mod.LocalAIEmbeddings(model="custom-model")
        assert emb.dimensions == 1536  # default fallback

    @pytest.mark.asyncio
    async def test_embed(self):
        emb, mock_client = self._make_embeddings()
        mock_client.post = AsyncMock(
            return_value={
                "data": [
                    {"embedding": [0.1, 0.2, 0.3]},
                    {"embedding": [0.4, 0.5, 0.6]},
                ],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
                "model": "text-embedding-ada-002",
            }
        )

        resp = await emb.embed(["hello", "world"])
        assert isinstance(resp, EmbeddingResponse)
        assert len(resp.embeddings) == 2
        assert resp.embeddings[0] == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_close(self):
        emb, mock_client = self._make_embeddings()
        await emb.close()
        mock_client.close.assert_awaited_once()


# =============================================================================
# localai — Factory helpers
# =============================================================================


class TestLocalAIFactories:
    def test_get_localai_provider(self):
        p = localai_mod.get_localai_provider(base_url="http://localhost:8080")
        assert isinstance(p, localai_mod.LocalAIProvider)

    def test_get_localai_embeddings(self):
        e = localai_mod.get_localai_embeddings(base_url="http://localhost:8080")
        assert isinstance(e, localai_mod.LocalAIEmbeddings)
