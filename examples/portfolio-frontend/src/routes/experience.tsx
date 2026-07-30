import { createFileRoute } from '@tanstack/react-router';
import { useExperience } from '@/hooks/useExperience';
import { ExperienceCard } from '@/components/experience/ExperienceCard';
import { Skeleton } from '@/components/ui/skeleton';
import { Briefcase } from 'lucide-react';

export const Route = createFileRoute('/experience')({
  component: ExperiencePage,
});

function ExperiencePage() {
  const { data: experience = [], isLoading, isError, error } = useExperience();

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Page header */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-4 py-12">
          <div className="flex items-center gap-3 mb-1">
            <Briefcase className="h-8 w-8 text-indigo-600" />
            <h1 className="text-3xl font-bold">Experience</h1>
          </div>
          <p className="text-muted-foreground">My professional journey and work history.</p>
        </div>
      </div>

      {/* Timeline */}
      <div className="container mx-auto px-4 py-10">
        {isLoading ? (
          <div className="space-y-6 max-w-2xl">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-32 rounded-lg" />
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-12">
            <p className="text-red-500">Failed to load experience.</p>
            <p className="text-sm text-muted-foreground mt-1">
              {error instanceof Error ? error.message : 'An unexpected error occurred.'}
            </p>
          </div>
        ) : experience.length > 0 ? (
          <div className="max-w-2xl">
            {experience.map((exp) => (
              <ExperienceCard key={exp.id} experience={exp} />
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <Briefcase className="h-12 w-12 text-slate-300 mx-auto mb-3" />
            <p className="text-muted-foreground">No experience listed yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}
