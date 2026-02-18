"""GitHub Actions CI/CD workflow generator."""

from __future__ import annotations


def generate_github_actions(
    *,
    python_version: str = "3.12",
    deploy_platform: str | None = None,
    postgres: bool = True,
    redis: bool = False,
    coverage: bool = True,
    lint: bool = True,
) -> str:
    """
    Generate a GitHub Actions CI/CD workflow YAML string.

    Args:
        python_version: Python version for the matrix.
        deploy_platform: Deploy target (fly, railway, render, k8s, or None).
        postgres: Include PostgreSQL service container.
        redis: Include Redis service container.
        coverage: Run pytest with --cov.
        lint: Include a ruff lint step.
    """
    services = ""
    env_block = ""

    if postgres:
        services += """
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5"""
        env_block += """
        DATABASE_URL: postgres://postgres:postgres@localhost:5432/test_db"""

    if redis:
        services += """
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5"""
        env_block += """
        REDIS_URL: redis://localhost:6379/0"""

    services_block = ""
    if services:
        services_block = f"""
    services:{services}"""

    # Lint job
    lint_job = ""
    if lint:
        lint_job = f"""
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install {python_version}
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
"""

    # Test job
    test_needs = '    needs: [lint]\n' if lint else ''
    pytest_cmd = "uv run pytest --cov --cov-report=xml" if coverage else "uv run pytest"
    env_section = f"""
      env:{env_block}""" if env_block else ""

    test_job = f"""
  test:
    runs-on: ubuntu-latest
{test_needs}{services_block}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install {python_version}
      - run: uv sync --frozen{env_section}
      - run: {pytest_cmd}"""

    if coverage:
        test_job += """
      - uses: codecov/codecov-action@v4
        if: always()
        with:
          file: ./coverage.xml"""

    test_job += "\n"

    # Deploy job
    deploy_job = ""
    if deploy_platform:
        deploy_job = _deploy_job(deploy_platform)

    return f"""name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
{lint_job}{test_job}{deploy_job}"""


def _deploy_job(platform: str) -> str:
    """Generate deploy job for a given platform."""
    if platform == "fly":
        return """
  deploy:
    runs-on: ubuntu-latest
    needs: [test]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
"""
    if platform == "railway":
        return """
  deploy:
    runs-on: ubuntu-latest
    needs: [test]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - uses: railwayapp/cli-action@v1
        with:
          token: ${{ secrets.RAILWAY_TOKEN }}
          command: up
"""
    if platform == "render":
        return """
  deploy:
    runs-on: ubuntu-latest
    needs: [test]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - name: Trigger Render deploy
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
"""
    if platform == "k8s":
        return """
  deploy:
    runs-on: ubuntu-latest
    needs: [test]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - uses: azure/setup-kubectl@v3
      - run: kubectl apply -f k8s/
        env:
          KUBECONFIG: ${{ secrets.KUBECONFIG }}
"""
    return ""
