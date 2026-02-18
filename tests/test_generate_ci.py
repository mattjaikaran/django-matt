"""Tests for CI/CD template generation."""

from io import StringIO

from django.core.management import call_command

from django_matt.deployment.ci_templates.github import generate_github_actions
from django_matt.deployment.ci_templates.gitlab import generate_gitlab_ci


class TestGitHubActions:
    def test_default_output(self):
        result = generate_github_actions()
        assert "name: CI" in result
        assert "uv sync --frozen" in result
        assert "uv run pytest" in result

    def test_includes_postgres(self):
        result = generate_github_actions(postgres=True)
        assert "postgres:16" in result
        assert "DATABASE_URL" in result

    def test_excludes_postgres(self):
        result = generate_github_actions(postgres=False)
        assert "postgres:16" not in result

    def test_includes_redis(self):
        result = generate_github_actions(redis=True)
        assert "redis:7" in result
        assert "REDIS_URL" in result

    def test_lint_step(self):
        result = generate_github_actions(lint=True)
        assert "ruff check" in result
        assert "ruff format" in result

    def test_no_lint(self):
        result = generate_github_actions(lint=False)
        assert "ruff check" not in result

    def test_coverage(self):
        result = generate_github_actions(coverage=True)
        assert "--cov" in result
        assert "codecov" in result

    def test_no_coverage(self):
        result = generate_github_actions(coverage=False)
        assert "codecov" not in result

    def test_python_version(self):
        result = generate_github_actions(python_version="3.11")
        assert "3.11" in result

    def test_fly_deploy(self):
        result = generate_github_actions(deploy_platform="fly")
        assert "flyctl deploy" in result
        assert "FLY_API_TOKEN" in result

    def test_railway_deploy(self):
        result = generate_github_actions(deploy_platform="railway")
        assert "RAILWAY_TOKEN" in result

    def test_render_deploy(self):
        result = generate_github_actions(deploy_platform="render")
        assert "RENDER_DEPLOY_HOOK_URL" in result

    def test_k8s_deploy(self):
        result = generate_github_actions(deploy_platform="k8s")
        assert "kubectl apply" in result

    def test_no_deploy(self):
        result = generate_github_actions(deploy_platform=None)
        # No deploy job should be present
        assert "flyctl" not in result
        assert "RAILWAY_TOKEN" not in result
        assert "RENDER_DEPLOY_HOOK_URL" not in result
        assert "kubectl apply" not in result

    def test_uses_uv_not_pip(self):
        result = generate_github_actions()
        assert "pip install" not in result
        assert "uv sync" in result


class TestGitLabCI:
    def test_default_output(self):
        result = generate_gitlab_ci()
        assert "stages:" in result
        assert "uv run pytest" in result

    def test_includes_postgres(self):
        result = generate_gitlab_ci(postgres=True)
        assert "postgres:16" in result

    def test_includes_redis(self):
        result = generate_gitlab_ci(redis=True)
        assert "redis:7" in result

    def test_lint_stage(self):
        result = generate_gitlab_ci(lint=True)
        assert "lint:" in result
        assert "ruff check" in result

    def test_no_lint(self):
        result = generate_gitlab_ci(lint=False)
        assert "ruff check" not in result

    def test_coverage_artifacts(self):
        result = generate_gitlab_ci(coverage=True)
        assert "coverage_report" in result or "coverage.xml" in result

    def test_fly_deploy(self):
        result = generate_gitlab_ci(deploy_platform="fly")
        assert "flyctl deploy" in result

    def test_k8s_deploy(self):
        result = generate_gitlab_ci(deploy_platform="k8s")
        assert "kubectl apply" in result


class TestGenerateCICommand:
    def test_command_dry_run(self):
        out = StringIO()
        call_command("generate_ci", "--dry-run", stdout=out)
        output = out.getvalue()
        assert "name: CI" in output

    def test_command_gitlab(self):
        out = StringIO()
        call_command("generate_ci", "--platform", "gitlab", "--dry-run", stdout=out)
        output = out.getvalue()
        assert "stages:" in output

    def test_command_with_deploy(self):
        out = StringIO()
        call_command("generate_ci", "--deploy", "fly", "--dry-run", stdout=out)
        output = out.getvalue()
        assert "flyctl" in output
