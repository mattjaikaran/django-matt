# Contributing

Thank you for your interest in contributing to django-matt!

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/mattjaikaran/django-matt.git
   cd django-matt
   ```

2. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies**
   ```bash
   uv sync --dev
   ```

4. **Run tests**
   ```bash
   uv run pytest
   ```

5. **Run linting**
   ```bash
   uv run ruff check django_matt/
   uv run ruff format django_matt/
   ```

## Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

- Line length: 100 characters
- Quote style: Double quotes
- Import sorting: isort-compatible

## Testing

- Write tests for all new features
- Maintain or improve code coverage
- Use pytest fixtures and factories
- Test both sync and async code paths

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests and linting
5. Commit with a descriptive message
6. Push and create a pull request

## Commit Messages

Follow conventional commits:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `test:` Test changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](https://github.com/mattjaikaran/django-matt/blob/main/LICENSE).
