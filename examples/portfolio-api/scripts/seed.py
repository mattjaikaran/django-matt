#!/usr/bin/env python
"""Seed the portfolio database with sample data."""
import os
import sys
import django

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.hashers import make_password  # noqa: E402

from apps.users.models import User  # noqa: E402
from apps.projects.models import Project  # noqa: E402
from apps.skills.models import Skill  # noqa: E402
from apps.experience.models import Experience  # noqa: E402


def seed_users() -> User:
    user, created = User.objects.get_or_create(
        email="admin@example.com",
        defaults={
            "password": make_password("admin123"),
            "name": "Portfolio Admin",
            "bio": "Senior software engineer building awesome things.",
            "github_url": "https://github.com/example",
            "linkedin_url": "https://linkedin.com/in/example",
            "website_url": "https://example.dev",
            "is_staff": True,
            "is_superuser": True,
        },
    )
    print(f"{'Created' if created else 'Exists'}: admin@example.com / admin123")
    return user


def seed_projects() -> None:
    projects = [
        {
            "title": "Django Meta-Framework",
            "slug": "django-meta-framework",
            "description": "A batteries-included Django meta-framework for rapid API development.",
            "long_description": "# Django Meta-Framework\n\nBuilt on top of Django with async-first controllers, Pydantic v2 schemas, JWT auth, and much more.",
            "tech_stack": ["Python", "Django", "Pydantic", "PostgreSQL"],
            "github_url": "https://github.com/example/django-matt",
            "featured": True,
            "order": 1,
        },
        {
            "title": "E-Commerce Platform",
            "slug": "ecommerce-platform",
            "description": "Multi-vendor marketplace with Stripe payments and real-time inventory.",
            "long_description": "# E-Commerce Platform\n\nFull-stack marketplace with React frontend, Django backend, Celery workers, and Stripe integration.",
            "tech_stack": ["Python", "Django", "React", "TypeScript", "Stripe", "Redis"],
            "live_url": "https://shop.example.dev",
            "github_url": "https://github.com/example/ecommerce",
            "featured": True,
            "order": 2,
        },
        {
            "title": "Real-Time Chat App",
            "slug": "realtime-chat",
            "description": "WebSocket-based chat with presence indicators and message history.",
            "long_description": "# Real-Time Chat\n\nBuilt with Django Channels, Redis pub/sub, and a React frontend using TanStack Query.",
            "tech_stack": ["Python", "Django Channels", "React", "Redis", "WebSockets"],
            "github_url": "https://github.com/example/chat",
            "featured": True,
            "order": 3,
        },
        {
            "title": "iOS Music Player",
            "slug": "ios-music-player",
            "description": "Native iOS music player with custom audio visualizer built in Swift.",
            "long_description": "# iOS Music Player\n\nSwiftUI app with AVFoundation audio engine and custom Metal-based visualizer.",
            "tech_stack": ["Swift", "SwiftUI", "AVFoundation", "Metal"],
            "image_url": "https://example.dev/images/music-player.png",
            "featured": False,
            "order": 4,
        },
        {
            "title": "CLI DevTool",
            "slug": "cli-devtool",
            "description": "Developer productivity CLI built in Rust for sub-millisecond startup.",
            "long_description": "# CLI DevTool\n\nRust binary using clap for argument parsing with zero-cost async via Tokio.",
            "tech_stack": ["Rust", "Tokio", "clap"],
            "github_url": "https://github.com/example/devtool",
            "featured": False,
            "order": 5,
        },
        {
            "title": "Portfolio API",
            "slug": "portfolio-api",
            "description": "This very portfolio backend — async Django API with JWT auth.",
            "long_description": "# Portfolio API\n\nBuilt with django-matt, async controllers, Pydantic v2, and PostgreSQL.",
            "tech_stack": ["Python", "Django", "django-matt", "PostgreSQL"],
            "github_url": "https://github.com/example/portfolio-api",
            "featured": False,
            "order": 6,
        },
    ]

    for data in projects:
        _, created = Project.objects.get_or_create(slug=data["slug"], defaults=data)
        print(f"{'Created' if created else 'Exists'}: Project '{data['title']}'")


def seed_skills() -> None:
    skills = [
        # Backend
        {"name": "Python", "category": "backend", "level": 5, "icon": "python", "order": 1},
        {"name": "Django", "category": "backend", "level": 5, "icon": "django", "order": 2},
        {"name": "FastAPI", "category": "backend", "level": 4, "icon": "fastapi", "order": 3},
        {"name": "Rust", "category": "backend", "level": 3, "icon": "rust", "order": 4},
        # Frontend
        {"name": "React", "category": "frontend", "level": 4, "icon": "react", "order": 1},
        {"name": "TypeScript", "category": "frontend", "level": 4, "icon": "typescript", "order": 2},
        {"name": "Tailwind CSS", "category": "frontend", "level": 4, "icon": "tailwind", "order": 3},
        # DevOps
        {"name": "Docker", "category": "devops", "level": 4, "icon": "docker", "order": 1},
        {"name": "PostgreSQL", "category": "database", "level": 4, "icon": "postgresql", "order": 1},
        {"name": "Swift", "category": "mobile", "level": 3, "icon": "swift", "order": 1},
    ]

    for data in skills:
        existing = Skill.objects.filter(name=data["name"], category=data["category"]).first()
        if not existing:
            Skill.objects.create(**data)
            print(f"Created: Skill '{data['name']}'")
        else:
            print(f"Exists: Skill '{data['name']}'")


def seed_experience() -> None:
    experiences = [
        {
            "company": "Acme Corp",
            "role": "Senior Software Engineer",
            "company_url": "https://acme.example.com",
            "location": "San Francisco, CA",
            "start_date": "2022-01-01",
            "is_current": True,
            "description": "## Acme Corp\n\nLead backend engineer building internal platform tools and APIs serving 100k+ users.",
            "tech_used": ["Python", "Django", "React", "PostgreSQL", "Redis"],
            "order": 1,
        },
        {
            "company": "Startup XYZ",
            "role": "Full-Stack Engineer",
            "company_url": "https://xyz.example.com",
            "location": "Remote",
            "start_date": "2020-03-01",
            "end_date": "2021-12-31",
            "is_current": False,
            "description": "## Startup XYZ\n\nBuilt the core product from 0→1 including a mobile app and REST API.",
            "tech_used": ["Python", "FastAPI", "React Native", "TypeScript", "AWS"],
            "order": 2,
        },
        {
            "company": "Agency Co",
            "role": "Junior Developer",
            "location": "New York, NY",
            "start_date": "2018-06-01",
            "end_date": "2020-02-28",
            "is_current": False,
            "description": "## Agency Co\n\nDelivered client websites and internal tools for Fortune 500 clients.",
            "tech_used": ["Python", "Django", "JavaScript", "PostgreSQL"],
            "order": 3,
        },
    ]

    for data in experiences:
        existing = Experience.objects.filter(
            company=data["company"], role=data["role"]
        ).first()
        if not existing:
            Experience.objects.create(**data)
            print(f"Created: Experience '{data['role']} at {data['company']}'")
        else:
            print(f"Exists: Experience '{data['role']} at {data['company']}'")


if __name__ == "__main__":
    print("Seeding portfolio data...\n")
    seed_users()
    print()
    seed_projects()
    print()
    seed_skills()
    print()
    seed_experience()
    print("\nDone!")
