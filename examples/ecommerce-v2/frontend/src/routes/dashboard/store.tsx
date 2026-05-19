import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery } from '@tanstack/react-query';
import { storesApi } from '@/api/stores';
import { useAuth } from '@/lib/store';
import { DashboardLayout } from '@/components/layouts/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { Store, Globe, Image, AlignLeft, Check } from 'lucide-react';
import { slugify } from '@/lib/utils';

export const Route = createFileRoute('/dashboard/store')({
  component: StorePage,
});

const storeSchema = z.object({
  name: z.string().min(2, 'Store name must be at least 2 characters').max(100),
  slug: z.string().min(2, 'Slug must be at least 2 characters').regex(/^[a-z0-9-]+$/, 'Slug can only contain lowercase letters, numbers, and hyphens'),
  description: z.string().max(500, 'Description too long').optional(),
  logoUrl: z.string().url('Must be a valid URL').optional().or(z.literal('')),
});
type StoreFormData = z.infer<typeof storeSchema>;

function StorePage() {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) navigate({ to: '/auth/login' });
  }, [isAuthenticated, navigate]);

  const { data: storesData, isLoading, refetch } = useQuery({
    queryKey: ['stores', 'mine'],
    queryFn: () => storesApi.list({ limit: 1 }),
    enabled: isAuthenticated,
  });

  const existingStore = storesData?.items?.find((s) => s.ownerId === user?.id) ?? null;

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors, isDirty },
  } = useForm<StoreFormData>({
    resolver: zodResolver(storeSchema),
  });

  useEffect(() => {
    if (existingStore) {
      reset({
        name: existingStore.name,
        slug: existingStore.slug,
        description: existingStore.description ?? '',
        logoUrl: existingStore.logoUrl ?? '',
      });
    }
  }, [existingStore, reset]);

  const nameValue = watch('name');

  function handleNameChange(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value;
    setValue('name', val);
    if (!existingStore) {
      setValue('slug', slugify(val), { shouldValidate: true });
    }
  }

  async function onSubmit(data: StoreFormData) {
    try {
      if (existingStore) {
        await storesApi.update(existingStore.id, data);
        toast.success('Store updated successfully');
        setIsEditing(false);
      } else {
        await storesApi.create(data);
        toast.success('Store created successfully');
      }
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Something went wrong');
    }
  }

  if (!isAuthenticated) return null;

  return (
    <DashboardLayout>
      <div className="p-6 max-w-2xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">My Store</h1>
            <p className="text-slate-500 mt-1">Manage your store settings</p>
          </div>
          {existingStore && !isEditing && (
            <Button
              variant="outline"
              onClick={() => setIsEditing(true)}
              className="gap-2"
            >
              Edit Store
            </Button>
          )}
        </div>

        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-20 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
          </div>
        ) : existingStore && !isEditing ? (
          /* Store View */
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            {/* Store header */}
            <div className="p-6 flex items-start gap-4">
              <div className="w-16 h-16 bg-slate-100 rounded-xl flex-shrink-0 flex items-center justify-center overflow-hidden">
                {existingStore.logoUrl ? (
                  <img src={existingStore.logoUrl} alt={existingStore.name} className="w-full h-full object-cover" />
                ) : (
                  <Store className="w-8 h-8 text-slate-300" />
                )}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold text-slate-900">{existingStore.name}</h2>
                  <Badge className={existingStore.isActive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                    {existingStore.isActive ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
                <p className="text-slate-500 text-sm mt-0.5">/{existingStore.slug}</p>
              </div>
            </div>
            <Separator />
            <div className="p-6 space-y-4">
              {existingStore.description && (
                <div>
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Description</p>
                  <p className="text-slate-700">{existingStore.description}</p>
                </div>
              )}
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Rating</p>
                <p className="text-slate-700">{existingStore.rating.toFixed(1)} / 5.0</p>
              </div>
            </div>
          </div>
        ) : (
          /* Create / Edit Form */
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="font-semibold text-slate-900 mb-5">
              {existingStore ? 'Edit Store' : 'Create Your Store'}
            </h2>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <Label htmlFor="name">
                  <Store className="w-3.5 h-3.5 inline mr-1" />
                  Store Name
                </Label>
                <Input
                  id="name"
                  placeholder="My Awesome Store"
                  {...register('name', { onChange: handleNameChange })}
                  className="mt-1"
                />
                {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>}
              </div>

              <div>
                <Label htmlFor="slug">
                  <Globe className="w-3.5 h-3.5 inline mr-1" />
                  URL Slug
                </Label>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-slate-400 text-sm">/store/</span>
                  <Input
                    id="slug"
                    placeholder="my-awesome-store"
                    {...register('slug')}
                  />
                </div>
                {errors.slug && <p className="text-red-500 text-xs mt-1">{errors.slug.message}</p>}
              </div>

              <div>
                <Label htmlFor="description">
                  <AlignLeft className="w-3.5 h-3.5 inline mr-1" />
                  Description
                </Label>
                <Textarea
                  id="description"
                  placeholder="Tell customers about your store..."
                  rows={3}
                  {...register('description')}
                  className="mt-1"
                />
                {errors.description && <p className="text-red-500 text-xs mt-1">{errors.description.message}</p>}
              </div>

              <div>
                <Label htmlFor="logoUrl">
                  <Image className="w-3.5 h-3.5 inline mr-1" />
                  Logo URL
                </Label>
                <Input
                  id="logoUrl"
                  placeholder="https://example.com/logo.png"
                  {...register('logoUrl')}
                  className="mt-1"
                />
                {errors.logoUrl && <p className="text-red-500 text-xs mt-1">{errors.logoUrl.message}</p>}
              </div>

              <div className="flex gap-3 pt-2">
                <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 gap-2">
                  <Check className="w-4 h-4" />
                  {existingStore ? 'Save Changes' : 'Create Store'}
                </Button>
                {existingStore && (
                  <Button type="button" variant="outline" onClick={() => setIsEditing(false)}>
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
