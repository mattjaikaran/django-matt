export interface AuthorSummary {
  id: string;
  username: string;
  fullName: string;
  avatar: string | null;
}

export interface Tag {
  id: string;
  name: string;
  slug: string;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string;
  parentId: string | null;
}

export interface Post {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  coverImageUrl: string | null;
  author: AuthorSummary;
  category: Category | null;
  tags: Tag[];
  status: string;
  featured: boolean;
  publishedAt: string | null;
  viewCount: number;
  readingTimeMinutes: number;
  createdAt: string;
  updatedAt: string;
}

export interface PostDetail extends Post {
  content: string;
  seoTitle: string;
  seoDescription: string;
}

export interface PaginatedPosts {
  items: Post[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface CommentAuthor {
  id: string;
  username: string;
  fullName: string;
}

export interface Comment {
  id: string;
  postId: string;
  author: CommentAuthor | null;
  displayName: string;
  content: string;
  parentId: string | null;
  replies: Comment[];
  createdAt: string;
  updatedAt: string;
  isApproved: boolean;
}

export interface PostCreate {
  title: string;
  slug?: string;
  excerpt: string;
  content: string;
  coverImageUrl?: string | null;
  categoryId?: string | null;
  tagIds?: string[];
  status?: string;
  featured?: boolean;
  seoTitle?: string;
  seoDescription?: string;
}

export interface PostUpdate {
  title?: string;
  slug?: string;
  excerpt?: string;
  content?: string;
  coverImageUrl?: string | null;
  categoryId?: string | null;
  tagIds?: string[];
  status?: string;
  featured?: boolean;
  seoTitle?: string;
  seoDescription?: string;
}

export interface CommentCreate {
  postId: string;
  content: string;
}

export interface PostListParams {
  page?: number;
  page_size?: number;
  tag?: string;
  category?: string;
  author?: string;
  status?: string;
  featured?: boolean;
  search?: string;
}
