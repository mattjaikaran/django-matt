import {
  authorsApi,
  categoriesApi,
  commentsApi,
  postsApi,
  tagsApi,
} from '@/api/blog';
import type {
  CommentCreate,
  PostCreate,
  PostListParams,
  PostUpdate,
} from '@/types/blog';
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

// ─── Posts ────────────────────────────────────────────────────────────────────

export const usePosts = (params?: PostListParams) => {
  return useQuery({
    queryKey: ['posts', params],
    queryFn: () => postsApi.list(params),
  });
};

export const usePost = (slug: string) => {
  return useQuery({
    queryKey: ['posts', slug],
    queryFn: () => postsApi.get(slug),
    enabled: !!slug,
  });
};

export const useSearchPosts = (q: string) => {
  return useQuery({
    queryKey: ['posts', 'search', q],
    queryFn: () => postsApi.search(q),
    enabled: q.length >= 2,
  });
};

export const useCreatePost = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PostCreate) => postsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] });
    },
  });
};

export const useUpdatePost = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: PostUpdate }) =>
      postsApi.update(slug, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      queryClient.invalidateQueries({ queryKey: ['posts', variables.slug] });
    },
  });
};

export const useDeletePost = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => postsApi.delete(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] });
    },
  });
};

// ─── Tags ─────────────────────────────────────────────────────────────────────

export const useTags = () => {
  return useQuery({
    queryKey: ['tags'],
    queryFn: tagsApi.list,
  });
};

export const useTag = (slug: string) => {
  return useQuery({
    queryKey: ['tags', slug],
    queryFn: () => tagsApi.get(slug),
    enabled: !!slug,
  });
};

// ─── Categories ───────────────────────────────────────────────────────────────

export const useCategories = () => {
  return useQuery({
    queryKey: ['categories'],
    queryFn: categoriesApi.list,
  });
};

export const useCategory = (slug: string) => {
  return useQuery({
    queryKey: ['categories', slug],
    queryFn: () => categoriesApi.get(slug),
    enabled: !!slug,
  });
};

// ─── Comments ─────────────────────────────────────────────────────────────────

export const useComments = (postId: string) => {
  return useQuery({
    queryKey: ['comments', postId],
    queryFn: () => commentsApi.list(postId),
    enabled: !!postId,
  });
};

export const useCreateComment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CommentCreate) => commentsApi.create(data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['comments', variables.postId],
      });
    },
  });
};

export const useDeleteComment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; postId: string }) =>
      commentsApi.delete(id),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['comments', variables.postId],
      });
    },
  });
};

// ─── Authors ──────────────────────────────────────────────────────────────────

export const useAuthors = () => {
  return useQuery({
    queryKey: ['authors'],
    queryFn: authorsApi.list,
  });
};

export const useAuthor = (username: string) => {
  return useQuery({
    queryKey: ['authors', username],
    queryFn: () => authorsApi.get(username),
    enabled: !!username,
  });
};
