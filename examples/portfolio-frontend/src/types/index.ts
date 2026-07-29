// --- API response types — match portfolio-api schemas ---

export interface Project {
  id: string;
  title: string;
  slug: string;
  description: string;
  long_description?: string;
  tech_stack: string[];
  image_url: string | null;
  live_url: string | null;
  github_url: string | null;
  featured: boolean;
  created_at: string;
  updated_at?: string;
}

export interface Skill {
  id: string;
  name: string;
  category: string;
  level: number;
  icon: string | null;
  order: number;
}

export interface Experience {
  id: string;
  company: string;
  role: string;
  company_url: string | null;
  location: string | null;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
  description: string;
  tech_used: string[];
}

export interface ContactForm {
  name: string;
  email: string;
  subject?: string;
  message: string;
}

// Portfolio API returns arrays directly, not paginated wrappers.
// Use these hooks to access them:
//   useProjects() → Project[]
//   useSkills() → Skill[]
//   useExperience() → Experience[]
