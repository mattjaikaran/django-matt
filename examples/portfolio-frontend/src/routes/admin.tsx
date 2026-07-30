import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  Trash2,
  Edit,
  Plus,
  LogOut,
  Shield,
  Loader2,
} from 'lucide-react';

import { useAuthStore } from '@/hooks/useAuth';
import { useProjects } from '@/hooks/useProjects';
import { useSkills } from '@/hooks/useSkills';
import { useExperience } from '@/hooks/useExperience';
import api from '@/lib/api';
import { queryClient } from '@/lib/queryClient';
import { formatDateRange } from '@/lib/utils';
import { cn } from '@/lib/utils';

import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';

import type { Project, Skill, Experience } from '@/types';

// ---------------------------------------------------------------------------
// Route
// ---------------------------------------------------------------------------

export const Route = createFileRoute('/admin')({
  component: AdminPage,
});

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SKILL_CATEGORIES = [
  'frontend',
  'backend',
  'devops',
  'database',
  'mobile',
  'other',
] as const;

// ---------------------------------------------------------------------------
// Project Mutation Hooks
// ---------------------------------------------------------------------------

function useCreateProject() {
  return useMutation({
    mutationFn: async (data: Omit<Project, 'id' | 'created_at' | 'updated_at'>) => {
      const { data: result } = await api.post<Project>('/projects', data);
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      toast.success('Project created');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to create project';
      toast.error(msg);
    },
  });
}

function useUpdateProject() {
  return useMutation({
    mutationFn: async ({ slug, ...data }: Partial<Project> & { slug: string }) => {
      const { data: result } = await api.patch<Project>(`/projects/${slug}`, data);
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      toast.success('Project updated');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to update project';
      toast.error(msg);
    },
  });
}

function useDeleteProject() {
  return useMutation({
    mutationFn: async (slug: string) => {
      await api.delete(`/projects/${slug}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      toast.success('Project deleted');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to delete project';
      toast.error(msg);
    },
  });
}

// ---------------------------------------------------------------------------
// Skill Mutation Hooks
// ---------------------------------------------------------------------------

function useCreateSkill() {
  return useMutation({
    mutationFn: async (data: Omit<Skill, 'id'>) => {
      const { data: result } = await api.post<Skill>('/skills', data);
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] });
      toast.success('Skill created');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to create skill';
      toast.error(msg);
    },
  });
}

function useUpdateSkill() {
  return useMutation({
    mutationFn: async ({ id, ...data }: Partial<Skill> & { id: string }) => {
      const { data: result } = await api.patch<Skill>(`/skills/${id}`, data);
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] });
      toast.success('Skill updated');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to update skill';
      toast.error(msg);
    },
  });
}

function useDeleteSkill() {
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/skills/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] });
      toast.success('Skill deleted');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to delete skill';
      toast.error(msg);
    },
  });
}

// ---------------------------------------------------------------------------
// Experience Mutation Hooks
// ---------------------------------------------------------------------------

function useCreateExperience() {
  return useMutation({
    mutationFn: async (data: Omit<Experience, 'id'>) => {
      const { data: result } = await api.post<Experience>('/experience', data);
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experience'] });
      toast.success('Experience created');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to create experience';
      toast.error(msg);
    },
  });
}

function useUpdateExperience() {
  return useMutation({
    mutationFn: async ({ id, ...data }: Partial<Experience> & { id: string }) => {
      const { data: result } = await api.patch<Experience>(`/experience/${id}`, data);
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experience'] });
      toast.success('Experience updated');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to update experience';
      toast.error(msg);
    },
  });
}

function useDeleteExperience() {
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/experience/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experience'] });
      toast.success('Experience deleted');
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to delete experience';
      toast.error(msg);
    },
  });
}

// ---------------------------------------------------------------------------
// Default form values
// ---------------------------------------------------------------------------

const DEFAULT_PROJECT = {
  title: '',
  slug: '',
  description: '',
  long_description: '',
  tech_stack: [] as string[],
  image_url: '',
  live_url: '',
  github_url: '',
  featured: false,
  order: 0,
  is_published: true,
};

const DEFAULT_SKILL = {
  name: '',
  category: 'other' as string,
  level: 3,
  icon: '',
  order: 0,
};

const DEFAULT_EXPERIENCE = {
  company: '',
  role: '',
  company_url: '',
  location: '',
  start_date: '',
  end_date: '',
  is_current: false,
  description: '',
  tech_used: [] as string[],
};

// ---------------------------------------------------------------------------
// Auth Section (login / register)
// ---------------------------------------------------------------------------

function AuthSection() {
  const { setAuth } = useAuthStore();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);

  const toggleMode = () => setMode((m) => (m === 'login' ? 'register' : 'login'));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/register';
      const payload =
        mode === 'login'
          ? { email, password }
          : { email, password, name };
      const { data } = await api.post<{
        user: { id: string; email: string; name: string; bio?: string; avatar_url?: string; github_url?: string; linkedin_url?: string; website_url?: string; date_joined: string };
        access_token: string;
        refresh_token?: string;
      }>(endpoint, payload);
      setAuth(data.user, data.access_token);
      if (data.refresh_token) {
        localStorage.setItem(
          import.meta.env.VITE_AUTH_REFRESH_TOKEN_KEY || 'refresh_token',
          data.refresh_token
        );
      }
      toast.success(mode === 'login' ? 'Logged in' : 'Account created');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || (mode === 'login' ? 'Login failed' : 'Registration failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <Shield className="mx-auto mb-2 h-10 w-10 text-primary" />
          <CardTitle>{mode === 'login' ? 'Admin Login' : 'Create Admin Account'}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="Your name"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="admin@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {mode === 'login' ? 'Sign In' : 'Register'}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
            <button
              type="button"
              onClick={toggleMode}
              className="text-primary underline underline-offset-4 hover:opacity-80"
            >
              {mode === 'login' ? 'Register' : 'Sign In'}
            </button>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Delete confirmation dialog
// ---------------------------------------------------------------------------

function DeleteConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  title = 'Delete item',
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirm: () => void;
  title?: string;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Are you sure? This action cannot be undone.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              onConfirm();
              onOpenChange(false);
            }}
          >
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ===========================================================================
// MAIN ADMIN PAGE
// ===========================================================================

function AdminPage() {
  const { user, logout } = useAuthStore();

  if (!user) {
    return <AuthSection />;
  }

  return (
    <div className="min-h-screen bg-muted/20">
      {/* Header bar */}
      <header className="sticky top-0 z-40 border-b bg-background">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <Shield className="h-5 w-5 text-primary" />
            <span className="font-semibold">Admin Dashboard</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">{user.email}</span>
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut className="mr-1 h-4 w-4" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8">
        <Tabs defaultValue="projects" className="space-y-6">
          <TabsList className="w-full max-w-md mx-auto grid grid-cols-3">
            <TabsTrigger value="projects">Projects</TabsTrigger>
            <TabsTrigger value="skills">Skills</TabsTrigger>
            <TabsTrigger value="experience">Experience</TabsTrigger>
          </TabsList>

          <TabsContent value="projects">
            <ProjectsTab />
          </TabsContent>

          <TabsContent value="skills">
            <SkillsTab />
          </TabsContent>

          <TabsContent value="experience">
            <ExperienceTab />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

// ===========================================================================
// PROJECTS TAB
// ===========================================================================

function ProjectsTab() {
  const { data: projects = [], isLoading } = useProjects();
  const createProject = useCreateProject();
  const updateProject = useUpdateProject();
  const deleteProject = useDeleteProject();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [deleteSlug, setDeleteSlug] = useState<string | null>(null);

  // Form state
  const [form, setForm] = useState(DEFAULT_PROJECT);

  const openCreate = () => {
    setEditing(null);
    setForm(DEFAULT_PROJECT);
    setDialogOpen(true);
  };

  const openEdit = (p: Project) => {
    setEditing(p);
    setForm({
      title: p.title,
      slug: p.slug,
      description: p.description,
      long_description: p.long_description || '',
      tech_stack: p.tech_stack || [],
      image_url: p.image_url || '',
      live_url: p.live_url || '',
      github_url: p.github_url || '',
      featured: p.featured || false,
      order: (p as Record<string, unknown>).order as number || 0,
      is_published: (p as Record<string, unknown>).is_published as boolean ?? true,
    });
    setDialogOpen(true);
  };

  const openDelete = (slug: string) => {
    setDeleteSlug(slug);
    setDeleteOpen(true);
  };

  const handleSave = async () => {
    const payload = {
      ...form,
      tech_stack: form.tech_stack.length
        ? form.tech_stack.filter(Boolean)
        : [],
    };

    if (editing) {
      await updateProject.mutateAsync({ slug: editing.slug, ...payload });
    } else {
      await createProject.mutateAsync(payload as Omit<Project, 'id' | 'created_at' | 'updated_at'>);
    }
    setDialogOpen(false);
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold">
          Projects ({projects.length})
        </h2>
        <Button onClick={openCreate} size="sm">
          <Plus className="mr-1 h-4 w-4" />
          Add Project
        </Button>
      </div>

      <div className="rounded-md border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Slug</th>
                <th className="px-4 py-3 font-medium">Featured</th>
                <th className="px-4 py-3 font-medium">Published</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {projects.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    No projects yet. Click "Add Project" to create one.
                  </td>
                </tr>
              )}
              {projects.map((p) => (
                <tr key={p.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium">{p.title}</td>
                  <td className="px-4 py-3 text-muted-foreground">{p.slug}</td>
                  <td className="px-4 py-3">
                    {p.featured ? (
                      <Badge variant="default" className="text-xs">Featured</Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {((p as Record<string, unknown>).is_published as boolean) ?? true ? (
                      <Badge variant="secondary" className="text-xs">Published</Badge>
                    ) : (
                      <Badge variant="outline" className="text-xs">Draft</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(p)}>
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => openDelete(p.slug)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Edit project dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit Project' : 'Add Project'}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="p-title">Title</Label>
                <Input
                  id="p-title"
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="p-slug">Slug</Label>
                <Input
                  id="p-slug"
                  value={form.slug}
                  onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-desc">Description</Label>
              <Textarea
                id="p-desc"
                rows={2}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-ldesc">Long Description</Label>
              <Textarea
                id="p-ldesc"
                rows={3}
                value={form.long_description}
                onChange={(e) => setForm((f) => ({ ...f, long_description: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-tech">Tech Stack (comma-separated)</Label>
              <Input
                id="p-tech"
                value={form.tech_stack.join(', ')}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    tech_stack: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                  }))
                }
                placeholder="React, TypeScript, Django"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="p-img">Image URL</Label>
                <Input
                  id="p-img"
                  value={form.image_url}
                  onChange={(e) => setForm((f) => ({ ...f, image_url: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="p-live">Live URL</Label>
                <Input
                  id="p-live"
                  value={form.live_url}
                  onChange={(e) => setForm((f) => ({ ...f, live_url: e.target.value }))}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="p-gh">GitHub URL</Label>
                <Input
                  id="p-gh"
                  value={form.github_url}
                  onChange={(e) => setForm((f) => ({ ...f, github_url: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="p-order">Order</Label>
                <Input
                  id="p-order"
                  type="number"
                  value={form.order}
                  onChange={(e) => setForm((f) => ({ ...f, order: Number(e.target.value) }))}
                />
              </div>
            </div>
            <div className="flex gap-6">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="p-featured"
                  checked={form.featured}
                  onCheckedChange={(c) => setForm((f) => ({ ...f, featured: !!c }))}
                />
                <Label htmlFor="p-featured" className="cursor-pointer text-sm">
                  Featured
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="p-published"
                  checked={form.is_published}
                  onCheckedChange={(c) => setForm((f) => ({ ...f, is_published: !!c }))}
                />
                <Label htmlFor="p-published" className="cursor-pointer text-sm">
                  Published
                </Label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={createProject.isPending || updateProject.isPending}>
              {(createProject.isPending || updateProject.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {editing ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <DeleteConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={() => {
          if (deleteSlug) deleteProject.mutate(deleteSlug);
        }}
        title="Delete project?"
      />
    </div>
  );
}

// ===========================================================================
// SKILLS TAB
// ===========================================================================

function SkillsTab() {
  const { data: skills = [], isLoading } = useSkills();
  const createSkill = useCreateSkill();
  const updateSkill = useUpdateSkill();
  const deleteSkill = useDeleteSkill();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [editing, setEditing] = useState<Skill | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [form, setForm] = useState(DEFAULT_SKILL);

  const openCreate = () => {
    setEditing(null);
    setForm(DEFAULT_SKILL);
    setDialogOpen(true);
  };

  const openEdit = (s: Skill) => {
    setEditing(s);
    setForm({
      name: s.name,
      category: s.category || 'other',
      level: s.level || 3,
      icon: s.icon || '',
      order: s.order || 0,
    });
    setDialogOpen(true);
  };

  const openDelete = (id: string) => {
    setDeleteId(id);
    setDeleteOpen(true);
  };

  const handleSave = async () => {
    if (editing) {
      await updateSkill.mutateAsync({ id: editing.id, ...form });
    } else {
      await createSkill.mutateAsync(form as Omit<Skill, 'id'>);
    }
    setDialogOpen(false);
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold">
          Skills ({skills.length})
        </h2>
        <Button onClick={openCreate} size="sm">
          <Plus className="mr-1 h-4 w-4" />
          Add Skill
        </Button>
      </div>

      <div className="rounded-md border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Level</th>
                <th className="px-4 py-3 font-medium">Order</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {skills.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    No skills yet. Click "Add Skill" to create one.
                  </td>
                </tr>
              )}
              {skills.map((s) => (
                <tr key={s.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium">{s.name}</td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className="text-xs">{s.category}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${(s.level / 5) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground">{s.level}/5</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{s.order}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(s)}>
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => openDelete(s.id)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Edit skill dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit Skill' : 'Add Skill'}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="s-name">Name</Label>
              <Input
                id="s-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Category</Label>
              <Select
                value={form.category}
                onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SKILL_CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c.charAt(0).toUpperCase() + c.slice(1)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="s-level">Level (1-5)</Label>
              <Input
                id="s-level"
                type="number"
                min={1}
                max={5}
                value={form.level}
                onChange={(e) => {
                  const v = Math.min(5, Math.max(1, Number(e.target.value) || 1));
                  setForm((f) => ({ ...f, level: v }));
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="s-icon">Icon</Label>
              <Input
                id="s-icon"
                value={form.icon}
                onChange={(e) => setForm((f) => ({ ...f, icon: e.target.value }))}
                placeholder="e.g. SiReact"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="s-order">Order</Label>
              <Input
                id="s-order"
                type="number"
                value={form.order}
                onChange={(e) => setForm((f) => ({ ...f, order: Number(e.target.value) }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={createSkill.isPending || updateSkill.isPending}>
              {(createSkill.isPending || updateSkill.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {editing ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <DeleteConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={() => {
          if (deleteId) deleteSkill.mutate(deleteId);
        }}
        title="Delete skill?"
      />
    </div>
  );
}

// ===========================================================================
// EXPERIENCE TAB
// ===========================================================================

function ExperienceTab() {
  const { data: experience = [], isLoading } = useExperience();
  const createExp = useCreateExperience();
  const updateExp = useUpdateExperience();
  const deleteExp = useDeleteExperience();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [editing, setEditing] = useState<Experience | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [form, setForm] = useState(DEFAULT_EXPERIENCE);

  // Sort by start_date desc
  const sorted = [...experience].sort((a, b) =>
    new Date(b.start_date).getTime() - new Date(a.start_date).getTime()
  );

  const openCreate = () => {
    setEditing(null);
    setForm(DEFAULT_EXPERIENCE);
    setDialogOpen(true);
  };

  const openEdit = (x: Experience) => {
    setEditing(x);
    setForm({
      company: x.company,
      role: x.role,
      company_url: x.company_url || '',
      location: x.location || '',
      start_date: x.start_date ? x.start_date.slice(0, 10) : '',
      end_date: x.end_date ? x.end_date.slice(0, 10) : '',
      is_current: x.is_current || false,
      description: x.description,
      tech_used: x.tech_used || [],
    });
    setDialogOpen(true);
  };

  const openDelete = (id: string) => {
    setDeleteId(id);
    setDeleteOpen(true);
  };

  const handleSave = async () => {
    const payload = {
      ...form,
      start_date: form.start_date ? new Date(form.start_date).toISOString() : '',
      end_date: form.is_current ? null : (form.end_date ? new Date(form.end_date).toISOString() : null),
      tech_used: form.tech_used.filter(Boolean),
    };

    if (editing) {
      await updateExp.mutateAsync({ id: editing.id, ...payload });
    } else {
      await createExp.mutateAsync(payload as Omit<Experience, 'id'>);
    }
    setDialogOpen(false);
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold">
          Experience ({sorted.length})
        </h2>
        <Button onClick={openCreate} size="sm">
          <Plus className="mr-1 h-4 w-4" />
          Add Experience
        </Button>
      </div>

      <div className="rounded-md border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Dates</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    No experience entries yet. Click "Add Experience" to create one.
                  </td>
                </tr>
              )}
              {sorted.map((x) => (
                <tr key={x.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium">{x.company}</td>
                  <td className="px-4 py-3 text-muted-foreground">{x.role}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">
                    {formatDateRange(x.start_date, x.end_date, x.is_current)}
                  </td>
                  <td className="px-4 py-3">
                    {x.is_current ? (
                      <Badge className="text-xs">Current</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs">Past</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(x)}>
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => openDelete(x.id)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Edit experience dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit Experience' : 'Add Experience'}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="e-company">Company</Label>
                <Input
                  id="e-company"
                  value={form.company}
                  onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="e-role">Role</Label>
                <Input
                  id="e-role"
                  value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="e-url">Company URL</Label>
                <Input
                  id="e-url"
                  value={form.company_url}
                  onChange={(e) => setForm((f) => ({ ...f, company_url: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="e-loc">Location</Label>
                <Input
                  id="e-loc"
                  value={form.location}
                  onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="e-start">Start Date</Label>
                <Input
                  id="e-start"
                  type="date"
                  value={form.start_date}
                  onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="e-end">End Date</Label>
                <Input
                  id="e-end"
                  type="date"
                  value={form.end_date}
                  onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
                  disabled={form.is_current}
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="e-current"
                checked={form.is_current}
                onCheckedChange={(c) => setForm((f) => ({ ...f, is_current: c }))}
              />
              <Label htmlFor="e-current" className="cursor-pointer text-sm">
                I currently work here
              </Label>
            </div>
            <div className="space-y-2">
              <Label htmlFor="e-desc">Description</Label>
              <Textarea
                id="e-desc"
                rows={4}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="e-tech">Tech Used (comma-separated)</Label>
              <Input
                id="e-tech"
                value={form.tech_used.join(', ')}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    tech_used: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                  }))
                }
                placeholder="React, TypeScript, Python"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={createExp.isPending || updateExp.isPending}>
              {(createExp.isPending || updateExp.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {editing ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <DeleteConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={() => {
          if (deleteId) deleteExp.mutate(deleteId);
        }}
        title="Delete experience?"
      />
    </div>
  );
}
