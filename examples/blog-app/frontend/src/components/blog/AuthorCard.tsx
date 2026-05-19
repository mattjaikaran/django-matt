import type { AuthorSummary } from '@/types/blog';
import { Link } from '@tanstack/react-router';
import { User } from 'lucide-react';

interface AuthorCardProps {
  author: AuthorSummary;
  size?: 'sm' | 'md';
}

export function AuthorCard({ author, size = 'md' }: AuthorCardProps) {
  const avatarSize = size === 'sm' ? 'h-8 w-8' : 'h-12 w-12';
  const nameSize = size === 'sm' ? 'text-sm' : 'text-base';

  return (
    <Link
      to={`/authors/${author.username}` as any}
      className="flex items-center gap-3 hover:opacity-80 transition-opacity"
    >
      <div
        className={`${avatarSize} rounded-full bg-muted flex items-center justify-center overflow-hidden flex-shrink-0`}
      >
        {author.avatar ? (
          <img
            src={author.avatar}
            alt={author.fullName}
            className="h-full w-full object-cover"
          />
        ) : (
          <User className="h-4 w-4 text-muted-foreground" />
        )}
      </div>
      <div>
        <p className={`${nameSize} font-medium text-foreground`}>
          {author.fullName}
        </p>
        <p className="text-xs text-muted-foreground">@{author.username}</p>
      </div>
    </Link>
  );
}
