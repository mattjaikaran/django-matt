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
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { ArrowLeft } from 'lucide-react';
import { useEffect, useState } from 'react';

export const Route = createFileRoute('/dashboard/edit/$slug')({
  component: EditPostPage,
});

function EditPostPage() {
  const { slug } = Route.useParams() as { slug: string };
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const { data: post, isLoading } = usePost(slug);
  const updatePost = useUpdatePost();
  const { data: categories = [] } = useCategories();
  const { data: tags = [] } = useTags();

  const [form, setForm] = useState<PostUpdate>({});
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (post && !initialized) {
      setForm({
        title: post.title,
        excerpt: post.excerpt,
        content: post.content,
        status: post.status,
        featured: post.featured,
        categoryId: post.category?.id ?? null,
        tagIds: post.tags.map(t => t.id),
        seoTitle: post.seoTitle,
        seoDescription: post.seoDescription,
      });
      setInitialized(true);
    }
  }, [post, initialized]);

  if (!isAuthenticated) {
    navigate({ to: '/auth/login' } as any);
    return null;
  }

  if (isLoading || !initialized) {
    return (
      <div className="page-container max-w-2xl space-y-6">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updatePost.mutate(
      { slug, data: form },
      {
        onSuccess: updated => {
          navigate({ to: `/posts/${updated.slug}` } as any);
        },
      }
    );
  };

  const toggleTag = (tagId: string) => {
    setForm(f => ({
      ...f,
      tagIds: f.tagIds?.includes(tagId)
        ? f.tagIds.filter(id => id !== tagId)
        : [...(f.tagIds ?? []), tagId],
    }));
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

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="title">Title</Label>
          <Input
            id="title"
            value={form.title ?? ''}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            placeholder="Post title"
            required
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="excerpt">Excerpt</Label>
          <Textarea
            id="excerpt"
            value={form.excerpt ?? ''}
            onChange={e => setForm(f => ({ ...f, excerpt: e.target.value }))}
            placeholder="Short description"
            rows={3}
            required
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="content">Content</Label>
          <Textarea
            id="content"
            value={form.content ?? ''}
            onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
            placeholder="Write your post content here…"
            rows={16}
            required
          />
        </div>

        <div className="space-y-2">
          <Label>Category</Label>
          <Select
            value={form.categoryId ?? 'none'}
            onValueChange={val =>
              setForm(f => ({ ...f, categoryId: val === 'none' ? null : val }))
            }
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
                  form.tagIds?.includes(tag.id)
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
          <Select
            value={form.status ?? 'draft'}
            onValueChange={val => setForm(f => ({ ...f, status: val }))}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="published">Published</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="featured"
            checked={form.featured ?? false}
            onChange={e => setForm(f => ({ ...f, featured: e.target.checked }))}
            className="h-4 w-4 rounded border-input accent-primary"
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
