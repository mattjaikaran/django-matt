// Auto-generated TypeScript types from Pydantic schemas
// Do not edit manually - regenerate with sync_types command

export interface AuthorSummary {
  id: string;
  username: string;
  full_name: string;
  avatar?: string | null;
}

export interface CategoryCreate {
  name: string;
  description?: string;
  parent_id?: string | null;
}

export interface CategoryResponse {
  id: string;
  name: string;
  slug: string;
  description: string;
  parent_id?: string | null;
}

export interface CategoryUpdate {
  name?: string | null;
  description?: string | null;
  parent_id?: string | null;
}

export interface PaginatedPostsResponse {
  items: PostListResponse[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PostCreate {
  title: string;
  content: string;
  excerpt?: string;
  status?: string;
  featured?: boolean;
  category_id?: string | null;
  tag_ids?: string[];
  seo_title?: string;
  seo_description?: string;
  published_at?: string | null;
}

export interface PostDetailResponse {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  cover_image_url?: string | null;
  author: AuthorSummary;
  category?: CategoryResponse | null;
  tags?: TagResponse[];
  status: string;
  featured: boolean;
  published_at?: string | null;
  view_count: number;
  reading_time_minutes: number;
  created_at: string;
  updated_at: string;
  content: string;
  seo_title: string;
  seo_description: string;
}

export interface PostListResponse {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  cover_image_url?: string | null;
  author: AuthorSummary;
  category?: CategoryResponse | null;
  tags?: TagResponse[];
  status: string;
  featured: boolean;
  published_at?: string | null;
  view_count: number;
  reading_time_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface PostUpdate {
  title?: string | null;
  content?: string | null;
  excerpt?: string | null;
  status?: string | null;
  featured?: boolean | null;
  category_id?: string | null;
  tag_ids?: string[] | null;
  seo_title?: string | null;
  seo_description?: string | null;
  published_at?: string | null;
}

export interface SEOMetaResponse {
  title: string;
  description: string;
  og_title: string;
  og_description: string;
  og_image?: string | null;
  canonical_url: string;
  published_at?: string | null;
  author: string;
}

export interface TagCreate {
  name: string;
}

export interface TagResponse {
  id: string;
  name: string;
  slug: string;
}

export interface AuthorProfileResponse {
  bio: string;
  avatar?: string | null;
  website: string;
  twitter: string;
  github: string;
  linkedin: string;
  location: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ProfileUpdateRequest {
  first_name?: string | null;
  last_name?: string | null;
  bio?: string | null;
  website?: string | null;
  twitter?: string | null;
  github?: string | null;
  linkedin?: string | null;
  location?: string | null;
}

export interface RefreshRequest {
  refresh: string;
}

export interface RefreshResponse {
  access: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

export interface TokenResponse {
  access: string;
  refresh: string;
  user: UserResponse;
}

export interface UserPublicResponse {
  id: string;
  username: string;
  full_name: string;
  author_profile?: AuthorProfileResponse | null;
}

export interface UserResponse {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  full_name: string;
  is_staff: boolean;
  date_joined: string;
  author_profile?: AuthorProfileResponse | null;
}

export interface CommentAuthorSummary {
  id: string;
  username: string;
  full_name: string;
}

export interface CommentCreate {
  post_id: string;
  content: string;
  parent_id?: string | null;
  author_name?: string;
  author_email?: string;
}

export interface CommentResponse {
  id: string;
  post_id: string;
  author?: CommentAuthorSummary | null;
  display_name: string;
  content: string;
  parent_id?: string | null;
  replies?: CommentResponse[];
  is_approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface CommentUpdate {
  content: string;
}
