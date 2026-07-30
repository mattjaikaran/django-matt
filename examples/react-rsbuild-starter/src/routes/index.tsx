import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/')({
  component: HomePage,
});

function HomePage() {
  return (
    <div className="text-center py-16">
      <h1 className="text-3xl font-bold text-slate-900 mb-4">
        React + RSBuild Starter
      </h1>
      <p className="text-slate-500 mb-8">
        Connected to django-matt API. Built with TanStack Router, React Query, and Tailwind.
      </p>
      <div className="flex gap-4 justify-center">
        <a
          href="/items"
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        >
          View Items →
        </a>
        <a
          href="/api/docs"
          target="_blank"
          className="px-4 py-2 border border-slate-300 rounded-lg hover:bg-slate-100"
          rel="noreferrer"
        >
          API Docs ↗
        </a>
      </div>
    </div>
  );
}
