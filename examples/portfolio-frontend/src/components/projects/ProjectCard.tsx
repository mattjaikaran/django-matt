import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { Project } from '@/types';
import { Link } from '@tanstack/react-router';
import { ExternalLink, Github, ArrowRight } from 'lucide-react';

interface ProjectCardProps {
  project: Project;
}

export function ProjectCard({ project }: ProjectCardProps) {
  return (
    <Card className="flex flex-col overflow-hidden hover:shadow-md transition-shadow duration-200">
      {project.image_url && (
        <div className="h-48 overflow-hidden bg-muted">
          <img
            src={project.image_url}
            alt={project.title}
            className="h-full w-full object-cover"
          />
        </div>
      )}
      {!project.image_url && (
        <div className="h-48 bg-gradient-to-br from-indigo-50 to-slate-100 flex items-center justify-center">
          <span className="text-4xl text-slate-300 font-mono">{'{}'}</span>
        </div>
      )}

      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-lg leading-snug">{project.title}</CardTitle>
          {project.featured && (
            <Badge className="shrink-0 bg-indigo-100 text-indigo-700 border-indigo-200 hover:bg-indigo-100">
              Featured
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex-1 pb-3">
        <p className="text-sm text-muted-foreground line-clamp-3 mb-4">{project.description}</p>
        <div className="flex flex-wrap gap-1.5">
          {project.tech_stack.slice(0, 5).map((tech) => (
            <Badge key={tech} variant="outline" className="text-xs">
              {tech}
            </Badge>
          ))}
          {project.tech_stack.length > 5 && (
            <Badge variant="outline" className="text-xs text-muted-foreground">
              +{project.tech_stack.length - 5}
            </Badge>
          )}
        </div>
      </CardContent>

      <CardFooter className="gap-2 pt-0 flex-wrap">
        <Button asChild size="sm" variant="ghost" className="gap-1 p-0 h-auto text-indigo-600 hover:text-indigo-700">
          <Link to="/projects/$slug" params={{ slug: project.slug }}>
            View details <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </Button>
        <div className="flex gap-2 ml-auto">
          {project.github_url && (
            <Button asChild size="sm" variant="ghost" className="h-8 w-8 p-0">
              <a href={project.github_url} target="_blank" rel="noopener noreferrer" aria-label="GitHub">
                <Github className="h-4 w-4" />
              </a>
            </Button>
          )}
          {project.live_url && (
            <Button asChild size="sm" variant="ghost" className="h-8 w-8 p-0">
              <a href={project.live_url} target="_blank" rel="noopener noreferrer" aria-label="Live demo">
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}
