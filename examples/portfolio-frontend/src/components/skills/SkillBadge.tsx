import { cn } from '@/lib/utils';
import type { Skill } from '@/types';

interface SkillBadgeProps {
  skill: Skill;
  className?: string;
}

export function SkillBadge({ skill, className }: SkillBadgeProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 rounded-lg border bg-card px-3 py-2',
        className
      )}
    >
      <span className="text-sm font-medium">{skill.name}</span>
      <div className="flex gap-0.5" aria-label={`Level ${skill.level} of 5`}>
        {Array.from({ length: 5 }).map((_, i) => (
          <span
            key={i}
            className={cn(
              'h-2 w-2 rounded-full',
              i < skill.level ? 'bg-indigo-500' : 'bg-slate-200'
            )}
          />
        ))}
      </div>
    </div>
  );
}
