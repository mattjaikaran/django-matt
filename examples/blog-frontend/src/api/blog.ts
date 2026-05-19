import { apiClient, handleApiResponse } from '@/lib/api';
import type {
  AuthorSummary,
  Category,
  Comment,
  CommentCreate,
  PaginatedPosts,
  Post,
  PostCreate,
  PostDetail,
  PostListParams,
  PostUpdate,
  Tag,
} from '@/types/blog';

export const postsApi = {
  list: async (params?: PostListParams): Promise<PaginatedPosts> => {
    const response = await apiClient.get<PaginatedPosts>('/posts/', { params });
    return handleApiResponse(response);
  },

  get: async (slug: string): Promise<PostDetail> => {
    const response = await apiClient.get<PostDetail>(`/posts/${slug}`);
    return handleApiResponse(response);
  },

  search: async (q: string): Promise<Post[]> => {
    const response = await apiClient.get<Post[]>('/posts/search', {
      params: { q },
    });
    return handleApiResponse(response);
  },

  create: async (data: PostCreate): Promise<PostDetail> => {
    const response = await apiClient.post<PostDetail>('/posts/', data);
    return handleApiResponse(response);
  },

  update: async (slug: string, data: PostUpdate): Promise<PostDetail> => {
    const response = await apiClient.patch<PostDetail>(`/posts/${slug}`, data);
    return handleApiResponse(response);
  },

  delete: async (slug: string): Promise<void> => {
    await apiClient.delete(`/posts/${slug}`);
  },
};

export const tagsApi = {
  list: async (): Promise<Tag[]> => {
    const response = await apiClient.get<Tag[]>('/tags/');
    return handleApiResponse(response);
  },

  get: async (slug: string): Promise<Tag> => {
    const response = await apiClient.get<Tag>(`/tags/${slug}`);
    return handleApiResponse(response);
  },
};

export const categoriesApi = {
  list: async (): Promise<Category[]> => {
    const response = await apiClient.get<Category[]>('/categories/');
    return handleApiResponse(response);
  },

  get: async (slug: string): Promise<Category> => {
    const response = await apiClient.get<Category>(`/categories/${slug}`);
    return handleApiResponse(response);
  },
};

export const commentsApi = {
  list: async (postId: string): Promise<Comment[]> => {
    const response = await apiClient.get<Comment[]>('/comments/', {
      params: { post: postId },
    });
    return handleApiResponse(response);
  },

  create: async (data: CommentCreate): Promise<Comment> => {
    const response = await apiClient.post<Comment>('/comments/', data);
    return handleApiResponse(response);
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/comments/${id}`);
  },
};

export const authorsApi = {
  list: async (): Promise<AuthorSummary[]> => {
    const response = await apiClient.get<AuthorSummary[]>('/authors/');
    return handleApiResponse(response);
  },

  get: async (username: string): Promise<AuthorSummary> => {
    const response = await apiClient.get<AuthorSummary>(
      `/authors/${username}`
    );
    return handleApiResponse(response);
  },
};
