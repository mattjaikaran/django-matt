import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useProfile, useUpdateProfile } from '@/hooks/use-auth';
import { useAuth } from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { User, Mail, Phone, FileText, Camera } from 'lucide-react';

export const Route = createFileRoute('/profile')({
  component: ProfilePage,
});

const profileSchema = z.object({
  firstName: z.string().optional(),
  lastName: z.string().optional(),
  username: z.string().min(3, 'Username must be at least 3 characters').optional(),
  bio: z.string().max(300, 'Bio too long').optional(),
  phone: z.string().optional(),
  avatarUrl: z.string().url('Must be a valid URL').optional().or(z.literal('')),
});
type ProfileFormData = z.infer<typeof profileSchema>;

function ProfilePage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { data: profile, isLoading } = useProfile();
  const updateProfile = useUpdateProfile();

  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ to: '/auth/login' });
    }
  }, [isAuthenticated, navigate]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
  });

  useEffect(() => {
    if (profile) {
      reset({
        firstName: profile.firstName ?? '',
        lastName: profile.lastName ?? '',
        username: profile.username ?? '',
        bio: profile.bio ?? '',
        phone: profile.phone ?? '',
        avatarUrl: profile.avatarUrl ?? '',
      });
    }
  }, [profile, reset]);

  function onSubmit(data: ProfileFormData) {
    updateProfile.mutate(data);
  }

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">Profile Settings</h1>

        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-24 rounded-xl" />
            <Skeleton className="h-64 rounded-xl" />
          </div>
        ) : (
          <>
            {/* Avatar Preview */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 flex items-center gap-4">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex-shrink-0 overflow-hidden flex items-center justify-center">
                {profile?.avatarUrl ? (
                  <img
                    src={profile.avatarUrl}
                    alt={profile.username}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <User className="w-8 h-8 text-slate-300" />
                )}
              </div>
              <div>
                <p className="font-semibold text-slate-900">
                  {profile?.firstName && profile?.lastName
                    ? `${profile.firstName} ${profile.lastName}`
                    : profile?.username}
                </p>
                <p className="text-sm text-slate-500">{profile?.email}</p>
              </div>
            </div>

            {/* Profile Form */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="font-semibold text-slate-900 mb-5">Personal Information</h2>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="firstName">
                      <User className="w-3.5 h-3.5 inline mr-1" />
                      First Name
                    </Label>
                    <Input
                      id="firstName"
                      {...register('firstName')}
                      className="mt-1"
                      placeholder="Jane"
                    />
                  </div>
                  <div>
                    <Label htmlFor="lastName">Last Name</Label>
                    <Input
                      id="lastName"
                      {...register('lastName')}
                      className="mt-1"
                      placeholder="Doe"
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    {...register('username')}
                    className="mt-1"
                    placeholder="janedoe"
                  />
                  {errors.username && (
                    <p className="text-red-500 text-xs mt-1">{errors.username.message}</p>
                  )}
                </div>

                <div>
                  <Label htmlFor="bio">
                    <FileText className="w-3.5 h-3.5 inline mr-1" />
                    Bio
                  </Label>
                  <Textarea
                    id="bio"
                    {...register('bio')}
                    rows={3}
                    className="mt-1"
                    placeholder="Tell us a bit about yourself..."
                  />
                  {errors.bio && (
                    <p className="text-red-500 text-xs mt-1">{errors.bio.message}</p>
                  )}
                </div>

                <div>
                  <Label htmlFor="phone">
                    <Phone className="w-3.5 h-3.5 inline mr-1" />
                    Phone
                  </Label>
                  <Input
                    id="phone"
                    {...register('phone')}
                    className="mt-1"
                    placeholder="+1 (555) 000-0000"
                    type="tel"
                  />
                </div>

                <div>
                  <Label htmlFor="avatarUrl">
                    <Camera className="w-3.5 h-3.5 inline mr-1" />
                    Avatar URL
                  </Label>
                  <Input
                    id="avatarUrl"
                    {...register('avatarUrl')}
                    className="mt-1"
                    placeholder="https://example.com/avatar.jpg"
                  />
                  {errors.avatarUrl && (
                    <p className="text-red-500 text-xs mt-1">{errors.avatarUrl.message}</p>
                  )}
                </div>

                <div className="pt-2">
                  <Button
                    type="submit"
                    className="bg-indigo-600 hover:bg-indigo-700"
                    disabled={!isDirty || updateProfile.isPending}
                  >
                    {updateProfile.isPending ? 'Saving...' : 'Save Changes'}
                  </Button>
                </div>
              </form>
            </div>

            {/* Account Info (read-only) */}
            <div className="bg-white rounded-xl border border-slate-200 p-6 mt-4">
              <h2 className="font-semibold text-slate-900 mb-4">Account Information</h2>
              <Separator className="mb-4" />
              <div className="space-y-3">
                <div className="flex items-center gap-3 text-sm">
                  <Mail className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <div>
                    <p className="text-slate-500 text-xs">Email</p>
                    <p className="font-medium text-slate-900">{profile?.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <User className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  <div>
                    <p className="text-slate-500 text-xs">Member since</p>
                    <p className="font-medium text-slate-900">
                      {profile?.dateJoined
                        ? new Date(profile.dateJoined).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'long',
                          })
                        : '—'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
