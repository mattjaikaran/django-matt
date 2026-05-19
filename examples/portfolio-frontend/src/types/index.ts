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
  created_at: string;
  updated_at: string;
}

export interface Skill {
  id: string;
  name: string;
  category: 'FRONTEND' | 'BACKEND' | 'DEVOPS' | 'DATABASE' | 'MOBILE' | 'OTHER';
  level: number; // 1-5
  icon: string;
  order: number;
}

export interface Experience {
  id: string;
  company: string;
  role: string;
  company_url: string | null;
  location: string;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
  description: string;
  tech_used: string[];
  order: number;
}

export interface User {
  id: string;
  email: string;
  name: string;
  bio: string;
  avatar_url: string | null;
  github_url: string | null;
  linkedin_url: string | null;
  website_url: string | null;
  date_joined: string;
}

export interface ContactForm {
  name: string;
  email: string;
  subject?: string;
  message: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
