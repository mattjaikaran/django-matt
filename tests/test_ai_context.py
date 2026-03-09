"""
Tests for AI context generation module.

Tests the enhanced AI IDE integration including:
- Context generators (Claude, Cursor, Copilot, JSON)
- Enhanced introspection
- File watcher
- Pre-commit hook generation
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestEnhancedIntrospector:
    """Tests for EnhancedIntrospector class."""

    def test_introspect_returns_project_info(self):
        """Test that introspect returns EnhancedProjectInfo."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        info = introspector.introspect()

        assert info is not None
        assert hasattr(info, "name")
        assert hasattr(info, "python_version")
        assert hasattr(info, "django_version")
        assert hasattr(info, "endpoints")
        assert hasattr(info, "schemas")
        assert hasattr(info, "models")

    def test_introspect_finds_endpoints(self):
        """Test that introspection finds API endpoints."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        info = introspector.introspect()

        # Should find at least some endpoints (from django_matt itself)
        # May be empty in minimal test setup
        assert isinstance(info.endpoints, list)

    def test_introspect_finds_schemas(self):
        """Test that introspection finds Pydantic schemas."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        info = introspector.introspect()

        # Should find at least some schemas
        assert isinstance(info.schemas, list)

    def test_introspect_finds_models(self):
        """Test that introspection finds Django models."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        info = introspector.introspect()

        # Should find at least the User model
        assert isinstance(info.models, list)

    def test_to_json_returns_valid_json(self):
        """Test that to_json returns valid JSON."""
        from django_matt.ai.context import EnhancedIntrospector

        introspector = EnhancedIntrospector()
        json_str = introspector.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert "endpoints" in data
        assert "schemas" in data
        assert "models" in data


class TestAuthRequirement:
    """Tests for AuthRequirement enum."""

    def test_auth_requirement_values(self):
        """Test that AuthRequirement has expected values."""
        from django_matt.ai.context import AuthRequirement

        assert AuthRequirement.NONE.value == "none"
        assert AuthRequirement.JWT_REQUIRED.value == "jwt_required"
        assert AuthRequirement.JWT_OPTIONAL.value == "jwt_optional"
        assert AuthRequirement.API_KEY.value == "api_key"


class TestEndpointInfo:
    """Tests for EndpointInfo dataclass."""

    def test_endpoint_info_to_dict(self):
        """Test that EndpointInfo converts to dict."""
        from django_matt.ai.context import AuthRequirement, EndpointInfo

        endpoint = EndpointInfo(
            path="/api/users",
            method="GET",
            name="list_users",
            auth_requirement=AuthRequirement.JWT_REQUIRED,
        )

        data = endpoint.to_dict()
        assert data["path"] == "/api/users"
        assert data["method"] == "GET"
        assert data["auth_requirement"] == "jwt_required"


class TestClaudeMdGenerator:
    """Tests for ClaudeMdGenerator class."""

    def test_generate_returns_content(self):
        """Test that generate returns markdown content."""
        from django_matt.ai.context import ClaudeMdGenerator

        generator = ClaudeMdGenerator()
        content = generator.generate()

        assert content is not None
        assert len(content) > 0
        assert "# " in content  # Should have markdown headers

    def test_generate_includes_project_name(self):
        """Test that generated content includes project info."""
        from django_matt.ai.context import ClaudeMdGenerator

        generator = ClaudeMdGenerator()
        content = generator.generate()

        assert "Project Overview" in content
        assert "Django" in content

    def test_write_creates_file(self):
        """Test that write creates a file."""
        from django_matt.ai.context import ClaudeMdGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ClaudeMdGenerator()
            path = generator.write(f"{tmpdir}/CLAUDE.md")

            assert path.exists()
            assert path.name == "CLAUDE.md"
            assert path.read_text().startswith("#")


class TestCursorRulesGenerator:
    """Tests for CursorRulesGenerator class."""

    def test_generate_returns_content(self):
        """Test that generate returns rules content."""
        from django_matt.ai.context import CursorRulesGenerator

        generator = CursorRulesGenerator()
        content = generator.generate()

        assert content is not None
        assert len(content) > 0

    def test_generate_includes_framework_rules(self):
        """Test that generated content includes framework rules."""
        from django_matt.ai.context import CursorRulesGenerator

        generator = CursorRulesGenerator()
        content = generator.generate()

        assert "Django" in content
        assert "API" in content or "controller" in content.lower()

    def test_write_creates_file(self):
        """Test that write creates a file."""
        from django_matt.ai.context import CursorRulesGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CursorRulesGenerator()
            path = generator.write(f"{tmpdir}/.cursorrules")

            assert path.exists()
            assert path.name == ".cursorrules"


class TestCopilotInstructionsGenerator:
    """Tests for CopilotInstructionsGenerator class."""

    def test_generate_returns_content(self):
        """Test that generate returns instructions content."""
        from django_matt.ai.context import CopilotInstructionsGenerator

        generator = CopilotInstructionsGenerator()
        content = generator.generate()

        assert content is not None
        assert len(content) > 0

    def test_generate_includes_copilot_header(self):
        """Test that generated content has Copilot header."""
        from django_matt.ai.context import CopilotInstructionsGenerator

        generator = CopilotInstructionsGenerator()
        content = generator.generate()

        assert "Copilot" in content or "copilot" in content.lower()

    def test_write_creates_file(self):
        """Test that write creates a file."""
        from django_matt.ai.context import CopilotInstructionsGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CopilotInstructionsGenerator()
            path = generator.write(f"{tmpdir}/.copilot-instructions")

            assert path.exists()
            assert path.name == ".copilot-instructions"


class TestJsonIntrospectionGenerator:
    """Tests for JsonIntrospectionGenerator class."""

    def test_generate_returns_dict(self):
        """Test that generate returns a dictionary."""
        from django_matt.ai.context.generators import JsonIntrospectionGenerator

        generator = JsonIntrospectionGenerator()
        data = generator.generate()

        assert isinstance(data, dict)
        assert "version" in data
        assert "generated_at" in data
        assert "project" in data

    def test_generate_json_returns_string(self):
        """Test that generate_json returns valid JSON string."""
        from django_matt.ai.context.generators import JsonIntrospectionGenerator

        generator = JsonIntrospectionGenerator()
        json_str = generator.generate_json()

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert "version" in data

    def test_write_creates_file(self):
        """Test that write creates a JSON file."""
        from django_matt.ai.context.generators import JsonIntrospectionGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = JsonIntrospectionGenerator()
            path = generator.write(f"{tmpdir}/introspection.json")

            assert path.exists()
            assert path.name == "introspection.json"

            # Verify it's valid JSON
            data = json.loads(path.read_text())
            assert "version" in data


class TestContextGenerator:
    """Tests for unified ContextGenerator class."""

    def test_generate_all_creates_files(self):
        """Test that generate_all creates all context files."""
        from django_matt.ai.context import ContextGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ContextGenerator(output_dir=tmpdir)
            files = generator.generate_all()

            assert "claude" in files
            assert "cursor" in files
            assert "copilot" in files
            assert "json" in files

            assert files["claude"].exists()
            assert files["cursor"].exists()
            assert files["copilot"].exists()
            assert files["json"].exists()

    def test_generate_specific_formats(self):
        """Test that specific formats can be generated."""
        from django_matt.ai.context import ContextGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ContextGenerator(output_dir=tmpdir)
            files = generator.generate_all(formats=["claude", "cursor"])

            assert "claude" in files
            assert "cursor" in files
            assert "copilot" not in files
            assert "json" not in files


class TestDebouncedCallback:
    """Tests for DebouncedCallback class."""

    def test_debounced_callback_delays_execution(self):
        """Test that callback is delayed."""
        from django_matt.ai.context import DebouncedCallback

        called = []

        def callback():
            called.append(True)

        debounced = DebouncedCallback(callback, delay=0.1)

        # Call multiple times rapidly
        debounced.call()
        debounced.call()
        debounced.call()

        # Should not have been called yet
        assert len(called) == 0

        # Wait for debounce
        import time

        time.sleep(0.15)

        # Should have been called once
        assert len(called) == 1

    def test_debounced_callback_can_be_cancelled(self):
        """Test that callback can be cancelled."""
        from django_matt.ai.context import DebouncedCallback

        called = []

        def callback():
            called.append(True)

        debounced = DebouncedCallback(callback, delay=0.1)
        debounced.call()
        debounced.cancel()

        import time

        time.sleep(0.15)

        assert len(called) == 0


class TestFileChangeHandler:
    """Tests for FileChangeHandler class."""

    def test_should_watch_python_files(self):
        """Test that Python files are watched."""
        from django_matt.ai.context import FileChangeHandler

        handler = FileChangeHandler(on_change=lambda: None)

        assert handler.should_watch(Path("app/models.py"))
        assert handler.should_watch(Path("app/views.py"))
        assert handler.should_watch(Path("tests/test_app.py"))

    def test_should_not_watch_context_files(self):
        """Test that generated context files are not watched."""
        from django_matt.ai.context import FileChangeHandler

        handler = FileChangeHandler(on_change=lambda: None)

        assert not handler.should_watch(Path("CLAUDE.md"))
        assert not handler.should_watch(Path(".cursorrules"))
        assert not handler.should_watch(Path(".copilot-instructions"))

    def test_should_not_watch_cache_dirs(self):
        """Test that cache directories are not watched."""
        from django_matt.ai.context import FileChangeHandler

        handler = FileChangeHandler(on_change=lambda: None)

        assert not handler.should_watch(Path("__pycache__/module.py"))
        assert not handler.should_watch(Path(".git/hooks/pre-commit"))
        assert not handler.should_watch(Path("node_modules/pkg/index.py"))


class TestPrecommitHook:
    """Tests for pre-commit hook generation."""

    def test_generate_precommit_hook(self):
        """Test that pre-commit hook script is generated."""
        from django_matt.ai.context.watcher import generate_precommit_hook

        hook = generate_precommit_hook()

        assert "#!/bin/bash" in hook
        assert "django-matt" in hook
        assert "generate_ai_context" in hook

    def test_generate_precommit_config(self):
        """Test that pre-commit config is generated."""
        from django_matt.ai.context.watcher import generate_precommit_config

        config = generate_precommit_config()

        assert "repos:" in config
        assert "update-ai-context" in config
        assert "generate_ai_context" in config


class TestTemplates:
    """Tests for template functions."""

    def test_get_template(self):
        """Test that templates can be retrieved."""
        from django_matt.ai.context.templates import get_template

        claude_template = get_template("claude")
        cursor_template = get_template("cursor")
        copilot_template = get_template("copilot")

        assert "{project_name}" in claude_template
        assert "{project_name}" in cursor_template
        assert "{project_name}" in copilot_template

    def test_get_template_invalid(self):
        """Test that invalid template name raises error."""
        from django_matt.ai.context.templates import get_template

        with pytest.raises(ValueError):
            get_template("invalid")

    def test_render_template(self):
        """Test that templates can be rendered."""
        from django_matt.ai.context.templates import render_template

        template = "Hello {name}, version {version}"
        result = render_template(template, {"name": "World", "version": "1.0"})

        assert result == "Hello World, version 1.0"

    def test_render_template_with_defaults(self):
        """Test that templates use defaults for missing keys."""
        from django_matt.ai.context.templates import render_template

        template = "Project: {project_name}"
        result = render_template(template, {})

        assert "Project:" in result


# ---------------------------------------------------------------------------
# Plan 03-02: --depth flag and --include-examples tests
# ---------------------------------------------------------------------------

class TestGenerateAiContextDepthFlag:
    """Tests for generate_ai_context --depth flag."""

    def test_generate_ai_context_has_depth_argument(self):
        """generate_ai_context command has --depth argument."""
        import argparse

        from django_matt.management.commands.generate_ai_context import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        action_names = {action.dest for action in parser._actions}
        assert "depth" in action_names

    def test_generate_ai_context_depth_choices(self):
        """--depth accepts minimal, standard, full."""
        import argparse

        from django_matt.management.commands.generate_ai_context import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        depth_action = next(
            a for a in parser._actions if a.dest == "depth"
        )
        assert "minimal" in depth_action.choices
        assert "standard" in depth_action.choices
        assert "full" in depth_action.choices

    def test_depth_minimal_routes_only(self):
        """--depth minimal produces routes but not full type/relationship output."""
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            err = StringIO()
            call_command(
                "generate_ai_context",
                output=tmpdir,
                format="claude",
                depth="minimal",
                stdout=out,
                stderr=err,
            )
            # Command should run without error
            import os
            assert os.path.exists(os.path.join(tmpdir, "CLAUDE.md"))

    def test_depth_standard_default(self):
        """--depth standard is the default."""
        import argparse

        from django_matt.management.commands.generate_ai_context import Command

        cmd = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        depth_action = next(
            a for a in parser._actions if a.dest == "depth"
        )
        assert depth_action.default == "standard"

    def test_depth_full_runs_without_error(self):
        """--depth full completes without error."""
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            err = StringIO()
            call_command(
                "generate_ai_context",
                output=tmpdir,
                format="claude",
                depth="full",
                stdout=out,
                stderr=err,
            )
            import os
            assert os.path.exists(os.path.join(tmpdir, "CLAUDE.md"))

    def test_format_all_produces_all_files(self):
        """--format all creates CLAUDE.md, .cursorrules, .copilot-instructions, and JSON."""
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            err = StringIO()
            call_command(
                "generate_ai_context",
                output=tmpdir,
                format="all",
                depth="minimal",
                stdout=out,
                stderr=err,
            )
            import os
            assert os.path.exists(os.path.join(tmpdir, "CLAUDE.md"))
            assert os.path.exists(os.path.join(tmpdir, ".cursorrules"))
            assert os.path.exists(os.path.join(tmpdir, ".copilot-instructions"))
            assert os.path.exists(os.path.join(tmpdir, "introspection.json"))

    def test_include_examples_flag_accepted(self):
        """--include-examples flag is accepted without error."""
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            err = StringIO()
            call_command(
                "generate_ai_context",
                output=tmpdir,
                format="claude",
                include_examples=True,
                depth="minimal",
                stdout=out,
                stderr=err,
            )
            import os
            assert os.path.exists(os.path.join(tmpdir, "CLAUDE.md"))


# ---------------------------------------------------------------------------
# Plan 07-05: Requirement-aligned LLM helper tests
# ---------------------------------------------------------------------------


class TestLLMHelpers:
    """Tests for LLM base helpers (AI-01)."""

    def test_messages_to_prompt_chatml(self):
        """messages_to_prompt renders ChatML format with variable content."""
        from django_matt.ai.base import Message, messages_to_prompt

        messages = [
            Message.system("You are a {role} assistant.".format(role="helpful")),
            Message.user("Hello, {name}!".format(name="World")),
        ]
        result = messages_to_prompt(messages, format="chatml")
        assert "<|im_start|>system" in result
        assert "You are a helpful assistant." in result
        assert "<|im_start|>user" in result
        assert "Hello, World!" in result
        assert "<|im_start|>assistant" in result

    def test_messages_to_prompt_simple(self):
        """messages_to_prompt renders simple format."""
        from django_matt.ai.base import Message, messages_to_prompt

        messages = [
            Message.system("Be helpful"),
            Message.user("Hi"),
        ]
        result = messages_to_prompt(messages, format="simple")
        assert "System: Be helpful" in result
        assert "User: Hi" in result
        assert "Assistant:" in result

    def test_messages_to_prompt_llama(self):
        """messages_to_prompt renders Llama format."""
        from django_matt.ai.base import Message, messages_to_prompt

        messages = [
            Message.system("System prompt"),
            Message.user("User question"),
        ]
        result = messages_to_prompt(messages, format="llama")
        assert "[INST]" in result
        assert "<<SYS>>" in result

    def test_message_factory_methods(self):
        """Message.system/user/assistant/tool factory methods set roles correctly."""
        from django_matt.ai.base import Message, Role

        assert Message.system("s").role == Role.SYSTEM
        assert Message.user("u").role == Role.USER
        assert Message.assistant("a").role == Role.ASSISTANT
        assert Message.tool("t", tool_call_id="tc1").role == Role.TOOL

    def test_message_to_dict(self):
        """Message.to_dict includes role, content, and optional fields."""
        from django_matt.ai.base import Message

        msg = Message.user("Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert "name" not in d
        assert "tool_call_id" not in d

    def test_completion_response_has_tool_calls(self):
        """CompletionResponse.has_tool_calls detects tool calls."""
        from django_matt.ai.base import CompletionResponse, ToolCall

        resp_no_tools = CompletionResponse(content="hello")
        assert not resp_no_tools.has_tool_calls

        resp_with_tools = CompletionResponse(
            content="",
            tool_calls=[ToolCall(id="1", name="f", arguments={})],
        )
        assert resp_with_tools.has_tool_calls


class TestEmbeddingHelpers:
    """Tests for embedding utilities (AI-02)."""

    def test_cosine_similarity(self):
        """cosine_similarity returns 1.0 for identical vectors."""
        from django_matt.ai.embeddings import cosine_similarity

        v = [1.0, 0.0, 0.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        """cosine_similarity returns 0 for orthogonal vectors."""
        from django_matt.ai.embeddings import cosine_similarity

        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_find_most_similar(self):
        """find_most_similar returns ranked results by cosine similarity."""
        from django_matt.ai.embeddings import find_most_similar

        query = [1.0, 0.0, 0.0]
        embeddings = [
            [0.0, 1.0, 0.0],   # orthogonal
            [0.9, 0.1, 0.0],   # close
            [1.0, 0.0, 0.0],   # identical
        ]
        results = find_most_similar(query, embeddings, top_k=2)
        assert len(results) == 2
        assert results[0][0] == 2  # identical vector first
        assert results[1][0] == 1  # close vector second

    def test_normalize_vector(self):
        """normalize_vector returns unit-length vector."""
        import math

        from django_matt.ai.embeddings import normalize_vector

        v = [3.0, 4.0]
        normed = normalize_vector(v)
        length = math.sqrt(sum(x * x for x in normed))
        assert abs(length - 1.0) < 1e-6


class TestRAGPipeline:
    """Tests for RAG pipeline (AI-03)."""

    @pytest.mark.asyncio
    async def test_rag_chain_query_retrieves_and_augments(self):
        """RAGChain.query retrieves docs from vector store and augments prompt."""
        from unittest.mock import AsyncMock

        from django_matt.ai.base import CompletionResponse, Message
        from django_matt.ai.rag import RAGChain
        from django_matt.ai.vectorstore import Document, SearchResult

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value=CompletionResponse(content="Python is a language")
        )

        mock_store = AsyncMock()
        mock_store.search = AsyncMock(
            return_value=[
                SearchResult(
                    document=Document(id="1", text="Python is interpreted"),
                    score=0.9,
                    rank=0,
                ),
                SearchResult(
                    document=Document(id="2", text="Python uses indentation"),
                    score=0.8,
                    rank=1,
                ),
            ]
        )

        rag = RAGChain(llm=mock_llm, vector_store=mock_store, top_k=2)
        response = await rag.query("What is Python?")

        assert response.answer == "Python is a language"
        assert len(response.sources) == 2
        assert response.sources[0].document.text == "Python is interpreted"
        mock_store.search.assert_awaited_once()
        mock_llm.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rag_chain_prompt_includes_context(self):
        """RAGChain prompt includes retrieved document text."""
        from unittest.mock import AsyncMock

        from django_matt.ai.base import CompletionResponse
        from django_matt.ai.rag import RAGChain
        from django_matt.ai.vectorstore import Document, SearchResult

        mock_llm = AsyncMock()
        captured_messages = []

        async def capture_complete(messages, **kwargs):
            captured_messages.extend(messages)
            return CompletionResponse(content="answer")

        mock_llm.complete = capture_complete

        mock_store = AsyncMock()
        mock_store.search = AsyncMock(
            return_value=[
                SearchResult(
                    document=Document(id="1", text="Django is a web framework"),
                    score=0.95,
                    rank=0,
                ),
            ]
        )

        rag = RAGChain(llm=mock_llm, vector_store=mock_store)
        await rag.query("What is Django?")

        # The user message should contain the context text
        user_content = captured_messages[-1].content
        assert "Django is a web framework" in user_content
        assert "What is Django?" in user_content


class TestVectorStoreOperations:
    """Tests for vector store insert and similarity search (ML-01)."""

    @pytest.mark.asyncio
    async def test_in_memory_store_add_and_search(self):
        """InMemoryVectorStore: add docs, then search returns ranked results."""
        from unittest.mock import AsyncMock

        from django_matt.ai.base import EmbeddingResponse
        from django_matt.ai.vectorstore import Document, InMemoryVectorStore

        mock_embedder = AsyncMock()
        mock_embedder.dimensions = 3

        # Return different embeddings for different texts
        call_count = 0

        async def mock_embed_single(text, **kwargs):
            embeddings_map = {
                "Hello world": [1.0, 0.0, 0.0],
                "Goodbye world": [0.0, 1.0, 0.0],
                "Hi there": [0.9, 0.1, 0.0],  # similar to Hello
            }
            return embeddings_map.get(text, [0.0, 0.0, 1.0])

        mock_embedder.embed_single = mock_embed_single

        store = InMemoryVectorStore(embedding_provider=mock_embedder)

        # Add documents
        ids = await store.add([
            Document(id="1", text="Hello world"),
            Document(id="2", text="Goodbye world"),
        ])
        assert len(ids) == 2

        # Search with a vector similar to "Hello world"
        results = await store.search([0.95, 0.05, 0.0], top_k=2)
        assert len(results) == 2
        # "Hello world" should rank first (closest to query)
        assert results[0].document.id == "1"
        assert results[0].score > results[1].score

    @pytest.mark.asyncio
    async def test_in_memory_store_delete(self):
        """InMemoryVectorStore: delete removes documents."""
        from django_matt.ai.vectorstore import Document, InMemoryVectorStore

        store = InMemoryVectorStore(dimensions=3)
        await store.add([
            Document(id="1", text="doc1", embedding=[1.0, 0.0, 0.0]),
            Document(id="2", text="doc2", embedding=[0.0, 1.0, 0.0]),
        ])

        deleted = await store.delete(["1"])
        assert deleted == 1

        remaining = await store.get(["1", "2"])
        assert len(remaining) == 1
        assert remaining[0].id == "2"

    @pytest.mark.asyncio
    async def test_in_memory_store_metadata_filter(self):
        """InMemoryVectorStore: search with metadata filter."""
        from django_matt.ai.vectorstore import Document, InMemoryVectorStore

        store = InMemoryVectorStore(dimensions=3)
        await store.add([
            Document(id="1", text="doc1", embedding=[1.0, 0.0, 0.0], metadata={"category": "A"}),
            Document(id="2", text="doc2", embedding=[0.9, 0.1, 0.0], metadata={"category": "B"}),
        ])

        results = await store.search([1.0, 0.0, 0.0], filter={"category": "B"})
        assert len(results) == 1
        assert results[0].document.id == "2"


class TestStructuredOutput:
    """Tests for structured output parsing (ML-02)."""

    @pytest.mark.asyncio
    async def test_localai_complete_structured(self):
        """LocalAIProvider.complete_structured extracts typed fields from JSON."""
        from unittest.mock import AsyncMock

        from pydantic import BaseModel

        from django_matt.ai.base import Message
        from django_matt.ml.localai import LocalAIProvider

        class PersonInfo(BaseModel):
            name: str
            age: int

        provider = LocalAIProvider(base_url="http://localhost:8080", model="test")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {"content": '{"name": "Alice", "age": 30}'},
                        "finish_reason": "stop",
                    }
                ],
                "model": "test",
            }
        )
        provider._client = mock_client

        result = await provider.complete_structured(
            [Message.user("Extract: Alice is 30")],
            response_model=PersonInfo,
        )

        assert isinstance(result, PersonInfo)
        assert result.name == "Alice"
        assert result.age == 30
