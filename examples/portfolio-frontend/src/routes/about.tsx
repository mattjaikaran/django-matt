import { createFileRoute } from '@tanstack/react-router';
import { useSkills } from '@/hooks/useSkills';
import { useExperience } from '@/hooks/useExperience';
import { SkillBadge } from '@/components/skills/SkillBadge';
import { ExperienceCard } from '@/components/experience/ExperienceCard';
import { Skeleton } from '@/components/ui/skeleton';
import { Github, Linkedin, Globe, User } from 'lucide-react';
import type { Skill } from '@/types';

export const Route = createFileRoute('/about')({
  component: AboutPage,
});

const SKILL_CATEGORY_LABELS: Record<string, string> = {
  frontend: 'Frontend',
  backend: 'Backend',
  devops: 'DevOps',
  database: 'Database',
  mobile: 'Mobile',
  other: 'Other',
};

function AboutPage() {
  const { data: skills = [], isLoading: skillsLoading } = useSkills();
  const { data: experience = [], isLoading: experienceLoading } = useExperience();

  const skillsByCategory = skills.reduce<Record<string, Skill[]>>((acc, skill) => {
    const cat = skill.category;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(skill);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Page header */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-4 py-12">
          <h1 className="text-3xl font-bold mb-1">About</h1>
          <p className="text-muted-foreground">A bit about me, my skills, and my background.</p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-10">
        {/* Profile + bio */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 mb-16">
          {/* Left: avatar + social */}
          <div className="flex flex-col items-center md:items-start gap-4">
            <div className="h-32 w-32 rounded-full bg-gradient-to-br from-indigo-200 to-slate-200 flex items-center justify-center border-4 border-white shadow-md">
              <User className="h-16 w-16 text-slate-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Matt Jaikaran</h2>
              <p className="text-sm text-muted-foreground">Full-Stack Developer</p>
            </div>
            <div className="flex gap-3">
              <a
                href="https://github.com/mattjaikaran"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
                aria-label="GitHub"
              >
                <Github className="h-5 w-5" />
              </a>
              <a
                href="https://linkedin.com/in/mattjaikaran"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
                aria-label="LinkedIn"
              >
                <Linkedin className="h-5 w-5" />
              </a>
              <a
                href="/"
                className="text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Website"
              >
                <Globe className="h-5 w-5" />
              </a>
            </div>
          </div>

          {/* Right: bio */}
          <div className="md:col-span-2">
            <h3 className="text-lg font-semibold mb-3">About me</h3>
            <div className="space-y-3 text-muted-foreground leading-relaxed">
              <p>
                I'm a full-stack developer with experience building production-grade web applications
                using Python (Django, FastAPI), React/TypeScript, and cloud infrastructure.
              </p>
              <p>
                I enjoy working across the entire stack — from API design and database modelling
                to performant, accessible frontend interfaces. I care deeply about developer experience
                and maintainable codebases.
              </p>
              <p>
                Outside of work I contribute to open-source, build side projects, and explore new
                languages and frameworks.
              </p>
            </div>
          </div>
        </div>

        {/* Skills */}
        <div className="mb-16">
          <h2 className="text-2xl font-bold mb-6">Skills</h2>
          {skillsLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={i} className="h-10 rounded-lg" />
              ))}
            </div>
          ) : skills.length > 0 ? (
            <div className="space-y-8">
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
            <p className="text-muted-foreground">No skills listed yet.</p>
          )}
        </div>

        {/* Experience */}
        <div>
          <h2 className="text-2xl font-bold mb-6">Work Experience</h2>
          {experienceLoading ? (
            <div className="space-y-6 max-w-2xl">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-32 rounded-lg" />
              ))}
            </div>
          ) : experience.length > 0 ? (
            <div className="max-w-2xl">
              {experience.map((exp) => (
                <ExperienceCard key={exp.id} experience={exp} />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">No experience listed yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
