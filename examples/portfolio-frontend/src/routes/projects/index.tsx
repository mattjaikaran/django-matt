import { createFileRoute } from '@tanstack/react-router';
import { useProjects } from '@/hooks/useProjects';
import { ProjectGrid } from '@/components/projects/ProjectGrid';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { useState, useMemo } from 'react';
import { Layers, X } from 'lucide-react';

export const Route = createFileRoute('/projects/')({
  component: ProjectsPage,
});

function ProjectsPage() {
  const { data, isLoading } = useProjects();
  const [selectedTech, setSelectedTech] = useState<string | null>(null);

  const projects = data?.items ?? [];

  // Derive unique tech stacks from all projects
  const allTech = useMemo(() => {
    const techSet = new Set<string>();
    projects.forEach((p) => p.tech_stack.forEach((t) => techSet.add(t)));
    return Array.from(techSet).sort();
  }, [projects]);

  const filteredProjects = useMemo(() => {
    if (!selectedTech) return projects;
    return projects.filter((p) => p.tech_stack.includes(selectedTech));
  }, [projects, selectedTech]);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Page header */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-4 py-12">
          <div className="flex items-center gap-3 mb-2">
            <Layers className="h-7 w-7 text-indigo-500" />
            <h1 className="text-3xl font-bold">Projects</h1>
          </div>
          <p className="text-muted-foreground">
            All my open-source and personal projects.
            {data && ` ${data.total} total.`}
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-10">
        {/* Tech filter */}
        {!isLoading && allTech.length > 0 && (
          <div className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
              Filter by technology
            </p>
            <div className="flex flex-wrap gap-2">
              {selectedTech && (
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1 h-7 text-xs"
                  onClick={() => setSelectedTech(null)}
                >
                  <X className="h-3 w-3" /> Clear
                </Button>
              )}
              {allTech.map((tech) => (
                <Badge
                  key={tech}
                  variant={selectedTech === tech ? 'default' : 'outline'}
                  className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors"
                  onClick={() => setSelectedTech(selectedTech === tech ? null : tech)}
                >
                  {tech}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-80 rounded-xl" />
            ))}
          </div>
        ) : (
          <>
            {selectedTech && (
              <p className="text-sm text-muted-foreground mb-4">
                Showing {filteredProjects.length} project{filteredProjects.length !== 1 ? 's' : ''} using{' '}
                <span className="font-medium text-foreground">{selectedTech}</span>
              </p>
            )}
            <ProjectGrid projects={filteredProjects} />
          </>
        )}
      </div>
    </div>
  );
}
