# AI Context Documentation

This directory contains documentation specifically designed for AI models (Claude, GPT, Cursor, etc.) to have complete context when working with django-matt projects.

## How to Use

Include these files in your AI model's context when:
- Starting a new project with django-matt
- Adding features to an existing django-matt project
- Debugging django-matt code
- Generating boilerplate code

### For Claude Code / CLAUDE.md

Add this to your project's `CLAUDE.md`:

```markdown
## Framework Reference
- Architecture: docs/ai-context/ARCHITECTURE.md
- Correct patterns: docs/ai-context/PATTERNS.md
- Common mistakes: docs/ai-context/ANTI-PATTERNS.md
- Quick reference: docs/ai-context/QUICK-REFERENCE.md
- Full examples: docs/ai-context/EXAMPLES.md
```

### For Cursor / .cursorrules

Reference these files in your `.cursorrules`:

```
When working with django-matt, always reference:
@docs/ai-context/ARCHITECTURE.md for how the framework works
@docs/ai-context/PATTERNS.md for correct code patterns
@docs/ai-context/ANTI-PATTERNS.md for common mistakes to avoid
```

## Files

| File | Purpose | When to Use |
|------|---------|-------------|
| `ARCHITECTURE.md` | Framework overview, module map, how it works | Starting a new project, understanding the framework |
| `PATTERNS.md` | Correct code patterns with examples | Writing new controllers, views, schemas, auth |
| `ANTI-PATTERNS.md` | Common mistakes and what NOT to do | Before generating any django-matt code |
| `QUICK-REFERENCE.md` | Cheat sheet: imports, settings, CLI | Quick lookups during development |
| `EXAMPLES.md` | Complete project examples | Building new features, scaffolding projects |

## Key Facts for AI Models

1. **orjson is always available** — it's a base dependency, import directly
2. **register_controller() takes ONE argument** — the class, no prefix
3. **Async-first** — use async ORM methods (`.aget()`, `.acreate()`, etc.)
4. **QuerySets are NOT awaitable** — use `[x async for x in qs]`
5. **Built-in JWT** — no PyJWT dependency needed
6. **Use uv, not pip** — `uv add django-matt`
7. **Pydantic v2, not DRF** — ModelSchema, not ModelSerializer
