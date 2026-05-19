import { Badge } from '@/components/ui/badge';
import { formatDateRange } from '@/lib/utils';
import type { Experience } from '@/types';
import { MapPin, ExternalLink } from 'lucide-react';

interface ExperienceCardProps {
  experience: Experience;
}

export function ExperienceCard({ experience }: ExperienceCardProps) {
  return (
    <div className="relative flex gap-6">
      {/* Timeline dot */}
      <div className="flex flex-col items-center">
        <div className="mt-1.5 h-3 w-3 rounded-full border-2 border-indigo-500 bg-background shrink-0" />
        <div className="mt-1 flex-1 w-px bg-border" />
      </div>

      <div className="pb-8 flex-1 min-w-0">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-1">
          <div>
            <h3 className="font-semibold text-foreground">{experience.role}</h3>
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground mt-0.5">
              {experience.company_url ? (
                <a
                  href={experience.company_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
                >
                  {experience.company}
                  <ExternalLink className="h-3 w-3" />
                </a>
              ) : (
                <span className="font-medium text-foreground">{experience.company}</span>
              )}
              {experience.location && (
                <>
                  <span>·</span>
                  <span className="flex items-center gap-0.5">
                    <MapPin className="h-3 w-3" />
                    {experience.location}
                  </span>
                </>
              )}
            </div>
          </div>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {formatDateRange(experience.start_date, experience.end_date, experience.is_current)}
          </span>
        </div>

        <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{experience.description}</p>

        {experience.tech_used.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {experience.tech_used.map((tech) => (
              <Badge key={tech} variant="outline" className="text-xs">
                {tech}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
