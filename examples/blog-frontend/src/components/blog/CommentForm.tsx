import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useCreateComment } from '@/hooks/use-blog';
import { useAuth } from '@/lib/store';
import { Link } from '@tanstack/react-router';
import { useState } from 'react';

interface CommentFormProps {
  postId: string;
}

export function CommentForm({ postId }: CommentFormProps) {
  const { isAuthenticated } = useAuth();
  const [content, setContent] = useState('');
  const createComment = useCreateComment();

  if (!isAuthenticated) {
    return (
      <p className="text-sm text-muted-foreground">
        <Link to="/auth/login" className="text-primary hover:underline">
          Sign in
        </Link>{' '}
        to leave a comment.
      </p>
    );
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    createComment.mutate(
      { postId, content: content.trim() },
      { onSuccess: () => setContent('') }
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Textarea
        value={content}
        onChange={e => setContent(e.target.value)}
        placeholder="Write a comment…"
        rows={4}
        disabled={createComment.isPending}
      />
      <Button
        type="submit"
        disabled={!content.trim() || createComment.isPending}
      >
        {createComment.isPending ? 'Posting…' : 'Post comment'}
      </Button>
    </form>
  );
}
