"""GitLab CI/CD pipeline generator."""

from __future__ import annotations


def generate_gitlab_ci(
    *,
    python_version: str = "3.12",
    deploy_platform: str | None = None,
    postgres: bool = True,
    redis: bool = False,
    coverage: bool = True,
    lint: bool = True,
) -> str:
    """
    Generate a GitLab CI/CD pipeline YAML string.

    Args:
        python_version: Python version for the image tag.
        deploy_platform: Deploy target (fly, railway, render, k8s, or None).
        postgres: Include PostgreSQL service.
        redis: Include Redis service.
        coverage: Run pytest with --cov.
        lint: Include ruff lint stage.
    """
    stages = ["lint", "test"] if lint else ["test"]
    if deploy_platform:
        stages.append("deploy")

    stages_str = "\n".join(f"  - {s}" for s in stages)

    services = ""
    variables = ""
    if postgres:
        services += """
  services:
    - name: postgres:16
      alias: postgres"""
        variables += """
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: postgres
  POSTGRES_DB: test_db
  DATABASE_URL: postgres://postgres:postgres@postgres:5432/test_db"""

    if redis:
        if "services:" in services:
            services += """
    - name: redis:7
      alias: redis"""
        else:
            services += """
  services:
    - name: redis:7
      alias: redis"""
        variables += """
  REDIS_URL: redis://redis:6379/0"""

    variables_block = ""
    if variables:
        variables_block = f"""
variables:{variables}
"""

    # Lint job
    lint_job = ""
    if lint:
        lint_job = f"""
lint:
  stage: lint
  image: python:{python_version}-slim
  before_script:
    - pip install uv
    - uv sync --frozen
  script:
    - uv run ruff check .
    - uv run ruff format --check .
"""

    # Test job
    pytest_cmd = "uv run pytest --cov --cov-report=xml" if coverage else "uv run pytest"
    test_job = f"""
test:
  stage: test
  image: python:{python_version}-slim{services}
  before_script:
    - pip install uv
    - uv sync --frozen
  script:
    - {pytest_cmd}"""

    if coverage:
        test_job += """
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml"""

    test_job += "\n"

    # Deploy job
    deploy_job = ""
    if deploy_platform:
        deploy_job = _gitlab_deploy_job(deploy_platform)

    return f"""stages:
{stages_str}
{variables_block}{lint_job}{test_job}{deploy_job}"""


def _gitlab_deploy_job(platform: str) -> str:
    """Generate deploy job for GitLab CI."""
    if platform == "fly":
        return """
deploy:
  stage: deploy
  image: flyio/flyctl
  script:
    - flyctl deploy --remote-only
  only:
    - main
"""
    if platform == "k8s":
        return """
deploy:
  stage: deploy
  image: bitnami/kubectl
  script:
    - kubectl apply -f k8s/
  only:
    - main
"""
    return ""
