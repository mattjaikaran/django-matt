"""
Seed data management command.

Creates sample data for development and testing.

Usage:
    python manage.py seed_data                  # Basic seed data
    python manage.py seed_data --full           # Full dataset
    python manage.py seed_data --clear          # Clear and reseed
    python manage.py seed_data --users=10       # Custom user count
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
import secrets


class Command(BaseCommand):
    help = "Seed database with sample data for development"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before seeding",
        )
        parser.add_argument(
            "--full",
            action="store_true",
            help="Create full dataset with more data",
        )
        parser.add_argument(
            "--users",
            type=int,
            default=5,
            help="Number of users to create (default: 5)",
        )
        parser.add_argument(
            "--orgs",
            type=int,
            default=1,
            help="Number of organizations to create (default: 1)",
        )
        parser.add_argument(
            "--projects",
            type=int,
            default=3,
            help="Number of projects per org (default: 3)",
        )
        parser.add_argument(
            "--tasks",
            type=int,
            default=20,
            help="Number of tasks per project (default: 20)",
        )
        parser.add_argument(
            "--features",
            action="store_true",
            help="Create sample feature flags",
        )

    def handle(self, *args, **options):
        from core.models import User, Organization, Team, Membership, MembershipRole, AuditLog
        from projects.models import (
            Project, Task, TaskStatus, TaskPriority, Comment, Label, ProjectMember, TaskActivity
        )
        from billing.models import Subscription, SubscriptionStatus, Invoice, InvoiceStatus, Coupon
        from notifications.models import (
            Notification, NotificationType, NotificationPreference, AnalyticsEvent
        )

        # Increase counts for full mode
        if options["full"]:
            options["users"] = max(options["users"], 20)
            options["orgs"] = max(options["orgs"], 3)
            options["projects"] = max(options["projects"], 10)
            options["tasks"] = max(options["tasks"], 50)
            options["features"] = True

        self.stdout.write(self.style.HTTP_INFO("Starting database seeding..."))

        if options["clear"]:
            self.clear_data()

        # Create admin user
        admin_user = self.create_admin_user()

        # Create demo users
        demo_users = self.create_demo_users(admin_user, options["users"])

        # Create organizations
        organizations = self.create_organizations(
            admin_user, demo_users, options["orgs"]
        )

        # Create projects, tasks, and comments for each org
        for org in organizations:
            org_users = list(org.memberships.values_list("user", flat=True))
            org_user_objects = [u for u in demo_users if u.id in org_users]

            labels = self.create_labels(org)
            projects = self.create_projects(
                org, org_user_objects, options["projects"]
            )

            for project in projects:
                self.create_tasks(
                    project, org_user_objects, labels, options["tasks"]
                )

            # Create subscription and billing data
            self.create_subscription(org)
            self.create_invoices(org)

            # Create notifications
            self.create_notifications(org, org_user_objects)

            # Create audit logs
            self.create_audit_logs(org, org_user_objects)

        # Create feature flags
        if options["features"]:
            self.create_feature_flags()

        # Create analytics events
        self.create_analytics_events(demo_users, organizations)

        # Create coupons
        self.create_coupons()

        self.print_summary(admin_user, demo_users, organizations)

    def clear_data(self):
        """Clear all seeded data."""
        from core.models import User, Organization, Team, Membership, AuditLog
        from projects.models import Project, Task, Comment, Label, TaskActivity, ProjectMember
        from billing.models import Subscription, Invoice, PaymentMethod, Coupon, CouponRedemption
        from notifications.models import Notification, NotificationPreference, AnalyticsEvent

        self.stdout.write("Clearing existing data...")

        # Clear in reverse order of dependencies
        AnalyticsEvent.objects.all().delete()
        Notification.objects.all().delete()
        NotificationPreference.objects.all().delete()
        CouponRedemption.objects.all().delete()
        Coupon.objects.all().delete()
        Invoice.objects.all().delete()
        PaymentMethod.objects.all().delete()
        Subscription.objects.all().delete()
        TaskActivity.objects.all().delete()
        Comment.objects.all().delete()
        Task.objects.all().delete()
        ProjectMember.objects.all().delete()
        Project.objects.all().delete()
        Label.objects.all().delete()
        AuditLog.objects.all().delete()
        Team.objects.all().delete()
        Membership.objects.all().delete()
        Organization.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

        self.stdout.write(self.style.SUCCESS("Data cleared!"))

    def create_admin_user(self):
        """Create admin user."""
        from core.models import User

        admin_user, created = User.objects.get_or_create(
            email="admin@saas-starter.local",
            defaults={
                "first_name": "Admin",
                "last_name": "User",
                "is_staff": True,
                "is_superuser": True,
                "is_verified": True,
            },
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Created admin user: admin@saas-starter.local / admin123"
            ))
        return admin_user

    def create_demo_users(self, admin_user, count):
        """Create demo users."""
        from core.models import User
        from notifications.models import NotificationPreference

        demo_users = [admin_user]
        first_names = [
            "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry",
            "Ivy", "Jack", "Kate", "Leo", "Mia", "Noah", "Olivia", "Paul",
            "Quinn", "Rose", "Sam", "Tara"
        ]
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
            "Davis", "Martinez", "Wilson", "Anderson", "Taylor", "Thomas", "Moore"
        ]
        timezones = ["America/New_York", "America/Los_Angeles", "Europe/London", "Asia/Tokyo", "UTC"]

        for i in range(count):
            first_name = first_names[i % len(first_names)]
            last_name = last_names[i % len(last_names)]
            email = f"{first_name.lower()}.{last_name.lower()}{i}@demo.local"

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_verified": True,
                    "timezone": random.choice(timezones),
                    "notification_preferences": {
                        "email_digest": random.choice(["instant", "daily", "weekly"]),
                    },
                },
            )
            if created:
                user.set_password("demo123")
                user.save()
                self.stdout.write(f"Created user: {email}")

                # Create notification preferences
                NotificationPreference.objects.get_or_create(
                    user=user,
                    defaults={
                        "email_enabled": True,
                        "push_enabled": random.choice([True, False]),
                        "in_app_enabled": True,
                    }
                )

            demo_users.append(user)

        return demo_users

    def create_organizations(self, admin_user, demo_users, count):
        """Create organizations with teams and memberships."""
        from core.models import Organization, Team, Membership, MembershipRole

        organizations = []
        org_data = [
            ("Demo Company", "demo-company", "A demo organization for testing", "pro"),
            ("Startup Inc", "startup-inc", "Fast-moving startup team", "free"),
            ("Enterprise Corp", "enterprise-corp", "Large enterprise organization", "enterprise"),
        ]

        for i in range(min(count, len(org_data))):
            name, slug, description, plan = org_data[i]

            org, created = Organization.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "owner": admin_user,
                    "plan": plan,
                    "plan_limits": settings.BILLING_PRODUCTS.get(plan, {}).get("limits", {}),
                    "description": description,
                    "settings": {
                        "default_project_visibility": "team",
                        "require_2fa": plan == "enterprise",
                    },
                },
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created organization: {org.name}"))

                # Create teams
                teams = self.create_teams(org)

                # Create memberships
                self.create_memberships(org, admin_user, demo_users, teams)

            organizations.append(org)

        return organizations

    def create_teams(self, org):
        """Create teams for an organization."""
        from core.models import Team

        teams_data = [
            ("Engineering", "engineering", "Software development team"),
            ("Design", "design", "UI/UX design team"),
            ("Marketing", "marketing", "Marketing and growth team"),
            ("Product", "product", "Product management team"),
            ("Support", "support", "Customer support team"),
        ]

        teams = []
        for name, slug, description in teams_data:
            team, _ = Team.objects.get_or_create(
                organization=org,
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                },
            )
            teams.append(team)

        return teams

    def create_memberships(self, org, admin_user, demo_users, teams):
        """Create memberships for users in an organization."""
        from core.models import Membership, MembershipRole

        roles = [MembershipRole.ADMIN, MembershipRole.MEMBER, MembershipRole.MEMBER, MembershipRole.VIEWER]

        # Add admin as owner
        owner_membership, _ = Membership.objects.get_or_create(
            user=admin_user,
            organization=org,
            defaults={
                "role": MembershipRole.OWNER,
                "accepted_at": timezone.now(),
            },
        )
        for team in teams:
            owner_membership.teams.add(team)

        # Add other users with random roles and teams
        for user in demo_users:
            if user == admin_user:
                continue

            if random.random() > 0.3:  # 70% chance to be in this org
                role = random.choice(roles)
                membership, created = Membership.objects.get_or_create(
                    user=user,
                    organization=org,
                    defaults={
                        "role": role,
                        "invited_by": admin_user,
                        "invited_at": timezone.now() - timedelta(days=random.randint(1, 30)),
                        "accepted_at": timezone.now() - timedelta(days=random.randint(0, 29)),
                    },
                )
                if created:
                    # Add to random teams
                    for team in random.sample(teams, k=random.randint(1, 3)):
                        membership.teams.add(team)

    def create_labels(self, org):
        """Create labels for an organization."""
        from projects.models import Label

        labels_data = [
            ("bug", "#EF4444", "Bug or defect"),
            ("feature", "#3B82F6", "New feature request"),
            ("enhancement", "#8B5CF6", "Enhancement to existing feature"),
            ("documentation", "#10B981", "Documentation update"),
            ("urgent", "#F59E0B", "Urgent priority"),
            ("blocked", "#6B7280", "Blocked by dependency"),
            ("design", "#EC4899", "Design work required"),
            ("backend", "#14B8A6", "Backend development"),
            ("frontend", "#6366F1", "Frontend development"),
            ("testing", "#84CC16", "Testing required"),
        ]

        labels = []
        for name, color, description in labels_data:
            label, _ = Label.objects.get_or_create(
                organization=org,
                name=name,
                defaults={
                    "color": color,
                    "description": description,
                },
            )
            labels.append(label)

        return labels

    def create_projects(self, org, users, count):
        """Create projects for an organization."""
        from projects.models import Project, ProjectStatus, ProjectMember

        projects_data = [
            ("Website Redesign", "website-redesign", "Redesign the company website with modern UI", "#3B82F6"),
            ("Mobile App", "mobile-app", "Native mobile application for iOS and Android", "#EF4444"),
            ("API Platform", "api-platform", "Build the new API platform", "#10B981"),
            ("Marketing Campaign", "marketing-q1", "Q1 Marketing initiatives", "#F59E0B"),
            ("Internal Tools", "internal-tools", "Developer productivity tools", "#8B5CF6"),
            ("Customer Portal", "customer-portal", "Self-service customer portal", "#EC4899"),
            ("Analytics Dashboard", "analytics", "Real-time analytics dashboard", "#14B8A6"),
            ("Payment Integration", "payments", "Payment gateway integration", "#6366F1"),
            ("Documentation Site", "docs-site", "Public documentation website", "#84CC16"),
            ("Security Audit", "security-audit", "Q1 security compliance audit", "#F97316"),
        ]

        projects = []
        statuses = list(ProjectStatus.values)

        for name, slug, description, color in projects_data[:count]:
            owner = random.choice(users) if users else org.owner

            project, created = Project.objects.get_or_create(
                organization=org,
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "owner": owner,
                    "color": color,
                    "status": random.choice(statuses),
                    "start_date": timezone.now().date() - timedelta(days=random.randint(0, 30)),
                    "due_date": timezone.now().date() + timedelta(days=random.randint(30, 90)),
                    "settings": {
                        "enable_time_tracking": random.choice([True, False]),
                        "default_assignee": None,
                    },
                },
            )

            if created:
                self.stdout.write(f"Created project: {project.name}")

                # Add project members
                for user in random.sample(users, k=min(5, len(users))):
                    role = "owner" if user == owner else random.choice(["editor", "viewer"])
                    ProjectMember.objects.get_or_create(
                        project=project,
                        user=user,
                        defaults={"role": role},
                    )

            projects.append(project)

        return projects

    def create_tasks(self, project, users, labels, count):
        """Create tasks for a project."""
        from projects.models import Task, TaskStatus, TaskPriority, Comment, TaskActivity

        task_titles = [
            "Set up development environment",
            "Design database schema",
            "Implement user authentication",
            "Create API endpoints",
            "Build frontend components",
            "Write unit tests",
            "Set up CI/CD pipeline",
            "Design landing page",
            "Implement payment integration",
            "Create admin dashboard",
            "Write documentation",
            "Performance optimization",
            "Security audit",
            "User testing",
            "Bug fixes for login flow",
            "Code review process",
            "Deploy to staging",
            "Create onboarding flow",
            "Implement search feature",
            "Add export functionality",
            "Mobile responsive design",
            "API rate limiting",
            "Error handling improvements",
            "Logging and monitoring",
            "Database optimization",
            "Cache implementation",
            "WebSocket integration",
            "Email notifications",
            "File upload feature",
            "User profile page",
            "Settings page",
            "Billing integration",
            "Webhook handlers",
            "API documentation",
            "Load testing",
            "Accessibility audit",
            "SEO optimization",
            "Analytics integration",
            "Feature flag system",
            "A/B testing setup",
            "Localization support",
            "Dark mode implementation",
            "Keyboard shortcuts",
            "Drag and drop functionality",
            "Real-time collaboration",
            "Comment system",
            "Mention notifications",
            "Activity feed",
            "Dashboard widgets",
            "Custom report builder",
        ]

        statuses = list(TaskStatus.values)
        priorities = list(TaskPriority.values)
        label_names = [l.name for l in labels]

        for i, title in enumerate(task_titles[:count]):
            status = random.choice(statuses)
            assignee = random.choice(users) if users and random.random() > 0.2 else None
            reporter = random.choice(users) if users else project.owner

            task, created = Task.objects.get_or_create(
                project=project,
                title=title,
                defaults={
                    "description": f"Detailed description for task: {title}\n\n"
                                   f"This task involves implementing {title.lower()} "
                                   f"for the {project.name} project.",
                    "assignee": assignee,
                    "reporter": reporter,
                    "status": status,
                    "priority": random.choice(priorities),
                    "position": i,
                    "labels": random.sample(label_names, k=random.randint(0, 3)),
                    "estimated_hours": random.choice([1, 2, 4, 8, 16, 24, 40]) if random.random() > 0.3 else None,
                    "actual_hours": random.choice([1, 2, 3, 5, 8, 12, 20]) if status == TaskStatus.DONE else None,
                    "due_date": (
                        timezone.now() + timedelta(days=random.randint(-5, 30))
                    ).date() if random.random() > 0.3 else None,
                    "completed_at": timezone.now() - timedelta(days=random.randint(0, 10)) if status == TaskStatus.DONE else None,
                    "custom_fields": {
                        "sprint": f"Sprint {random.randint(1, 10)}",
                        "story_points": random.choice([1, 2, 3, 5, 8, 13]),
                    },
                },
            )

            if created:
                # Add comments
                if random.random() > 0.5:
                    self.create_comments(task, users)

                # Add activity log
                if random.random() > 0.6:
                    self.create_task_activity(task, users)

    def create_comments(self, task, users):
        """Create comments for a task."""
        from projects.models import Comment

        comments_content = [
            "This looks good! Let's move forward with this approach.",
            "I have some concerns about the implementation. Can we discuss?",
            "LGTM! Ship it! :rocket:",
            "Could you add more tests for edge cases?",
            "I've updated the PR with the requested changes.",
            "This is blocked by the API changes. Waiting on backend team.",
            "Great progress! Just a few minor tweaks needed.",
            "@alice Can you review this when you have a chance?",
            "Fixed the bug. Ready for another review.",
            "This might impact performance. Let's run some benchmarks.",
        ]

        for _ in range(random.randint(1, 4)):
            author = random.choice(users) if users else task.reporter
            Comment.objects.create(
                task=task,
                author=author,
                content=random.choice(comments_content),
                reactions={"thumbs_up": [], "heart": []} if random.random() > 0.7 else {},
            )

    def create_task_activity(self, task, users):
        """Create activity log entries for a task."""
        from projects.models import TaskActivity, TaskStatus

        activities = [
            ("created", None, None, None),
            ("status_changed", "status", "todo", "in_progress"),
            ("assigned", "assignee", None, str(random.choice(users).id) if users else None),
            ("priority_changed", "priority", "medium", "high"),
            ("commented", None, None, None),
        ]

        for action, field, old_val, new_val in random.sample(activities, k=random.randint(1, 3)):
            TaskActivity.objects.create(
                task=task,
                user=random.choice(users) if users else task.reporter,
                action=action,
                field=field or "",
                old_value=old_val,
                new_value=new_val,
            )

    def create_subscription(self, org):
        """Create subscription for an organization."""
        from billing.models import Subscription, SubscriptionStatus

        plan_map = {
            "free": ("Free", 0),
            "pro": ("Pro", 1),
            "enterprise": ("Enterprise", 1),
        }

        plan_name, quantity = plan_map.get(org.plan, ("Free", 0))

        Subscription.objects.get_or_create(
            organization=org,
            defaults={
                "stripe_subscription_id": f"sub_{secrets.token_hex(12)}",
                "stripe_price_id": f"price_{secrets.token_hex(12)}",
                "stripe_product_id": f"prod_{secrets.token_hex(12)}",
                "plan_name": plan_name,
                "plan_interval": random.choice(["month", "year"]),
                "status": SubscriptionStatus.ACTIVE if org.plan != "free" else SubscriptionStatus.TRIALING,
                "current_period_start": timezone.now() - timedelta(days=15),
                "current_period_end": timezone.now() + timedelta(days=15),
                "quantity": org.memberships.count() if quantity else 1,
            },
        )

    def create_invoices(self, org):
        """Create sample invoices for an organization."""
        from billing.models import Invoice, InvoiceStatus

        if org.plan == "free":
            return

        for i in range(3):
            month_offset = i + 1
            Invoice.objects.get_or_create(
                organization=org,
                stripe_invoice_id=f"inv_{secrets.token_hex(12)}",
                defaults={
                    "number": f"INV-{org.slug.upper()}-{2024}{month_offset:02d}",
                    "status": InvoiceStatus.PAID,
                    "subtotal": random.choice([2900, 4900, 9900]),
                    "tax": 0,
                    "total": random.choice([2900, 4900, 9900]),
                    "amount_paid": random.choice([2900, 4900, 9900]),
                    "amount_due": 0,
                    "invoice_date": timezone.now() - timedelta(days=30 * month_offset),
                    "paid_at": timezone.now() - timedelta(days=30 * month_offset - 2),
                    "line_items": [
                        {
                            "description": f"{org.plan.title()} Plan",
                            "quantity": org.memberships.count(),
                            "unit_amount": 2900 if org.plan == "pro" else 9900,
                        }
                    ],
                },
            )

    def create_notifications(self, org, users):
        """Create sample notifications."""
        from notifications.models import Notification, NotificationType

        notification_types = [
            (NotificationType.TASK_ASSIGNED, "New task assigned", "You have been assigned to a new task"),
            (NotificationType.TASK_COMMENTED, "New comment", "Someone commented on your task"),
            (NotificationType.PROJECT_MEMBER_ADDED, "Added to project", "You've been added to a project"),
            (NotificationType.ORG_MEMBER_JOINED, "New team member", "A new member joined your organization"),
        ]

        for user in users[:5]:
            for notification_type, title, message in random.sample(notification_types, k=2):
                Notification.objects.get_or_create(
                    user=user,
                    organization=org,
                    type=notification_type,
                    defaults={
                        "title": title,
                        "message": message,
                        "is_read": random.choice([True, False]),
                        "actor": random.choice(users) if users else None,
                    },
                )

    def create_audit_logs(self, org, users):
        """Create sample audit logs."""
        from core.models import AuditLog

        actions = [
            ("user.login", "user", "User logged in"),
            ("project.create", "project", "Created new project"),
            ("task.create", "task", "Created new task"),
            ("member.invite", "membership", "Invited new member"),
            ("settings.update", "organization", "Updated org settings"),
        ]

        for user in users[:5]:
            for action, resource_type, _ in random.sample(actions, k=2):
                AuditLog.objects.create(
                    user=user,
                    organization=org,
                    action=action,
                    resource_type=resource_type,
                    ip_address="127.0.0.1",
                    data={"detail": f"Sample {action} event"},
                )

    def create_feature_flags(self):
        """Create sample feature flags."""
        try:
            from django_matt.flags.models import FeatureFlag

            flags_data = [
                ("new_dashboard", "New Dashboard", "Enable the new dashboard UI", True, "boolean"),
                ("beta_features", "Beta Features", "Enable beta features for testing", False, "boolean"),
                ("dark_mode", "Dark Mode", "Enable dark mode support", True, "boolean"),
                ("ai_assistant", "AI Assistant", "Enable AI-powered assistant", False, "boolean"),
                ("checkout_v2", "Checkout V2", "New checkout flow", True, "percentage", 50),
                ("onboarding_ab", "Onboarding A/B", "A/B test for onboarding flow", True, "variant"),
            ]

            for name, display_name, description, enabled, flag_type, *args in flags_data:
                flag, created = FeatureFlag.objects.get_or_create(
                    name=name,
                    defaults={
                        "description": description,
                        "is_enabled": enabled,
                        "flag_type": flag_type,
                        "rollout_percentage": args[0] if args else 100,
                    },
                )
                if created:
                    self.stdout.write(f"Created feature flag: {name}")

        except ImportError:
            self.stdout.write(self.style.WARNING("Feature flags module not available"))

    def create_analytics_events(self, users, organizations):
        """Create sample analytics events."""
        from notifications.models import AnalyticsEvent

        event_names = [
            "page_view", "button_click", "form_submit", "feature_used",
            "task_created", "project_viewed", "search_performed"
        ]

        for user in users[:5]:
            for org in organizations:
                for _ in range(random.randint(5, 15)):
                    AnalyticsEvent.objects.create(
                        user=user,
                        organization=org,
                        event_name=random.choice(event_names),
                        event_category="user_action",
                        properties={
                            "source": random.choice(["web", "mobile", "api"]),
                            "duration_ms": random.randint(100, 5000),
                        },
                        page_url=f"/app/{random.choice(['dashboard', 'projects', 'tasks', 'settings'])}",
                        device_type=random.choice(["desktop", "mobile", "tablet"]),
                        browser=random.choice(["Chrome", "Firefox", "Safari"]),
                        timestamp=timezone.now() - timedelta(
                            days=random.randint(0, 30),
                            hours=random.randint(0, 23)
                        ),
                    )

    def create_coupons(self):
        """Create sample coupons."""
        from billing.models import Coupon

        coupons_data = [
            ("WELCOME20", "Welcome Discount", "percent", 20, "once"),
            ("ANNUAL50", "Annual Plan Discount", "percent", 50, "once"),
            ("STARTUP", "Startup Program", "percent", 100, "repeating", 12),
        ]

        for code, name, discount_type, value, duration, *args in coupons_data:
            Coupon.objects.get_or_create(
                code=code,
                defaults={
                    "stripe_coupon_id": f"coupon_{secrets.token_hex(8)}",
                    "name": name,
                    "discount_type": discount_type,
                    "discount_value": value,
                    "duration": duration,
                    "duration_months": args[0] if args else None,
                    "valid_until": timezone.now() + timedelta(days=365),
                },
            )

    def print_summary(self, admin_user, demo_users, organizations):
        """Print summary of created data."""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Seed data created successfully!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("Demo Credentials:"))
        self.stdout.write(f"  Admin: admin@saas-starter.local / admin123")
        self.stdout.write(f"  Demo users: <firstname>.<lastname><n>@demo.local / demo123")
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("Organizations:"))
        for org in organizations:
            self.stdout.write(f"  - {org.name} (slug: {org.slug}, plan: {org.plan})")
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("Quick Links:"))
        self.stdout.write("  API Docs: http://localhost:8000/api/docs")
        self.stdout.write("  Admin:    http://localhost:8000/admin/")
        self.stdout.write("  Health:   http://localhost:8000/api/health/")
        self.stdout.write("")
