import { Badge } from '@/components/ui/badge';
import type { Tag } from '@/types/blog';
import { Link } from '@tanstack/react-router';

interface TagBadgeProps {
  tag: Tag;
  variant?: 'default' | 'secondary' | 'outline';
}

export function TagBadge({ tag, variant = 'secondary' }: TagBadgeProps) {
  return (
    <Link to={`/tags/${tag.slug}` as any}>
      <Badge variant={variant} className="cursor-pointer hover:opacity-80">
        {tag.name}
      </Badge>
    </Link>
  );
}
