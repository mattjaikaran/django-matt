/**
 * Generated API client types for portfolio-api.
 *
 * Auto-generated from Pydantic schemas in apps/*/schemas.py.
 * DO NOT EDIT MANUALLY — regenerate with: uv run python manage.py sync_types
 */

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  bio: string;
  avatar_url: string | null;
  github_url: string | null;
  linkedin_url: string | null;
  website_url: string | null;
  date_joined: string; // ISO 8601 datetime
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export interface RegisterResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

export interface ProfileUpdateRequest {
  name?: string | null;
  bio?: string | null;
  avatar_url?: string | null;
  github_url?: string | null;
  linkedin_url?: string | null;
  website_url?: string | null;
}

// ── Projects ──────────────────────────────────────────────────────────────────

export interface Project {
  id: string;
  title: string;
  slug: string;
  description: string;
  long_description: string;
  tech_stack: string[];
  image_url: string | null;
  live_url: string | null;
  github_url: string | null;
  featured: boolean;
  order: number;
  is_published: boolean;
  created_at: string; // ISO 8601 datetime
  updated_at: string; // ISO 8601 datetime
}

export interface ProjectCreateRequest {
  title: string;
  slug: string;
  description: string;
  long_description?: string;
  tech_stack?: string[];
  image_url?: string | null;
  live_url?: string | null;
  github_url?: string | null;
  featured?: boolean;
  order?: number;
  is_published?: boolean;
}

export interface ProjectUpdateRequest {
  title?: string | null;
  slug?: string | null;
  description?: string | null;
  long_description?: string | null;
  tech_stack?: string[] | null;
  image_url?: string | null;
  live_url?: string | null;
  github_url?: string | null;
  featured?: boolean | null;
  order?: number | null;
  is_published?: boolean | null;
}

// ── Skills ────────────────────────────────────────────────────────────────────

export type SkillCategory = "frontend" | "backend" | "devops" | "database" | "mobile" | "other";

export interface Skill {
  id: string;
  name: string;
  category: string;
  level: number; // 1–5
  icon: string;
  order: number;
  created_at: string; // ISO 8601 datetime
  updated_at: string; // ISO 8601 datetime
}

export interface SkillCreateRequest {
  name: string;
  category: SkillCategory;
  level?: number; // 1–5, default 3
  icon?: string;
  order?: number;
}

export interface SkillUpdateRequest {
  name?: string | null;
  category?: SkillCategory | null;
  level?: number | null; // 1–5
  icon?: string | null;
  order?: number | null;
}

// ── Experience ────────────────────────────────────────────────────────────────

export interface Experience {
  id: string;
  company: string;
  role: string;
  company_url: string | null;
  location: string;
  start_date: string; // ISO 8601 date
  end_date: string | null; // ISO 8601 date
  is_current: boolean;
  description: string;
  tech_used: string[];
  order: number;
  created_at: string; // ISO 8601 datetime
  updated_at: string; // ISO 8601 datetime
}

export interface ExperienceCreateRequest {
  company: string;
  role: string;
  company_url?: string | null;
  location?: string;
  start_date: string; // ISO 8601 date
  end_date?: string | null;
  is_current?: boolean;
  description: string;
  tech_used?: string[];
  order?: number;
}

export interface ExperienceUpdateRequest {
  company?: string | null;
  role?: string | null;
  company_url?: string | null;
  location?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  is_current?: boolean | null;
  description?: string | null;
  tech_used?: string[] | null;
  order?: number | null;
}

// ── Contact ───────────────────────────────────────────────────────────────────

export interface ContactMessage {
  id: string;
  name: string;
  email: string;
  subject: string;
  message: string;
  is_read: boolean;
  created_at: string; // ISO 8601 datetime
  updated_at: string; // ISO 8601 datetime
}

export interface ContactCreateRequest {
  name: string;
  email: string;
  subject?: string;
  message: string;
}

// ── Site Config ───────────────────────────────────────────────────────────────

export interface SiteConfig {
  site_name: string;
  tagline: string;
  description: string;
  about_text: string;
  email: string;
  phone: string;
  location: string;
  github_url: string;
  linkedin_url: string;
  twitter_url: string;
  resume_url: string;
  meta_description: string;
  meta_keywords: string;
}

export interface SiteConfigUpdateRequest {
  site_name?: string | null;
  tagline?: string | null;
  description?: string | null;
  about_text?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  github_url?: string | null;
  linkedin_url?: string | null;
  twitter_url?: string | null;
  resume_url?: string | null;
  meta_description?: string | null;
  meta_keywords?: string | null;
}

// ── Common ────────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface DeleteResponse {
  message: string;
}

export interface HealthResponse {
  status: string;
}

export interface ApiError {
  status_code: number;
  message: string;
  detail?: unknown;
}

// ── API Endpoints (route → types) ─────────────────────────────────────────────

export interface ApiEndpoints {
  // Auth
  "POST /api/auth/register": {
    request: RegisterRequest;
    response: RegisterResponse;
  };
  "POST /api/auth/login": {
    request: LoginRequest;
    response: TokenPair;
  };
  "GET /api/auth/me": {
    response: User;
  };
  "PATCH /api/auth/me": {
    request: ProfileUpdateRequest;
    response: User;
  };

  // Projects
  "GET /api/projects": {
    response: PaginatedResponse<Project>;
  };
  "POST /api/projects": {
    request: ProjectCreateRequest;
    response: Project;
  };
  "GET /api/projects/{slug}": {
    response: Project;
  };
  "PATCH /api/projects/{slug}": {
    request: ProjectUpdateRequest;
    response: Project;
  };
  "DELETE /api/projects/{slug}": {
    response: DeleteResponse;
  };

  // Skills
  "GET /api/skills": {
    response: PaginatedResponse<Skill>;
  };
  "POST /api/skills": {
    request: SkillCreateRequest;
    response: Skill;
  };
  "GET /api/skills/{id}": {
    response: Skill;
  };
  "PATCH /api/skills/{id}": {
    request: SkillUpdateRequest;
    response: Skill;
  };
  "DELETE /api/skills/{id}": {
    response: DeleteResponse;
  };

  // Experience
  "GET /api/experience": {
    response: PaginatedResponse<Experience>;
  };
  "POST /api/experience": {
    request: ExperienceCreateRequest;
    response: Experience;
  };
  "GET /api/experience/{id}": {
    response: Experience;
  };
  "PATCH /api/experience/{id}": {
    request: ExperienceUpdateRequest;
    response: Experience;
  };
  "DELETE /api/experience/{id}": {
    response: DeleteResponse;
  };

  // Contact
  "POST /api/contact": {
    request: ContactCreateRequest;
    response: ContactMessage;
  };
  "GET /api/contact": {
    response: PaginatedResponse<ContactMessage>;
  };
  "PATCH /api/contact/{id}/read": {
    response: ContactMessage;
  };

  // Site Config
  "GET /api/site-config": {
    response: SiteConfig;
  };
  "PATCH /api/site-config": {
    request: SiteConfigUpdateRequest;
    response: SiteConfig;
  };

  // Health
  "GET /api/health": {
    response: HealthResponse;
  };
}
