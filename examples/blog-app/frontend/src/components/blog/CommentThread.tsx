import { Button } from '@/components/ui/button';
import { useDeleteComment } from '@/hooks/use-blog';
import { useAuth } from '@/lib/store';
import { formatRelativeTime } from '@/lib/utils';
import type { Comment } from '@/types/blog';
import { Trash2, User } from 'lucide-react';

interface CommentThreadProps {
  comments: Comment[];
  postId: string;
}

export function CommentThread({ comments, postId }: CommentThreadProps) {
  const { user, isAuthenticated } = useAuth();
  const deleteComment = useDeleteComment();

  const handleDelete = (id: string) => {
    if (confirm('Delete this comment?')) {
      deleteComment.mutate({ id, postId });
    }
  };

  if (comments.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4">
        No comments yet. Be the first!
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {comments.map(comment => {
        const isOwn = isAuthenticated && user?.id === comment.author.id;
        return (
          <div key={comment.id} className="flex gap-3">
            <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center flex-shrink-0 overflow-hidden">
              {comment.author.avatar ? (
                <img
                  src={comment.author.avatar}
                  alt={comment.author.fullName}
                  className="h-full w-full object-cover"
                />
              ) : (
                <User className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
            <div className="flex-1 rounded-lg bg-muted/50 p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">
                  {comment.author.fullName}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {formatRelativeTime(comment.createdAt)}
                  </span>
                  {isOwn && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() => handleDelete(comment.id)}
                      disabled={deleteComment.isPending}
                      aria-label="Delete comment"
                    >
                      <Trash2 className="h-3 w-3 text-destructive" />
                    </Button>
                  )}
                </div>
              </div>
              <p className="text-sm whitespace-pre-wrap">{comment.content}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
