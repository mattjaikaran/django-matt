# Contributing to django-matt

Thanks for your interest in contributing to django-matt! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Git

### Getting Started

```bash
# Clone the repo
git clone https://github.com/mattjaikaran/django-matt.git
cd django-matt

# Install dependencies
uv sync --group dev

# Run tests
uv run pytest tests/ -x -q

# Run linter
uv run ruff check django_matt/

# Run formatter
uv run ruff format django_matt/
```

## Development Workflow

1. **Fork and clone** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** — follow the code style below
4. **Write tests** for new functionality
5. **Run the test suite** to confirm nothing is broken:
   ```bash
   uv run pytest tests/ -x -q
   ```
6. **Lint your code**:
   ```bash
   uv run ruff check django_matt/ --fix
   uv run ruff format django_matt/
   ```
7. **Commit** with a clear message (imperative mood, lowercase, no period):
   ```bash
   git commit -m "feat: add support for custom middleware chains"
   ```
8. **Push** and open a Pull Request

## Code Style

### Python

- **Formatter/Linter**: ruff (line-length 100, target py312)
- **Type hints** on every function signature: `str | None`, `dict[str, Any]`, `list[UUID]`
- **Async/await** for all IO-bound operations
- **Imports**: stdlib → Django → third-party → local, sorted by ruff

### Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new feature
- `fix:` — bug fix
- `refactor:` — code change that neither fixes a bug nor adds a feature
- `docs:` — documentation only
- `test:` — adding or updating tests
- `chore:` — maintenance tasks

## Testing

- **Framework**: pytest with pytest-asyncio
- **Async tests** are the default (`asyncio_mode = "auto"`)
- Write tests that test **behavior**, not implementation details
- Integration tests hit real DB — no mocking the database
- Every bug fix gets a regression test

```bash
# Run all tests
uv run pytest tests/ -x -q

# Run specific test file
uv run pytest tests/test_auth.py -v

# Run with coverage
uv run pytest tests/ --cov=django_matt
```

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include tests for new functionality
- Update docs if you're changing public API
- All CI checks must pass before merge
- Link related issues in the PR description

## Reporting Bugs

Use the [Bug Report template](https://github.com/mattjaikaran/django-matt/issues/new?template=bug_report.md) and include:

- django-matt version
- Python and Django versions
- Steps to reproduce
- Expected vs actual behavior
- Error traceback (if applicable)

## Requesting Features

Use the [Feature Request template](https://github.com/mattjaikaran/django-matt/issues/new?template=feature_request.md) and include:

- Problem you're trying to solve
- Proposed solution
- Alternatives you've considered

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
