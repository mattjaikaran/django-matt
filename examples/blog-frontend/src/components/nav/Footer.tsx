import { Link } from '@tanstack/react-router';
import { Github, Linkedin, Twitter } from 'lucide-react';

interface FooterProps {
  className?: string;
}

export function Footer({ className }: FooterProps) {
  const currentYear = new Date().getFullYear();

  const navigation = {
    main: [
      { name: 'Home', href: '/' },
      { name: 'About', href: '/about' },
      { name: 'Contact', href: '/contact' },
      { name: 'FAQ', href: '/faq' },
    ],
    legal: [
      { name: 'Privacy Policy', href: '/privacy' },
      { name: 'Terms of Service', href: '/terms' },
    ],
    social: [
      {
        name: 'GitHub',
        href: 'https://github.com',
        icon: Github,
      },
      {
        name: 'Twitter',
        href: 'https://twitter.com',
        icon: Twitter,
      },
      {
        name: 'LinkedIn',
        href: 'https://linkedin.com',
        icon: Linkedin,
      },
    ],
  };

  return (
    <footer className={`border-t bg-background ${className}`}>
      <div className="container mx-auto px-4 py-12 sm:px-6 lg:px-8">
        <div className="xl:grid xl:grid-cols-3 xl:gap-8">
          <div className="space-y-8 xl:col-span-1">
            <div>
              <span className="text-2xl font-bold text-primary">
                React Vite Boilerplate
              </span>
              <p className="mt-2 text-sm text-muted-foreground">
                A modern, scalable React application boilerplate built with
                Vite, TypeScript, and the latest tools.
              </p>
            </div>
            <div className="flex space-x-6">
              {navigation.social.map(item => (
                <a
                  key={item.name}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground transition-colors hover:text-primary"
                >
                  <span className="sr-only">{item.name}</span>
                  <item.icon className="h-6 w-6" />
                </a>
              ))}
            </div>
          </div>

          <div className="mt-12 grid grid-cols-2 gap-8 xl:col-span-2 xl:mt-0">
            <div className="md:grid md:grid-cols-2 md:gap-8">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground">
                  Navigation
                </h3>
                <ul className="mt-4 space-y-4">
                  {navigation.main.map(item => (
                    <li key={item.name}>
                      <Link
                        to={item.href}
                        className="text-base text-muted-foreground transition-colors hover:text-primary"
                      >
                        {item.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="mt-12 md:mt-0">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground">
                  Legal
                </h3>
                <ul className="mt-4 space-y-4">
                  {navigation.legal.map(item => (
                    <li key={item.name}>
                      <Link
                        to={item.href}
                        className="text-base text-muted-foreground transition-colors hover:text-primary"
                      >
                        {item.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="md:grid md:grid-cols-1">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground">
                  Built With
                </h3>
                <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                  <li>React 19 & TypeScript</li>
                  <li>Vite & TanStack Router</li>
                  <li>Tailwind CSS & Shadcn/ui</li>
                  <li>Zustand & React Query</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-12 border-t border-border pt-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between">
            <p className="text-sm text-muted-foreground">
              &copy; {currentYear} React Vite Boilerplate. All rights reserved.
            </p>
            <p className="mt-2 text-sm text-muted-foreground md:mt-0">
              Made by Matt Jaikaran
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
