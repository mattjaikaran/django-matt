"""CI/CD template generators for common platforms."""

from django_matt.deployment.ci_templates.github import generate_github_actions
from django_matt.deployment.ci_templates.gitlab import generate_gitlab_ci

__all__ = ["generate_github_actions", "generate_gitlab_ci"]
