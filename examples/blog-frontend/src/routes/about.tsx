import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/about')({
  component: AboutPage,
});

function AboutPage() {
  return (
    <div className="page-container">
      <div className="mx-auto max-w-4xl space-y-8">
        <div className="space-y-4 text-center">
          <h1 className="text-4xl font-bold tracking-tight">About</h1>
          <p className="text-xl text-muted-foreground">
            Learn more about this React Vite boilerplate
          </p>
        </div>

        <div className="grid gap-8">
          <div className="card-container p-8">
            <h2 className="mb-4 text-2xl font-semibold">What is this?</h2>
            <p className="leading-relaxed text-muted-foreground">
              This is a modern React application boilerplate built with Vite,
              TypeScript, and a carefully curated set of tools and libraries.
              It's designed to provide a solid foundation for building scalable
              web applications with excellent developer experience and best
              practices built-in.
            </p>
          </div>

          <div className="card-container p-8">
            <h2 className="mb-4 text-2xl font-semibold">Key Features</h2>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <h3 className="mb-2 font-semibold">Development Experience</h3>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  <li>• Hot module replacement with Vite</li>
                  <li>• TypeScript for type safety</li>
                  <li>• ESLint and Prettier for code quality</li>
                  <li>• VS Code settings and extensions</li>
                </ul>
              </div>
              <div>
                <h3 className="mb-2 font-semibold">UI & Styling</h3>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  <li>• Tailwind CSS for styling</li>
                  <li>• Shadcn/ui component library</li>
                  <li>• Dark mode support</li>
                  <li>• Responsive design</li>
                </ul>
              </div>
              <div>
                <h3 className="mb-2 font-semibold">State Management</h3>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  <li>• Zustand for global state</li>
                  <li>• React Query for server state</li>
                  <li>• Form state with React Hook Form</li>
                  <li>• Validation with Zod</li>
                </ul>
              </div>
              <div>
                <h3 className="mb-2 font-semibold">Routing & API</h3>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  <li>• TanStack Router for routing</li>
                  <li>• Axios for HTTP requests</li>
                  <li>• Authentication system</li>
                  <li>• Mock API for development</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="card-container p-8">
            <h2 className="mb-4 text-2xl font-semibold">Architecture</h2>
            <p className="mb-4 leading-relaxed text-muted-foreground">
              The project follows a feature-based architecture with clear
              separation of concerns:
            </p>
            <div className="grid gap-6 text-sm md:grid-cols-2">
              <div>
                <h3 className="mb-2 font-semibold">Folder Structure</h3>
                <ul className="space-y-1 font-mono text-muted-foreground">
                  <li>src/components/ - Reusable UI components</li>
                  <li>src/pages/ - Page components</li>
                  <li>src/forms/ - Form components</li>
                  <li>src/lib/ - Utilities and configurations</li>
                  <li>src/hooks/ - Custom React hooks</li>
                  <li>src/api/ - API layer</li>
                  <li>src/types/ - TypeScript type definitions</li>
                </ul>
              </div>
              <div>
                <h3 className="mb-2 font-semibold">Design Principles</h3>
                <ul className="space-y-1 text-muted-foreground">
                  <li>• Component composition over inheritance</li>
                  <li>• Custom hooks for logic reuse</li>
                  <li>• Type-safe API layer</li>
                  <li>• Consistent error handling</li>
                  <li>• Accessibility best practices</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
