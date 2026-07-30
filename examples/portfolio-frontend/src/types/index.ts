// Re-export all generated types matching portfolio-api schemas
export type {
  ProjectSchema,
  ProjectCreateSchema,
  ProjectUpdateSchema,
  SkillSchema,
  SkillCreateSchema,
  SkillUpdateSchema,
  ExperienceSchema,
  ExperienceCreateSchema,
  ExperienceUpdateSchema,
  ContactMessageSchema,
  ContactCreateSchema,
  UserSchema,
  LoginSchema,
  RegisterSchema,
  TokenSchema,
  RegisterResponseSchema,
  ProfileUpdateSchema,
  SiteConfigOut,
  SiteConfigUpdate,
} from './generated';

export type Project = ProjectSchema;
export type Skill = SkillSchema;
export type Experience = ExperienceSchema;
export type User = UserSchema;
export type SiteConfig = SiteConfigOut;

// Contact form type (public-facing, not the admin schema)
export interface ContactForm {
  name: string;
  email: string;
  subject?: string;
  message: string;
}
