import { createFileRoute, Link } from '@tanstack/react-router';
import { useProjects } from '@/hooks/useProjects';
import { useSkills } from '@/hooks/useSkills';
import { useExperience } from '@/hooks/useExperience';
import { ProjectGrid } from '@/components/projects/ProjectGrid';
import { SkillBadge } from '@/components/skills/SkillBadge';
import { ExperienceCard } from '@/components/experience/ExperienceCard';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Github, Mail, ArrowRight, Code2, Layers, Briefcase } from 'lucide-react';
import type { Skill } from '@/types';

export const Route = createFileRoute('/')({
  component: HomePage,
});

const SKILL_CATEGORY_LABELS: Record<string, string> = {
  frontend: 'Frontend',
  backend: 'Backend',
  devops: 'DevOps',
  database: 'Database',
  mobile: 'Mobile',
  other: 'Other',
};

function HomePage() {
  const { data: featuredProjects = [], isLoading: projectsLoading } = useProjects({ featured: true });
  const { data: skills = [], isLoading: skillsLoading } = useSkills();
  const { data: recentExperience = [], isLoading: experienceLoading } = useExperience();

  // Group skills by category
  const skillsByCategory = skills.reduce<Record<string, Skill[]>>((acc, skill) => {
    const cat = skill.category;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(skill);
    return acc;
  }, {});

  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-900/40 via-transparent to-transparent" />
        <div className="container mx-auto px-4 py-28 relative z-10">
          <div className="max-w-3xl">
            <Badge className="mb-4 bg-indigo-500/20 text-indigo-300 border-indigo-500/30 hover:bg-indigo-500/30">
              Available for hire
            </Badge>
            <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6 bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
              Hi, I'm a Full-Stack Developer
            </h1>
            <p className="text-lg text-slate-300 mb-8 leading-relaxed max-w-xl">
              Building scalable web applications with Python, Django, React, and TypeScript.
              Passionate about clean code and great developer experiences.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link to="/projects">
                <Button size="lg" className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2">
                  <Layers className="h-5 w-5" />
                  View Projects
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link to="/contact">
                <Button size="lg" variant="outline" className="border-slate-500 text-slate-200 hover:bg-slate-800 hover:text-white gap-2">
                  <Mail className="h-4 w-4" />
                  Contact Me
                </Button>
              </Link>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer">
                <Button size="lg" variant="ghost" className="text-slate-300 hover:text-white hover:bg-slate-700 gap-2">
                  <Github className="h-5 w-5" />
                  GitHub
                </Button>
              </a>
            </div>

            {/* Stats badges */}
            <div className="flex flex-wrap gap-3 mt-10">
              {[
                { label: 'Python', color: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
                { label: 'Django', color: 'bg-green-500/20 text-green-300 border-green-500/30' },
                { label: 'React', color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' },
                { label: 'TypeScript', color: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30' },
              ].map(({ label, color }) => (
                <span
                  key={label}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-mono font-medium ${color}`}
                >
                  <Code2 className="h-3 w-3" />
                  {label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Featured Projects */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">Featured Projects</h2>
              <p className="text-slate-500 mt-1">A selection of my recent work</p>
            </div>
            <Link to="/projects">
              <Button variant="ghost" className="gap-1 text-indigo-600 hover:text-indigo-700">
                View all <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>

          {projectsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-72 rounded-xl" />
              ))}
            </div>
          ) : featuredProjects.length > 0 ? (
            <ProjectGrid projects={featuredProjects} />
          ) : (
            <p className="text-slate-500 text-center py-12">No featured projects yet.</p>
          )}
        </div>
      </section>

      {/* Skills snapshot */}
      <section className="py-16 bg-slate-50">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">Skills</h2>
              <p className="text-slate-500 mt-1">Technologies I work with</p>
            </div>
            <Link to="/about">
              <Button variant="ghost" className="gap-1 text-indigo-600 hover:text-indigo-700">
                Full profile <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>

          {skillsLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-10 rounded-lg" />
              ))}
            </div>
          ) : skills.length > 0 ? (
            <div className="space-y-6">
              {Object.entries(skillsByCategory).map(([category, catSkills]) => (
                <div key={category}>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                    {SKILL_CATEGORY_LABELS[category as Skill['category']] ?? category}
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
                    {catSkills.map((skill) => (
                      <SkillBadge key={skill.id} skill={skill} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-8">No skills listed yet.</p>
          )}
        </div>
      </section>

      {/* Recent Experience */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">Experience</h2>
              <p className="text-slate-500 mt-1">Where I've worked</p>
            </div>
            <Link to="/about">
              <Button variant="ghost" className="gap-1 text-indigo-600 hover:text-indigo-700">
                Full history <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>

          {experienceLoading ? (
            <div className="space-y-6">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-28 rounded-lg" />
              ))}
            </div>
          ) : recentExperience.length > 0 ? (
            <div className="max-w-2xl">
              {recentExperience.map((exp) => (
                <ExperienceCard key={exp.id} experience={exp} />
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-8">No experience listed yet.</p>
          )}
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 bg-indigo-600">
        <div className="container mx-auto px-4 text-center">
          <Briefcase className="h-10 w-10 text-indigo-200 mx-auto mb-4" />
          <h2 className="text-3xl font-bold text-white mb-4">Let's work together</h2>
          <p className="text-indigo-200 mb-8 text-lg max-w-md mx-auto">
            Have a project in mind? I'd love to hear about it.
          </p>
          <Link to="/contact">
            <Button size="lg" className="bg-white text-indigo-600 hover:bg-indigo-50 font-semibold gap-2">
              <Mail className="h-4 w-4" />
              Get in touch
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
