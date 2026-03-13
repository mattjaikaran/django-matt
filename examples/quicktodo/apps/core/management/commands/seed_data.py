from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from apps.organizations.models import Membership, MembershipRole, Organization, Team
from apps.todos.models import Todo, TodoList, TodoPriority, TodoStatus
from apps.users.models import User


class Command(BaseCommand):
    help = "Seed the database with sample data"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Clear existing data first")

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            Todo.objects.all().delete()
            TodoList.objects.all().delete()
            Team.objects.all().delete()
            Membership.objects.all().delete()
            Organization.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        # Admin user
        admin, created = User.objects.get_or_create(
            email="admin@example.com",
            defaults={
                "username": "admin",
                "password": make_password("admin123"),
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Admin",
                "last_name": "User",
            },
        )
        if created:
            self.stdout.write(f"  Created admin: {admin.email}")

        # Sample users
        users = []
        for name in ["alice", "bob", "charlie"]:
            user, created = User.objects.get_or_create(
                email=f"{name}@example.com",
                defaults={
                    "username": name,
                    "password": make_password("password123"),
                    "first_name": name.capitalize(),
                },
            )
            users.append(user)
            if created:
                self.stdout.write(f"  Created user: {user.email}")

        alice, bob, charlie = users

        # Organization
        org, _ = Organization.objects.get_or_create(
            slug="acme",
            defaults={"name": "Acme Corp", "description": "Demo organization"},
        )
        self.stdout.write(f"  Organization: {org.name}")

        # Memberships
        roles = [
            (admin, MembershipRole.OWNER),
            (alice, MembershipRole.ADMIN),
            (bob, MembershipRole.MEMBER),
            (charlie, MembershipRole.VIEWER),
        ]
        for user, role in roles:
            Membership.objects.get_or_create(
                user=user,
                organization=org,
                defaults={"role": role.value},
            )

        # Teams
        eng_team, _ = Team.objects.get_or_create(
            organization=org,
            slug="engineering",
            defaults={"name": "Engineering"},
        )
        design_team, _ = Team.objects.get_or_create(
            organization=org,
            slug="design",
            defaults={"name": "Design"},
        )

        # Todo Lists
        backlog, _ = TodoList.objects.get_or_create(
            organization=org,
            name="Sprint Backlog",
            defaults={"description": "Current sprint items", "created_by": alice},
        )
        bugs, _ = TodoList.objects.get_or_create(
            organization=org,
            name="Bug Tracker",
            defaults={"description": "Known bugs to fix", "created_by": alice},
        )

        # Todos
        sample_todos = [
            ("Set up CI/CD pipeline", backlog, TodoStatus.IN_PROGRESS, TodoPriority.HIGH, alice),
            ("Write API documentation", backlog, TodoStatus.PENDING, TodoPriority.MEDIUM, bob),
            ("Deploy to staging", backlog, TodoStatus.PENDING, TodoPriority.HIGH, alice),
            ("Review pull requests", backlog, TodoStatus.DONE, TodoPriority.MEDIUM, charlie),
            ("Fix login redirect bug", bugs, TodoStatus.IN_PROGRESS, TodoPriority.URGENT, alice),
            ("Handle 404 on missing org", bugs, TodoStatus.PENDING, TodoPriority.LOW, bob),
        ]
        for title, todo_list, status, priority, assignee in sample_todos:
            Todo.objects.get_or_create(
                title=title,
                todo_list=todo_list,
                defaults={
                    "status": status.value,
                    "priority": priority.value,
                    "assignee": assignee,
                },
            )

        self.stdout.write(self.style.SUCCESS("Seed data created successfully!"))
        self.stdout.write(f"  Users: {User.objects.count()}")
        self.stdout.write(f"  Organizations: {Organization.objects.count()}")
        self.stdout.write(f"  Todo Lists: {TodoList.objects.count()}")
        self.stdout.write(f"  Todos: {Todo.objects.count()}")
