"""Pydantic schemas for SiteConfig."""

from pydantic import BaseModel, Field


class SiteConfigOut(BaseModel):
    """Public site configuration response."""

    site_name: str
    tagline: str
    description: str
    about_text: str
    email: str
    phone: str
    location: str
    github_url: str
    linkedin_url: str
    twitter_url: str
    resume_url: str
    meta_description: str
    meta_keywords: str

    model_config = {"from_attributes": True}


class SiteConfigUpdate(BaseModel):
    """Fields that can be updated (admin only)."""

    site_name: str | None = None
    tagline: str | None = None
    description: str | None = None
    about_text: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    twitter_url: str | None = None
    resume_url: str | None = None
    meta_description: str | None = None
    meta_keywords: str | None = None
