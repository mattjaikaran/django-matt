# Django Matt — Lessons Learned

## CLAUDE.md / Context Files

- **Keep CLAUDE.md under 150 lines.** Exhaustive API docs belong in `docs/`, not context files. The AI can read source files on demand.
- **macOS is case-insensitive for filenames.** `claude.md` and `CLAUDE.md` are the same file on disk. Use `git mv` to rename in git.

## CI/CD

- **Never use `continue-on-error: true` for linting or type-checking jobs.** It silently swallows real failures. Only use it for advisory checks (e.g., `uv pip audit` where the DB may lag).
- **Every tool referenced in CI must be in dev dependencies.** Pyright and twine were used but not installed — jobs passed but did nothing.
- **Keep version targets consistent.** If `requires-python = ">=3.12"`, all tool configs (ruff, pyright, mypy) must also target 3.12+.

## Dependencies

- **`django>=5.2.0` not `>=6.0.0`.** The CI tests against Django 5.2 and 6.0 both. The floor constraint must match the minimum tested version.
- **Drop Python 3.11 from test matrix** when `requires-python = ">=3.12"`.

## Testing

- **Security code (auth) is the highest-priority test target.** 14k LOC with zero tests is unacceptable for JWT, OAuth, SSO, and passkey implementations.
- **Revenue code (billing) is second priority.** Webhook signature verification, subscription state machines, and checkout flows need coverage.
- **Data isolation code (multitenancy) is third.** Tenant leaks are catastrophic and hard to detect without tests.
- **Async queryset mocks need real async generators.** `MagicMock().__aiter__` returning a regular iterator silently fails. Use a helper like `_make_qs(items)` that builds an object with `__aiter__` returning `async_generator(items)`.
- **Don't use `instance.__setattr__.call_args_list` on MagicMock.** It doesn't capture setattr calls. Use a real `FakeInstance` class with `__setattr__` recording to a dict, and pre-set attributes so `hasattr()` returns True.

## Services

- **PEP 695 type parameters avoid UP046 lint.** Use `class MyService[ModelT: models.Model]:` instead of `class MyService(Generic[ModelT]):` for Python 3.12+. The latter triggers `UP046` (use generic syntax).
- **Sync model methods need `sync_to_async` wrapping.** If a model has a `soft_delete()` sync method, call it as `await sync_to_async(instance.soft_delete)(user=user)` — not inside `async with transaction.atomic()` inline.
- **`get_active_queryset()` checks `hasattr(self.model, "is_active")` at call time.** The `is_active` attribute must exist on the model class itself (field descriptor), not just instances.

## Centrifugo

- **Centrifugo HTTP API v2 envelope format:** `POST /api` with body `{"method": "...", "params": {...}}` and header `Authorization: apikey <key>`.
- **Connection and subscription tokens** sign with `{"sub": user_id}` (connection) or `{"sub": user_id, "channel": channel}` using the Centrifugo HMAC secret — not the Django JWT secret.
- **Proxy views must be csrf_exempt** — Centrifugo POSTs without CSRF tokens; decorate or set `enforce_csrf_checks = False` on the class.
- **httpx as optional dep for centrifugo**: wrap import in `try/except ImportError` with install hint. Add as `[centrifugo]` optional extra in `pyproject.toml`.
