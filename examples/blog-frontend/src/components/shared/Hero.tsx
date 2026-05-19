import { Button } from '@/components/ui/button';
import { ArrowRight, Github } from 'lucide-react';

interface HeroProps {
  title?: string;
  subtitle?: string;
  description?: string;
  primaryAction?: {
    label: string;
    href: string;
  };
  secondaryAction?: {
    label: string;
    href: string;
  };
  showGithubStats?: boolean;
}

export function Hero({
  title = 'React Vite Boilerplate',
  subtitle = 'Build faster, ship sooner',
  description = 'A modern, scalable React application boilerplate built with Vite, TypeScript, and the latest development tools.',
  primaryAction = {
    label: 'Get Started',
    href: '/auth/register',
  },
  secondaryAction = {
    label: 'View on GitHub',
    href: 'https://github.com/mattjaikaran/react-vite-boilerplate',
  },
}: HeroProps) {
  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-primary/5 via-background to-secondary/5">
      <div className="container mx-auto px-4 py-24 sm:py-32">
        <div className="space-y-8 text-center">
          {/* Main heading */}
          <div className="space-y-4">
            <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-6xl lg:text-7xl">
              {title}
            </h1>
            <p className="text-xl font-semibold text-primary sm:text-2xl">
              {subtitle}
            </p>
            <p className="mx-auto max-w-3xl text-lg leading-relaxed text-muted-foreground">
              {description}
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="lg" className="group" asChild>
              <a href={primaryAction.href}>
                {primaryAction.label}
                <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
              </a>
            </Button>

            <Button size="lg" variant="outline" className="group" asChild>
              <a
                href={secondaryAction.href}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Github className="mr-2 h-4 w-4" />
                {secondaryAction.label}
              </a>
            </Button>
          </div>

          {/* Feature highlights */}
          <div className="mx-auto grid max-w-4xl grid-cols-1 gap-8 pt-16 md:grid-cols-3">
            <div className="space-y-3 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                <span className="text-2xl">⚡</span>
              </div>
              <h3 className="text-lg font-semibold">Lightning Fast</h3>
              <p className="text-sm text-muted-foreground">
                Built with Vite for instant hot module replacement and optimized
                builds
              </p>
            </div>

            <div className="space-y-3 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                <span className="text-2xl">🎯</span>
              </div>
              <h3 className="text-lg font-semibold">Type Safe</h3>
              <p className="text-sm text-muted-foreground">
                Full TypeScript support with strict type checking and excellent
                DX
              </p>
            </div>

            <div className="space-y-3 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                <span className="text-2xl">🎨</span>
              </div>
              <h3 className="text-lg font-semibold">Beautiful UI</h3>
              <p className="text-sm text-muted-foreground">
                Styled with Tailwind CSS and Shadcn/ui for a modern, accessible
                design
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Background decoration */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="h-[800px] w-[800px] rounded-full bg-gradient-to-r from-primary/20 to-secondary/20 opacity-20 blur-3xl" />
        </div>
      </div>
    </div>
  );
}
