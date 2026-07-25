"""Benchmark schema definitions and sample data generators."""

from __future__ import annotations

import random
import string
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Small schema (5 fields)
# ---------------------------------------------------------------------------

class UserSmall(BaseModel):
    id: int
    name: str
    email: str
    active: bool = True
    score: float = 0.0


# ---------------------------------------------------------------------------
# Medium schema (15 fields)
# ---------------------------------------------------------------------------

class Address(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "US"


class UserMedium(BaseModel):
    id: int
    uuid: UUID
    name: str
    email: str
    phone: str
    active: bool = True
    role: str = "member"
    score: float = 0.0
    login_count: int = 0
    bio: str = ""
    avatar_url: str = ""
    address: Address
    created_at: datetime
    updated_at: datetime
    tags: list[str] = []


# ---------------------------------------------------------------------------
# Large schema (50 fields)
# ---------------------------------------------------------------------------

class SocialLinks(BaseModel):
    twitter: str = ""
    github: str = ""
    linkedin: str = ""
    website: str = ""


class Preferences(BaseModel):
    theme: str = "light"
    language: str = "en"
    timezone: str = "UTC"
    notifications_email: bool = True
    notifications_push: bool = True
    notifications_sms: bool = False
    digest_frequency: str = "daily"
    show_online_status: bool = True


class UserLarge(BaseModel):
    id: int
    uuid: UUID
    username: str
    first_name: str
    last_name: str
    email: str
    phone: str
    active: bool = True
    verified: bool = False
    role: str = "member"
    department: str = ""
    title: str = ""
    bio: str = ""
    avatar_url: str = ""
    cover_url: str = ""
    score: float = 0.0
    reputation: int = 0
    login_count: int = 0
    failed_login_count: int = 0
    last_login_ip: str = ""
    address: Address
    social: SocialLinks
    preferences: Preferences
    tags: list[str] = []
    permissions: list[str] = []
    groups: list[str] = []
    metadata: dict[str, str] = {}
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None
    deleted_at: datetime | None = None
    referral_code: str = ""
    referred_by: str | None = None
    stripe_customer_id: str = ""
    subscription_tier: str = "free"
    api_key: str = ""
    two_factor_enabled: bool = False
    locale: str = "en-US"
    currency: str = "USD"
    storage_used_bytes: int = 0
    max_storage_bytes: int = 1_073_741_824
    project_count: int = 0
    max_projects: int = 10
    team_id: int | None = None
    org_id: int | None = None
    manager_id: int | None = None
    hire_date: datetime | None = None
    notes: str = ""
    custom_fields: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Nested schema (3 levels deep)
# ---------------------------------------------------------------------------

class CommentNested(BaseModel):
    id: int
    author: str
    body: str
    created_at: datetime


class PostNested(BaseModel):
    id: int
    title: str
    body: str
    author: UserSmall
    comments: list[CommentNested] = []
    tags: list[str] = []
    created_at: datetime


class BlogNested(BaseModel):
    id: int
    name: str
    owner: UserMedium
    posts: list[PostNested] = []
    created_at: datetime


# ---------------------------------------------------------------------------
# Data generators (deterministic with fixed seed)
# ---------------------------------------------------------------------------

_rng = random.Random(42)


def _rand_str(length: int = 10) -> str:
    return "".join(_rng.choices(string.ascii_lowercase, k=length))


def _rand_email() -> str:
    return f"{_rand_str(8)}@example.com"


def _rand_datetime() -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC)


def _rand_uuid() -> UUID:
    return uuid4()


def gen_small_data() -> dict:
    return {
        "id": _rng.randint(1, 100_000),
        "name": f"User {_rand_str(6)}",
        "email": _rand_email(),
        "active": True,
        "score": round(_rng.uniform(0, 100), 2),
    }


def gen_address_data() -> dict:
    return {
        "street": f"{_rng.randint(1, 9999)} {_rand_str(8).title()} St",
        "city": _rand_str(8).title(),
        "state": _rand_str(2).upper(),
        "zip_code": f"{_rng.randint(10000, 99999)}",
        "country": "US",
    }


def gen_medium_data() -> dict:
    return {
        "id": _rng.randint(1, 100_000),
        "uuid": str(_rand_uuid()),
        "name": f"User {_rand_str(6)}",
        "email": _rand_email(),
        "phone": f"+1{_rng.randint(2000000000, 9999999999)}",
        "active": True,
        "role": _rng.choice(["member", "admin", "moderator"]),
        "score": round(_rng.uniform(0, 100), 2),
        "login_count": _rng.randint(0, 500),
        "bio": f"Bio text {_rand_str(30)}",
        "avatar_url": f"https://cdn.example.com/avatars/{_rand_str(12)}.jpg",
        "address": gen_address_data(),
        "created_at": _rand_datetime().isoformat(),
        "updated_at": _rand_datetime().isoformat(),
        "tags": [_rand_str(5) for _ in range(3)],
    }


def gen_large_data() -> dict:
    return {
        "id": _rng.randint(1, 100_000),
        "uuid": str(_rand_uuid()),
        "username": _rand_str(10),
        "first_name": _rand_str(6).title(),
        "last_name": _rand_str(8).title(),
        "email": _rand_email(),
        "phone": f"+1{_rng.randint(2000000000, 9999999999)}",
        "active": True,
        "verified": True,
        "role": "member",
        "department": "Engineering",
        "title": "Software Engineer",
        "bio": _rand_str(100),
        "avatar_url": f"https://cdn.example.com/{_rand_str(12)}.jpg",
        "cover_url": f"https://cdn.example.com/{_rand_str(12)}.jpg",
        "score": round(_rng.uniform(0, 100), 2),
        "reputation": _rng.randint(0, 10000),
        "login_count": _rng.randint(0, 500),
        "failed_login_count": 0,
        "last_login_ip": "192.168.1.1",
        "address": gen_address_data(),
        "social": {"twitter": "@test", "github": "test", "linkedin": "", "website": ""},
        "preferences": {
            "theme": "dark",
            "language": "en",
            "timezone": "America/New_York",
            "notifications_email": True,
            "notifications_push": True,
            "notifications_sms": False,
            "digest_frequency": "daily",
            "show_online_status": True,
        },
        "tags": [_rand_str(5) for _ in range(5)],
        "permissions": ["read", "write", "delete"],
        "groups": ["engineering", "backend"],
        "metadata": {"source": "api", "version": "2"},
        "created_at": _rand_datetime().isoformat(),
        "updated_at": _rand_datetime().isoformat(),
        "last_login_at": _rand_datetime().isoformat(),
        "deleted_at": None,
        "referral_code": _rand_str(8).upper(),
        "referred_by": None,
        "stripe_customer_id": f"cus_{_rand_str(14)}",
        "subscription_tier": "pro",
        "api_key": f"matt_{_rand_str(32)}",
        "two_factor_enabled": False,
        "locale": "en-US",
        "currency": "USD",
        "storage_used_bytes": _rng.randint(0, 1_000_000_000),
        "max_storage_bytes": 1_073_741_824,
        "project_count": _rng.randint(0, 50),
        "max_projects": 100,
        "team_id": 1,
        "org_id": 1,
        "manager_id": None,
        "hire_date": _rand_datetime().isoformat(),
        "notes": "",
        "custom_fields": {},
    }


def gen_nested_data() -> dict:
    small = gen_small_data()
    medium = gen_medium_data()
    comments = [
        {
            "id": i,
            "author": _rand_str(8),
            "body": _rand_str(50),
            "created_at": _rand_datetime().isoformat(),
        }
        for i in range(5)
    ]
    posts = [
        {
            "id": i,
            "title": f"Post {_rand_str(10)}",
            "body": _rand_str(200),
            "author": small,
            "comments": comments,
            "tags": [_rand_str(5) for _ in range(3)],
            "created_at": _rand_datetime().isoformat(),
        }
        for i in range(3)
    ]
    return {
        "id": 1,
        "name": f"Blog {_rand_str(8)}",
        "owner": medium,
        "posts": posts,
        "created_at": _rand_datetime().isoformat(),
    }


def gen_small_list(n: int = 100) -> list[dict]:
    return [gen_small_data() for _ in range(n)]
