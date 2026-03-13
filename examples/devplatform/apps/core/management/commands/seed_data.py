import secrets
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.gateway.models import RequestLog
from apps.keys.models import APIKey
from apps.organizations.models import Membership, MembershipRole, Organization, Team
from apps.projects.models import Project
from apps.users.models import User
from apps.webhooks.models import Webhook


class Command(BaseCommand):
    help = "Seed the database with sample data"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing data first")

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            RequestLog.objects.all().delete()
            Webhook.objects.all().delete()
            APIKey.objects.all().delete()
            Project.objects.all().delete()
            Team.objects.all().delete()
            Membership.objects.all().delete()
            Organization.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        # Admin
        admin, _ = User.objects.get_or_create(
            email="admin@example.com",
            defaults={
                "username": "admin",
                "password": make_password("admin123"),
                "is_staff": True,
                "is_superuser": True,
            },
        )

        # Users
        alice, _ = User.objects.get_or_create(
            email="alice@example.com",
            defaults={"username": "alice", "password": make_password("password123")},
        )
        bob, _ = User.objects.get_or_create(
            email="bob@example.com",
            defaults={"username": "bob", "password": make_password("password123")},
        )

        # Organization
        org, _ = Organization.objects.get_or_create(
            slug="acme-dev",
            defaults={"name": "Acme Dev", "description": "Developer platform demo"},
        )

        for user, role in [
            (admin, MembershipRole.OWNER),
            (alice, MembershipRole.ADMIN),
            (bob, MembershipRole.MEMBER),
        ]:
            Membership.objects.get_or_create(
                user=user, organization=org, defaults={"role": role.value}
            )

        # Projects
        prod_project, _ = Project.objects.get_or_create(
            organization=org,
            slug="main-api",
            defaults={
                "name": "Main API",
                "environment": "production",
            },
        )
        staging_project, _ = Project.objects.get_or_create(
            organization=org,
            slug="staging-api",
            defaults={
                "name": "Staging API",
                "environment": "staging",
            },
        )

        # API Keys
        for project, name in [
            (prod_project, "Production Key"),
            (staging_project, "Staging Key"),
        ]:
            import hashlib

            full_key = "sk_live_" + secrets.token_hex(24)
            APIKey.objects.get_or_create(
                project=project,
                name=name,
                defaults={
                    "key_prefix": full_key[:12],
                    "key_hash": hashlib.sha256(full_key.encode()).hexdigest(),
                    "scopes": ["read", "write"],
                    "created_by": admin,
                },
            )

        # Webhooks
        Webhook.objects.get_or_create(
            project=prod_project,
            url="https://example.com/webhook",
            defaults={
                "secret": secrets.token_hex(32),
                "events": ["request.completed", "error.occurred"],
            },
        )

        # Sample request logs
        now = timezone.now()
        paths = ["/api/users", "/api/products", "/api/orders", "/api/health"]
        methods = ["GET", "POST", "PUT", "DELETE"]
        for i in range(50):
            RequestLog.objects.get_or_create(
                project=prod_project,
                method=methods[i % 4],
                path=paths[i % 4],
                status_code=200 if i % 7 != 0 else 500,
                response_time_ms=20 + (i * 3) % 200,
                defaults={"created_at": now - timedelta(hours=i)},
            )

        self.stdout.write(self.style.SUCCESS("Seed data created!"))
        self.stdout.write(f"  Users: {User.objects.count()}")
        self.stdout.write(f"  Projects: {Project.objects.count()}")
        self.stdout.write(f"  API Keys: {APIKey.objects.count()}")
        self.stdout.write(f"  Request Logs: {RequestLog.objects.count()}")
