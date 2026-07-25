// Auto-generated Zod schemas from Pydantic models
// Do not edit manually - regenerate with sync_types command

import { z } from "zod";

export const AuthorSummarySchema = z.object({
  id: z.string().uuid(),
  username: z.string(),
  full_name: z.string(),
  avatar: z.string().nullable(),
});

export const CategoryCreateSchema = z.object({
  name: z.string(),
  description: z.string().default("").optional(),
  parent_id: z.string().uuid().nullable(),
});

export const CategoryResponseSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  slug: z.string(),
  description: z.string(),
  parent_id: z.string().uuid().nullable(),
});

export const CategoryUpdateSchema = z.object({
  name: z.string().nullable(),
  description: z.string().nullable(),
  parent_id: z.string().uuid().nullable(),
});

export const TagCreateSchema = z.object({
  name: z.string(),
});

export const TagResponseSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  slug: z.string(),
});

export const PostCreateSchema = z.object({
  title: z.string(),
  content: z.string(),
  excerpt: z.string().default("").optional(),
  status: z.string().default("draft").optional(),
  featured: z.boolean().default(false).optional(),
  category_id: z.string().uuid().nullable(),
  tag_ids: z.array(z.string().uuid()).default([]).optional(),
  seo_title: z.string().default("").optional(),
  seo_description: z.string().default("").optional(),
  published_at: z.string().datetime().nullable(),
});

export const PostListResponseSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  slug: z.string(),
  excerpt: z.string(),
  cover_image_url: z.string().nullable(),
  author: AuthorSummarySchema,
  category: CategoryResponseSchema.nullable(),
  tags: z.array(TagResponseSchema).default([]).optional(),
  status: z.string(),
  featured: z.boolean(),
  published_at: z.string().datetime().nullable(),
  view_count: z.number().int(),
  reading_time_minutes: z.number().int(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export const PostDetailResponseSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  slug: z.string(),
  excerpt: z.string(),
  cover_image_url: z.string().nullable(),
  author: AuthorSummarySchema,
  category: CategoryResponseSchema.nullable(),
  tags: z.array(TagResponseSchema).default([]).optional(),
  status: z.string(),
  featured: z.boolean(),
  published_at: z.string().datetime().nullable(),
  view_count: z.number().int(),
  reading_time_minutes: z.number().int(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  content: z.string(),
  seo_title: z.string(),
  seo_description: z.string(),
});

export const PaginatedPostsResponseSchema = z.object({
  items: z.array(PostListResponseSchema),
  total: z.number().int(),
  page: z.number().int(),
  page_size: z.number().int(),
  total_pages: z.number().int(),
});

export const PostUpdateSchema = z.object({
  title: z.string().nullable(),
  content: z.string().nullable(),
  excerpt: z.string().nullable(),
  status: z.string().nullable(),
  featured: z.boolean().nullable(),
  category_id: z.string().uuid().nullable(),
  tag_ids: z.array(z.string().uuid()).nullable(),
  seo_title: z.string().nullable(),
  seo_description: z.string().nullable(),
  published_at: z.string().datetime().nullable(),
});

export const SEOMetaResponseSchema = z.object({
  title: z.string(),
  description: z.string(),
  og_title: z.string(),
  og_description: z.string(),
  og_image: z.string().nullable(),
  canonical_url: z.string(),
  published_at: z.string().datetime().nullable(),
  author: z.string(),
});

export const AuthorProfileResponseSchema = z.object({
  bio: z.string(),
  avatar: z.string().nullable(),
  website: z.string(),
  twitter: z.string(),
  github: z.string(),
  linkedin: z.string(),
  location: z.string(),
});

export const LoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string(),
});

export const ProfileUpdateRequestSchema = z.object({
  first_name: z.string().nullable(),
  last_name: z.string().nullable(),
  bio: z.string().nullable(),
  website: z.string().nullable(),
  twitter: z.string().nullable(),
  github: z.string().nullable(),
  linkedin: z.string().nullable(),
  location: z.string().nullable(),
});

export const RefreshRequestSchema = z.object({
  refresh: z.string(),
});

export const RefreshResponseSchema = z.object({
  access: z.string(),
});

export const RegisterRequestSchema = z.object({
  email: z.string().email(),
  username: z.string(),
  password: z.string(),
  first_name: z.string().default("").optional(),
  last_name: z.string().default("").optional(),
});

export const UserResponseSchema = z.object({
  id: z.string().uuid(),
  email: z.string(),
  username: z.string(),
  first_name: z.string(),
  last_name: z.string(),
  full_name: z.string(),
  is_staff: z.boolean(),
  date_joined: z.string().datetime(),
  author_profile: AuthorProfileResponseSchema.nullable(),
});

export const TokenResponseSchema = z.object({
  access: z.string(),
  refresh: z.string(),
  user: UserResponseSchema,
});

export const UserPublicResponseSchema = z.object({
  id: z.string().uuid(),
  username: z.string(),
  full_name: z.string(),
  author_profile: AuthorProfileResponseSchema.nullable(),
});

export const CommentAuthorSummarySchema = z.object({
  id: z.string().uuid(),
  username: z.string(),
  full_name: z.string(),
});

export const CommentCreateSchema = z.object({
  post_id: z.string().uuid(),
  content: z.string(),
  parent_id: z.string().uuid().nullable(),
  author_name: z.string().default("").optional(),
  author_email: z.string().default("").optional(),
});

export type CommentResponse = {
  id: string;
  post_id: string;
  author: { id: string; username: string; full_name: string } | null;
  display_name: string;
  content: string;
  parent_id: string | null;
  replies?: CommentResponse[];
  is_approved: boolean;
  created_at: string;
  updated_at: string;
};

export const CommentResponseSchema: z.ZodType<CommentResponse> = z.lazy(() =>
  z.object({
    id: z.string().uuid(),
    post_id: z.string().uuid(),
    author: CommentAuthorSummarySchema.nullable(),
    display_name: z.string(),
    content: z.string(),
    parent_id: z.string().uuid().nullable(),
    replies: z.array(CommentResponseSchema).default([]).optional(),
    is_approved: z.boolean(),
    created_at: z.string().datetime(),
    updated_at: z.string().datetime(),
  })
);

export const CommentUpdateSchema = z.object({
  content: z.string(),
});

// Inferred types
export type AuthorSummary = z.infer<typeof AuthorSummarySchema>;
export type CategoryCreate = z.infer<typeof CategoryCreateSchema>;
export type CategoryResponse = z.infer<typeof CategoryResponseSchema>;
export type CategoryUpdate = z.infer<typeof CategoryUpdateSchema>;
export type PaginatedPostsResponse = z.infer<typeof PaginatedPostsResponseSchema>;
export type PostCreate = z.infer<typeof PostCreateSchema>;
export type PostDetailResponse = z.infer<typeof PostDetailResponseSchema>;
export type PostListResponse = z.infer<typeof PostListResponseSchema>;
export type PostUpdate = z.infer<typeof PostUpdateSchema>;
export type SEOMetaResponse = z.infer<typeof SEOMetaResponseSchema>;
export type TagCreate = z.infer<typeof TagCreateSchema>;
export type TagResponse = z.infer<typeof TagResponseSchema>;
export type AuthorProfileResponse = z.infer<typeof AuthorProfileResponseSchema>;
export type LoginRequest = z.infer<typeof LoginRequestSchema>;
export type ProfileUpdateRequest = z.infer<typeof ProfileUpdateRequestSchema>;
export type RefreshRequest = z.infer<typeof RefreshRequestSchema>;
export type RefreshResponse = z.infer<typeof RefreshResponseSchema>;
export type RegisterRequest = z.infer<typeof RegisterRequestSchema>;
export type TokenResponse = z.infer<typeof TokenResponseSchema>;
export type UserPublicResponse = z.infer<typeof UserPublicResponseSchema>;
export type UserResponse = z.infer<typeof UserResponseSchema>;
export type CommentAuthorSummary = z.infer<typeof CommentAuthorSummarySchema>;
export type CommentCreate = z.infer<typeof CommentCreateSchema>;
export type CommentUpdate = z.infer<typeof CommentUpdateSchema>;
