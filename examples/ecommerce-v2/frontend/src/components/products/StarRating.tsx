import { cn } from '@/lib/utils';
import { Star } from 'lucide-react';

interface StarRatingProps {
  rating: number;
  maxRating?: number;
  size?: 'sm' | 'md';
  interactive?: boolean;
  onRate?: (rating: number) => void;
}

export function StarRating({ rating, maxRating = 5, size = 'md', interactive, onRate }: StarRatingProps) {
  const stars = Array.from({ length: maxRating }, (_, i) => i + 1);
  const iconSize = size === 'sm' ? 'h-3 w-3' : 'h-5 w-5';

  return (
    <div className="flex items-center gap-0.5">
      {stars.map(star => (
        <Star
          key={star}
          className={cn(
            iconSize,
            star <= rating ? 'fill-yellow-400 text-yellow-400' : 'text-muted-foreground',
            interactive && 'cursor-pointer hover:fill-yellow-400 hover:text-yellow-400 transition-colors'
          )}
          onClick={() => interactive && onRate?.(star)}
        />
      ))}
    </div>
  );
}
