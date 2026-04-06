# AI Context Documentation

This directory contains documentation specifically designed for AI models (Claude, GPT, Cursor, etc.) to have complete context when working with django-matt projects.

## How to Use

Include these files in your AI model's context when:
- Starting a new project with django-matt
- Adding features to an existing django-matt project
- Debugging django-matt code
- Generating boilerplate code

### For Any LLM (Claude, GPT, Gemini, etc.)

Paste `LLM-SYSTEM-PROMPT.md` into the system prompt. This is the single canonical reference — it contains everything an LLM needs to generate correct django-matt code.

For code generation tasks, also include `CODEGEN-RECIPES.md` for step-by-step patterns.

### For Claude Code / CLAUDE.md

Add this to your project's `CLAUDE.md`:

```markdown
## Framework Reference
- LLM system prompt: docs/ai-context/LLM-SYSTEM-PROMPT.md
- Architecture: docs/ai-context/ARCHITECTURE.md
- Correct patterns: docs/ai-context/PATTERNS.md
- Common mistakes: docs/ai-context/ANTI-PATTERNS.md
- Code generation recipes: docs/ai-context/CODEGEN-RECIPES.md
- Quick reference: docs/ai-context/QUICK-REFERENCE.md
```

### For Cursor / .cursorrules

Reference these files in your `.cursorrules`:

```
When working with django-matt, always reference:
@docs/ai-context/LLM-SYSTEM-PROMPT.md for the canonical framework reference
@docs/ai-context/CODEGEN-RECIPES.md for code generation patterns
@docs/ai-context/ANTI-PATTERNS.md for common mistakes to avoid
```

### Auto-Generation

Generate project-specific LLM prompts from live introspection:

```bash
# Generate all context files (including LLM-PROMPT.md)
python manage.py generate_ai_context --format all

# Generate only the LLM system prompt
python manage.py generate_ai_context --format llm

# Watch mode — auto-regenerate on file changes
python manage.py generate_ai_context --watch
```

Or programmatically:

```python
from django_matt.ai.context import LlmPromptGenerator, ContextGenerator

# Single format
generator = LlmPromptGenerator()
prompt = generator.generate()
generator.write("LLM-PROMPT.md")

# All formats at once
ctx = ContextGenerator()
files = ctx.generate_all()  # CLAUDE.md, .cursorrules, .copilot-instructions, introspection.json, LLM-PROMPT.md
```

## Files

| File | Purpose | When to Use |
|------|---------|-------------|
| `LLM-SYSTEM-PROMPT.md` | **Canonical LLM system prompt** — all core truths, patterns, imports, anti-patterns | **Always** — paste into any LLM before generating django-matt code |
| `CODEGEN-RECIPES.md` | Step-by-step recipes for common tasks (CRUD, auth, AI endpoints, RAG, etc.) | Code generation — building new features |
| `ARCHITECTURE.md` | Framework overview, module map, how it works | Starting a new project, understanding the framework |
| `PATTERNS.md` | Correct code patterns with examples | Writing new controllers, views, schemas, auth |
| `ANTI-PATTERNS.md` | Common mistakes and what NOT to do | Before generating any django-matt code |
| `QUICK-REFERENCE.md` | Cheat sheet: imports, settings, CLI | Quick lookups during development |

## Key Facts for AI Models

1. **orjson is always available** — it's a base dependency, import directly
2. **register_controller() takes ONE argument** — the class, no prefix
3. **Async-first** — use async ORM methods (`.aget()`, `.acreate()`, etc.)
4. **QuerySets are NOT awaitable** — use `[x async for x in qs]`
5. **Built-in JWT** — no PyJWT dependency needed
6. **Use uv, not pip** — `uv add django-matt`
7. **Pydantic v2, not DRF** — ModelSchema, not ModelSerializer
8. **Interceptors, not middleware** — for route-scoped concerns, use `@intercept()` instead of global middleware
9. **SSE streaming** — use `sse_response()` from `django_matt.streaming` for Server-Sent Events
10. **Event bus** — `get_event_bus().emit()` for fire-and-forget; `@on()` to subscribe
11. **CQRS** — `Command`/`Query` are frozen Pydantic models; dispatch via `get_command_bus()`/`get_query_bus()`
12. **Serialization groups** — use `Grouped()`, `Secret()` field markers + `@serialize_for()` for role-based APIs
13. **Exception filters** — use `ExceptionFilter` + `register_global_filter()` instead of try/except in controllers
14. **Slim mode** — configure `DJANGO_MATT["SLIM_MODE"]` to control which modules load
