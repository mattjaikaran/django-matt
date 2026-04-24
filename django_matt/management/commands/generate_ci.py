"""Management command to generate CI/CD configuration files."""

import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Generate CI/CD pipeline configuration for GitHub Actions or GitLab CI."""

    help = "Generate CI/CD configuration for your project."

    def add_arguments(self, parser):
        parser.add_argument(
            "--platform",
            choices=["github", "gitlab"],
            default="github",
            help="CI platform (default: github)",
        )
        parser.add_argument(
            "--deploy",
            choices=["fly", "railway", "render", "k8s"],
            default=None,
            help="Deploy target (optional)",
        )
        parser.add_argument(
            "--python",
            default="3.12",
            help="Python version (default: 3.12)",
        )
        parser.add_argument(
            "--no-postgres",
            action="store_true",
            help="Exclude PostgreSQL service",
        )
        parser.add_argument(
            "--redis",
            action="store_true",
            help="Include Redis service",
        )
        parser.add_argument(
            "--no-lint",
            action="store_true",
            help="Exclude lint stage",
        )
        parser.add_argument(
            "--no-coverage",
            action="store_true",
            help="Exclude coverage reporting",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Output file path (default: auto-detect from platform)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print to stdout instead of writing to file",
        )

    def handle(self, *args, **options):
        """Generate CI/CD workflow files for the selected platform."""
        platform = options["platform"]
        deploy = options["deploy"]
        python_version = options["python"]
        postgres = not options["no_postgres"]
        redis = options["redis"]
        lint = not options["no_lint"]
        coverage = not options["no_coverage"]
        output = options["output"]
        dry_run = options["dry_run"]

        kwargs = {
            "python_version": python_version,
            "deploy_platform": deploy,
            "postgres": postgres,
            "redis": redis,
            "coverage": coverage,
            "lint": lint,
        }

        if platform == "github":
            from django_matt.deployment.ci_templates.github import generate_github_actions

            content = generate_github_actions(**kwargs)
            default_path = ".github/workflows/ci.yml"
        elif platform == "gitlab":
            from django_matt.deployment.ci_templates.gitlab import generate_gitlab_ci

            content = generate_gitlab_ci(**kwargs)
            default_path = ".gitlab-ci.yml"
        else:
            raise CommandError(f"Unknown platform: {platform}")

        if dry_run:
            self.stdout.write(content)
            return

        output_path = output or default_path
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(content)

        self.stdout.write(self.style.SUCCESS(f"Generated {output_path}"))
