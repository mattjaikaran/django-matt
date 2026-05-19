import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  useCategories,
  usePost,
  useTags,
  useUpdatePost,
} from '@/hooks/use-blog';
import { useAuth } from '@/lib/store';
import type { PostUpdate } from '@/types/blog';
import { zodResolver } from '@hookform/resolvers/zod';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { ArrowLeft } from 'lucide-react';
import { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';

export const Route = createFileRoute('/dashboard/edit/$slug')({
  component: EditPostPage,
});

const schema = z.object({
  title: z.string().min(1, 'Title is required'),
  excerpt: z.string().min(1, 'Excerpt is required'),
  content: z.string().min(1, 'Content is required'),
  status: z.enum(['draft', 'published']).default('draft'),
  featured: z.boolean().default(false),
  categoryId: z.string().nullable().default(null),
  tagIds: z.array(z.string()).default([]),
  seoTitle: z.string().optional(),
  seoDescription: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

function EditPostPage() {
  const { slug } = Route.useParams() as { slug: string };
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const { data: post, isLoading } = usePost(slug);
  const updatePost = useUpdatePost();
  const { data: categories = [] } = useCategories();
  const { data: tags = [] } = useTags();

  const {
    register,
    handleSubmit,
    control,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  const tagIds = watch('tagIds') ?? [];

  useEffect(() => {
    if (post) {
      reset({
        title: post.title,
        excerpt: post.excerpt,
        content: post.content,
        status: post.status as 'draft' | 'published',
        featured: post.featured,
        categoryId: post.category?.id ?? null,
        tagIds: post.tags.map(t => t.id),
        seoTitle: post.seoTitle,
        seoDescription: post.seoDescription,
      });
    }
  }, [post, reset]);

  if (!isAuthenticated) {
    navigate({ to: '/auth/login' } as any);
    return null;
  }

  if (isLoading || !post) {
    return (
      <div className="page-container max-w-2xl space-y-6">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const onSubmit = (values: FormValues) => {
    const data: PostUpdate = {
      ...values,
      categoryId: values.categoryId ?? null,
    };
    updatePost.mutate(
      { slug, data },
      {
        onSuccess: updated => {
          navigate({ to: `/posts/${updated.slug}` } as any);
        },
      }
    );
  };

  const toggleTag = (tagId: string) => {
    const next = tagIds.includes(tagId)
      ? tagIds.filter(id => id !== tagId)
      : [...tagIds, tagId];
    setValue('tagIds', next);
  };

  return (
    <div className="page-container max-w-2xl space-y-8">
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to dashboard
      </Link>

      <h1 className="text-3xl font-bold">Edit Post</h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="title">Title</Label>
          <Input id="title" placeholder="Post title" {...register('title')} />
          {errors.title && (
            <p className="text-sm text-destructive">{errors.title.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="excerpt">Excerpt</Label>
          <Textarea
            id="excerpt"
            placeholder="Short description"
            rows={3}
            {...register('excerpt')}
          />
          {errors.excerpt && (
            <p className="text-sm text-destructive">{errors.excerpt.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="content">Content</Label>
          <Textarea
            id="content"
            placeholder="Write your post content here…"
            rows={16}
            {...register('content')}
          />
          {errors.content && (
            <p className="text-sm text-destructive">{errors.content.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label>Category</Label>
          <Controller
            name="categoryId"
            control={control}
            render={({ field }) => (
              <Select
                value={field.value ?? 'none'}
                onValueChange={val => field.onChange(val === 'none' ? null : val)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No category</SelectItem>
                  {categories.map(cat => (
                    <SelectItem key={cat.id} value={cat.id}>
                      {cat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </div>

        <div className="space-y-2">
          <Label>Tags</Label>
          <div className="flex flex-wrap gap-2">
            {tags.map(tag => (
              <button
                key={tag.id}
                type="button"
                onClick={() => toggleTag(tag.id)}
                className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                  tagIds.includes(tag.id)
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'border-input hover:bg-muted'
                }`}
              >
                {tag.name}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <Label>Status</Label>
          <Controller
            name="status"
            control={control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="draft">Draft</SelectItem>
                  <SelectItem value="published">Published</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </div>

        <div className="flex items-center gap-2">
          <Controller
            name="featured"
            control={control}
            render={({ field }) => (
              <input
                type="checkbox"
                id="featured"
                checked={field.value}
                onChange={e => field.onChange(e.target.checked)}
                className="h-4 w-4 rounded border-input accent-primary"
              />
            )}
          />
          <Label htmlFor="featured">Featured post</Label>
        </div>

        <div className="flex gap-3">
          <Button type="submit" disabled={updatePost.isPending}>
            {updatePost.isPending ? 'Saving…' : 'Save changes'}
          </Button>
          <Button variant="outline" asChild>
            <Link to="/dashboard">Cancel</Link>
          </Button>
        </div>

        {updatePost.isError && (
          <p className="text-sm text-destructive">
            Failed to save changes. Please try again.
          </p>
        )}
      </form>
    </div>
  );
}
