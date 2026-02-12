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
