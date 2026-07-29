// Auto-generated TypeScript types from Pydantic schemas
// Do not edit manually - regenerate with sync_types command

export interface ProjectCreateSchema {
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

export interface ProjectSchema {
  id: string;
  title: string;
  slug: string;
  description: string;
  long_description: string;
  tech_stack: string[];
  image_url?: string | null;
  live_url?: string | null;
  github_url?: string | null;
  featured: boolean;
  order: number;
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectUpdateSchema {
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

export interface SkillCreateSchema {
  name: string;
  category: "frontend" | "backend" | "devops" | "database" | "mobile" | "other";
  level?: number;
  icon?: string;
  order?: number;
}

export interface SkillSchema {
  id: string;
  name: string;
  category: string;
  level: number;
  icon: string;
  order: number;
  created_at: string;
  updated_at: string;
}

export interface SkillUpdateSchema {
  name?: string | null;
  category?: "frontend" | "backend" | "devops" | "database" | "mobile" | "other" | null;
  level?: number | null;
  icon?: string | null;
  order?: number | null;
}

export interface ExperienceCreateSchema {
  company: string;
  role: string;
  company_url?: string | null;
  location?: string;
  start_date: string;
  end_date?: string | null;
  is_current?: boolean;
  description: string;
  tech_used?: string[];
  order?: number;
}

export interface ExperienceSchema {
  id: string;
  company: string;
  role: string;
  company_url?: string | null;
  location: string;
  start_date: string;
  end_date?: string | null;
  is_current: boolean;
  description: string;
  tech_used: string[];
  order: number;
  created_at: string;
  updated_at: string;
}

export interface ExperienceUpdateSchema {
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

export interface ContactCreateSchema {
  name: string;
  email: string;
  subject?: string;
  message: string;
}

export interface ContactMessageSchema {
  id: string;
  name: string;
  email: string;
  subject: string;
  message: string;
  is_read: boolean;
  created_at: string;
  updated_at: string;
}
