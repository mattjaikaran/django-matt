import { createFileRoute, Link } from '@tanstack/react-router';
import { useProject } from '@/hooks/useProjects';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, ExternalLink, Github } from 'lucide-react';

export const Route = createFileRoute('/projects/$slug')({
  component: ProjectDetailPage,
});

function ProjectDetailPage() {
  const { slug } = Route.useParams();
  const { data: project, isLoading, isError } = useProject(slug);

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-12 max-w-3xl">
        <Skeleton className="h-6 w-32 mb-8" />
        <Skeleton className="h-64 rounded-xl mb-8" />
        <Skeleton className="h-10 w-2/3 mb-4" />
        <Skeleton className="h-4 w-full mb-2" />
        <Skeleton className="h-4 w-full mb-2" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    );
  }

  if (isError || !project) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <h1 className="text-2xl font-bold mb-4">Project not found</h1>
        <p className="text-muted-foreground mb-6">
          The project you're looking for doesn't exist or has been removed.
        </p>
        <Button asChild>
          <Link to="/projects">Back to Projects</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-4 py-10 max-w-3xl">
        {/* Back link */}
        <Link
          to="/projects"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-8 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to projects
        </Link>

        {/* Hero image */}
        {project.image_url ? (
          <div className="rounded-xl overflow-hidden mb-8 border bg-muted">
            <img
              src={project.image_url}
              alt={project.title}
              className="w-full object-cover max-h-80"
            />
          </div>
        ) : (
          <div className="rounded-xl mb-8 border bg-gradient-to-br from-indigo-50 to-slate-100 h-48 flex items-center justify-center">
            <span className="text-6xl text-slate-200 font-mono">{'{}'}</span>
          </div>
        )}

        {/* Title + badges */}
        <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
          <h1 className="text-3xl font-bold">{project.title}</h1>
          <div className="flex gap-2">
            {project.featured && (
              <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200">Featured</Badge>
            )}
          </div>
        </div>

        {/* Short description */}
        <p className="text-lg text-muted-foreground mb-6">{project.description}</p>

        {/* Tech stack */}
        {project.tech_stack.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-8">
            {project.tech_stack.map((tech) => (
              <Badge key={tech} variant="outline">
                {tech}
              </Badge>
            ))}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex flex-wrap gap-3 mb-10">
          {project.live_url && (
            <Button asChild className="gap-2 bg-indigo-600 hover:bg-indigo-700">
              <a href={project.live_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4" />
                Live Demo
              </a>
            </Button>
          )}
          {project.github_url && (
            <Button asChild variant="outline" className="gap-2">
              <a href={project.github_url} target="_blank" rel="noopener noreferrer">
                <Github className="h-4 w-4" />
                View on GitHub
              </a>
            </Button>
          )}
        </div>

        {/* Long description */}
        {project.long_description && (
          <div className="border-t pt-8">
            <h2 className="text-xl font-semibold mb-4">About this project</h2>
            <div className="prose prose-slate max-w-none">
              <p className="whitespace-pre-wrap text-muted-foreground leading-relaxed">
                {project.long_description}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
