/**
 * Generated Zod schemas for portfolio-api.
 *
 * Auto-generated from Pydantic schemas in apps/*/schemas.py.
 * DO NOT EDIT MANUALLY — regenerate with: uv run python manage.py sync_types
 */

import { z } from "zod";

// ── Auth ──────────────────────────────────────────────────────────────────────

export const UserSchema = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string(),
  bio: z.string(),
  avatar_url: z.string().nullable(),
  github_url: z.string().nullable(),
  linkedin_url: z.string().nullable(),
  website_url: z.string().nullable(),
  date_joined: z.string(), // ISO 8601 datetime
});

export const RegisterRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().min(1).max(255),
});

export const LoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string(),
});

export const TokenPairSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
});

export const RegisterResponseSchema = z.object({
  user: UserSchema,
  access_token: z.string(),
  refresh_token: z.string(),
});

export const ProfileUpdateRequestSchema = z.object({
  name: z.string().min(1).max(255).nullable().optional(),
  bio: z.string().nullable().optional(),
  avatar_url: z.string().nullable().optional(),
  github_url: z.string().nullable().optional(),
  linkedin_url: z.string().nullable().optional(),
  website_url: z.string().nullable().optional(),
});

// ── Projects ──────────────────────────────────────────────────────────────────

export const ProjectSchema = z.object({
  id: z.string(),
  title: z.string(),
  slug: z.string(),
  description: z.string(),
  long_description: z.string(),
  tech_stack: z.array(z.string()),
  image_url: z.string().nullable(),
  live_url: z.string().nullable(),
  github_url: z.string().nullable(),
  featured: z.boolean(),
  order: z.number().int(),
  is_published: z.boolean(),
  created_at: z.string(), // ISO 8601 datetime
  updated_at: z.string(), // ISO 8601 datetime
});

export const ProjectCreateRequestSchema = z.object({
  title: z.string().min(1).max(255),
  slug: z.string().regex(/^[a-z0-9-]+$/),
  description: z.string(),
  long_description: z.string().default(""),
  tech_stack: z.array(z.string()).default([]),
  image_url: z.string().nullable().optional(),
  live_url: z.string().nullable().optional(),
  github_url: z.string().nullable().optional(),
  featured: z.boolean().default(false),
  order: z.number().int().default(0),
  is_published: z.boolean().default(true),
});

export const ProjectUpdateRequestSchema = z.object({
  title: z.string().min(1).max(255).nullable().optional(),
  slug: z.string().regex(/^[a-z0-9-]+$/).nullable().optional(),
  description: z.string().nullable().optional(),
  long_description: z.string().nullable().optional(),
  tech_stack: z.array(z.string()).nullable().optional(),
  image_url: z.string().nullable().optional(),
  live_url: z.string().nullable().optional(),
  github_url: z.string().nullable().optional(),
  featured: z.boolean().nullable().optional(),
  order: z.number().int().nullable().optional(),
  is_published: z.boolean().nullable().optional(),
});

// ── Skills ────────────────────────────────────────────────────────────────────

export const SkillCategorySchema = z.enum([
  "frontend",
  "backend",
  "devops",
  "database",
  "mobile",
  "other",
]);

export const SkillSchema = z.object({
  id: z.string(),
  name: z.string(),
  category: z.string(),
  level: z.number().int(),
  icon: z.string(),
  order: z.number().int(),
  created_at: z.string(), // ISO 8601 datetime
  updated_at: z.string(), // ISO 8601 datetime
});

export const SkillCreateRequestSchema = z.object({
  name: z.string().min(1).max(100),
  category: SkillCategorySchema,
  level: z.number().int().min(1).max(5).default(3),
  icon: z.string().max(50).default(""),
  order: z.number().int().default(0),
});

export const SkillUpdateRequestSchema = z.object({
  name: z.string().min(1).max(100).nullable().optional(),
  category: SkillCategorySchema.nullable().optional(),
  level: z.number().int().min(1).max(5).nullable().optional(),
  icon: z.string().nullable().optional(),
  order: z.number().int().nullable().optional(),
});

// ── Experience ────────────────────────────────────────────────────────────────

export const ExperienceSchema = z.object({
  id: z.string(),
  company: z.string(),
  role: z.string(),
  company_url: z.string().nullable(),
  location: z.string(),
  start_date: z.string(), // ISO 8601 date
  end_date: z.string().nullable(), // ISO 8601 date
  is_current: z.boolean(),
  description: z.string(),
  tech_used: z.array(z.string()),
  order: z.number().int(),
  created_at: z.string(), // ISO 8601 datetime
  updated_at: z.string(), // ISO 8601 datetime
});

export const ExperienceCreateRequestSchema = z.object({
  company: z.string().min(1).max(255),
  role: z.string().min(1).max(255),
  company_url: z.string().nullable().optional(),
  location: z.string().default(""),
  start_date: z.string(), // ISO 8601 date
  end_date: z.string().nullable().optional(),
  is_current: z.boolean().default(false),
  description: z.string(),
  tech_used: z.array(z.string()).default([]),
  order: z.number().int().default(0),
});

export const ExperienceUpdateRequestSchema = z.object({
  company: z.string().min(1).max(255).nullable().optional(),
  role: z.string().min(1).max(255).nullable().optional(),
  company_url: z.string().nullable().optional(),
  location: z.string().nullable().optional(),
  start_date: z.string().nullable().optional(),
  end_date: z.string().nullable().optional(),
  is_current: z.boolean().nullable().optional(),
  description: z.string().nullable().optional(),
  tech_used: z.array(z.string()).nullable().optional(),
  order: z.number().int().nullable().optional(),
});

// ── Contact ───────────────────────────────────────────────────────────────────

export const ContactMessageSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string(),
  subject: z.string(),
  message: z.string(),
  is_read: z.boolean(),
  created_at: z.string(), // ISO 8601 datetime
  updated_at: z.string(), // ISO 8601 datetime
});

export const ContactCreateRequestSchema = z.object({
  name: z.string().min(1).max(255),
  email: z.string().email(),
  subject: z.string().max(255).default(""),
  message: z.string().min(1),
});

// ── Site Config ───────────────────────────────────────────────────────────────

export const SiteConfigSchema = z.object({
  site_name: z.string(),
  tagline: z.string(),
  description: z.string(),
  about_text: z.string(),
  email: z.string(),
  phone: z.string(),
  location: z.string(),
  github_url: z.string(),
  linkedin_url: z.string(),
  twitter_url: z.string(),
  resume_url: z.string(),
  meta_description: z.string(),
  meta_keywords: z.string(),
});

export const SiteConfigUpdateRequestSchema = z.object({
  site_name: z.string().nullable().optional(),
  tagline: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  about_text: z.string().nullable().optional(),
  email: z.string().nullable().optional(),
  phone: z.string().nullable().optional(),
  location: z.string().nullable().optional(),
  github_url: z.string().nullable().optional(),
  linkedin_url: z.string().nullable().optional(),
  twitter_url: z.string().nullable().optional(),
  resume_url: z.string().nullable().optional(),
  meta_description: z.string().nullable().optional(),
  meta_keywords: z.string().nullable().optional(),
});

// ── Common ────────────────────────────────────────────────────────────────────

export const PaginatedResponseSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    items: z.array(itemSchema),
    total: z.number().int(),
  });

export const DeleteResponseSchema = z.object({
  message: z.string(),
});

export const HealthResponseSchema = z.object({
  status: z.string(),
});

export const ApiErrorSchema = z.object({
  status_code: z.number().int(),
  message: z.string(),
  detail: z.unknown().optional(),
});

// ── Inferred types ────────────────────────────────────────────────────────────

export type User = z.infer<typeof UserSchema>;
export type RegisterRequest = z.infer<typeof RegisterRequestSchema>;
export type LoginRequest = z.infer<typeof LoginRequestSchema>;
export type TokenPair = z.infer<typeof TokenPairSchema>;
export type RegisterResponse = z.infer<typeof RegisterResponseSchema>;
export type ProfileUpdateRequest = z.infer<typeof ProfileUpdateRequestSchema>;

export type Project = z.infer<typeof ProjectSchema>;
export type ProjectCreateRequest = z.infer<typeof ProjectCreateRequestSchema>;
export type ProjectUpdateRequest = z.infer<typeof ProjectUpdateRequestSchema>;

export type SkillCategory = z.infer<typeof SkillCategorySchema>;
export type Skill = z.infer<typeof SkillSchema>;
export type SkillCreateRequest = z.infer<typeof SkillCreateRequestSchema>;
export type SkillUpdateRequest = z.infer<typeof SkillUpdateRequestSchema>;

export type Experience = z.infer<typeof ExperienceSchema>;
export type ExperienceCreateRequest = z.infer<typeof ExperienceCreateRequestSchema>;
export type ExperienceUpdateRequest = z.infer<typeof ExperienceUpdateRequestSchema>;

export type ContactMessage = z.infer<typeof ContactMessageSchema>;
export type ContactCreateRequest = z.infer<typeof ContactCreateRequestSchema>;

export type SiteConfig = z.infer<typeof SiteConfigSchema>;
export type SiteConfigUpdateRequest = z.infer<typeof SiteConfigUpdateRequestSchema>;

export type HealthResponse = z.infer<typeof HealthResponseSchema>;
export type ApiError = z.infer<typeof ApiErrorSchema>;
