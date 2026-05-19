/**
 * Settings Page
 * User preferences and account settings
 */

import { DashboardLayout } from '@/components/layouts/DashboardLayout';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useChangePassword, useUpdateProfile } from '@/hooks';
import { useAuth } from '@/lib/store';
import { cn } from '@/lib/utils';
import { createFileRoute } from '@tanstack/react-router';
import {
  Bell,
  Globe,
  Key,
  Loader2,
  Palette,
  Save,
  Shield,
  User,
} from 'lucide-react';
import { useState } from 'react';

export const Route = createFileRoute('/settings' as any)({
  component: SettingsPage,
});

type SettingsTab = 'profile' | 'notifications' | 'security' | 'appearance';

const tabs: { id: SettingsTab; label: string; icon: React.ElementType }[] = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'appearance', label: 'Appearance', icon: Palette },
];

function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');
  const { user } = useAuth();
  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();

  // Form states
  const [profileForm, setProfileForm] = useState({
    firstName: user?.firstName || '',
    lastName: user?.lastName || '',
    email: user?.email || '',
  });

  const [passwordForm, setPasswordForm] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const [notifications, setNotifications] = useState({
    emailNotifications: true,
    pushNotifications: true,
    weeklyDigest: false,
    taskReminders: true,
  });

  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateProfile.mutate(profileForm);
  };

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      return; // Show error
    }
    changePassword.mutate({
      currentPassword: passwordForm.currentPassword,
      newPassword: passwordForm.newPassword,
    });
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Page header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Manage your account settings and preferences.
          </p>
        </div>

        <div className="flex flex-col gap-6 lg:flex-row">
          {/* Sidebar navigation */}
          <nav className="shrink-0 lg:w-64">
            <div className="space-y-1 lg:sticky lg:top-24">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
                    activeTab === tab.id
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <tab.icon className="h-5 w-5" />
                  {tab.label}
                </button>
              ))}
            </div>
          </nav>

          {/* Content area */}
          <div className="max-w-2xl flex-1">
            {/* Profile Tab */}
            {activeTab === 'profile' && (
              <Card>
                <CardHeader>
                  <CardTitle>Profile Information</CardTitle>
                  <CardDescription>
                    Update your personal information and email address.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleProfileSubmit} className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="firstName">First Name</Label>
                        <Input
                          id="firstName"
                          value={profileForm.firstName}
                          onChange={e =>
                            setProfileForm(prev => ({
                              ...prev,
                              firstName: e.target.value,
                            }))
                          }
                          placeholder="John"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="lastName">Last Name</Label>
                        <Input
                          id="lastName"
                          value={profileForm.lastName}
                          onChange={e =>
                            setProfileForm(prev => ({
                              ...prev,
                              lastName: e.target.value,
                            }))
                          }
                          placeholder="Doe"
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email</Label>
                      <Input
                        id="email"
                        type="email"
                        value={profileForm.email}
                        onChange={e =>
                          setProfileForm(prev => ({
                            ...prev,
                            email: e.target.value,
                          }))
                        }
                        placeholder="john@example.com"
                      />
                    </div>
                    <Button
                      type="submit"
                      disabled={updateProfile.isPending}
                      className="gap-2"
                    >
                      {updateProfile.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      Save Changes
                    </Button>
                  </form>
                </CardContent>
              </Card>
            )}

            {/* Notifications Tab */}
            {activeTab === 'notifications' && (
              <Card>
                <CardHeader>
                  <CardTitle>Notification Preferences</CardTitle>
                  <CardDescription>
                    Choose how you want to be notified about updates.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {[
                    {
                      id: 'emailNotifications',
                      label: 'Email Notifications',
                      description: 'Receive notifications via email',
                    },
                    {
                      id: 'pushNotifications',
                      label: 'Push Notifications',
                      description: 'Receive push notifications in your browser',
                    },
                    {
                      id: 'weeklyDigest',
                      label: 'Weekly Digest',
                      description: 'Receive a weekly summary of your activity',
                    },
                    {
                      id: 'taskReminders',
                      label: 'Task Reminders',
                      description: 'Get reminded about upcoming due dates',
                    },
                  ].map(item => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between"
                    >
                      <div>
                        <p className="font-medium">{item.label}</p>
                        <p className="text-sm text-muted-foreground">
                          {item.description}
                        </p>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={
                          notifications[item.id as keyof typeof notifications]
                        }
                        onClick={() =>
                          setNotifications(prev => ({
                            ...prev,
                            [item.id]:
                              !prev[item.id as keyof typeof notifications],
                          }))
                        }
                        className={cn(
                          'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors',
                          notifications[item.id as keyof typeof notifications]
                            ? 'bg-primary'
                            : 'bg-muted'
                        )}
                      >
                        <span
                          className={cn(
                            'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow-lg ring-0 transition',
                            notifications[item.id as keyof typeof notifications]
                              ? 'translate-x-5'
                              : 'translate-x-0'
                          )}
                        />
                      </button>
                    </div>
                  ))}
                  <Button className="gap-2">
                    <Save className="h-4 w-4" />
                    Save Preferences
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Security Tab */}
            {activeTab === 'security' && (
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Key className="h-5 w-5" />
                      Change Password
                    </CardTitle>
                    <CardDescription>
                      Update your password to keep your account secure.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <form onSubmit={handlePasswordSubmit} className="space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="currentPassword">
                          Current Password
                        </Label>
                        <Input
                          id="currentPassword"
                          type="password"
                          value={passwordForm.currentPassword}
                          onChange={e =>
                            setPasswordForm(prev => ({
                              ...prev,
                              currentPassword: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="newPassword">New Password</Label>
                        <Input
                          id="newPassword"
                          type="password"
                          value={passwordForm.newPassword}
                          onChange={e =>
                            setPasswordForm(prev => ({
                              ...prev,
                              newPassword: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="confirmPassword">
                          Confirm New Password
                        </Label>
                        <Input
                          id="confirmPassword"
                          type="password"
                          value={passwordForm.confirmPassword}
                          onChange={e =>
                            setPasswordForm(prev => ({
                              ...prev,
                              confirmPassword: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <Button
                        type="submit"
                        disabled={changePassword.isPending}
                        className="gap-2"
                      >
                        {changePassword.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Key className="h-4 w-4" />
                        )}
                        Update Password
                      </Button>
                    </form>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Shield className="h-5 w-5" />
                      Two-Factor Authentication
                    </CardTitle>
                    <CardDescription>
                      Add an extra layer of security to your account.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Status: Not enabled</p>
                        <p className="text-sm text-muted-foreground">
                          Protect your account with 2FA
                        </p>
                      </div>
                      <Button variant="outline">Enable 2FA</Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Appearance Tab */}
            {activeTab === 'appearance' && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Palette className="h-5 w-5" />
                    Appearance
                  </CardTitle>
                  <CardDescription>
                    Customize how the app looks on your device.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div>
                    <Label className="text-base">Theme</Label>
                    <p className="mb-4 text-sm text-muted-foreground">
                      Select your preferred color scheme.
                    </p>
                    <div className="grid grid-cols-3 gap-4">
                      {['light', 'dark', 'system'].map(theme => (
                        <button
                          key={theme}
                          className={cn(
                            'flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-colors',
                            'hover:border-primary/50',
                            'focus:outline-none focus:ring-2 focus:ring-primary'
                          )}
                        >
                          <div
                            className={cn(
                              'h-20 w-full rounded-md',
                              theme === 'light'
                                ? 'border bg-white'
                                : theme === 'dark'
                                  ? 'bg-zinc-900'
                                  : 'bg-gradient-to-r from-white to-zinc-900'
                            )}
                          />
                          <span className="text-sm font-medium capitalize">
                            {theme}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <Label className="flex items-center gap-2 text-base">
                      <Globe className="h-4 w-4" />
                      Language
                    </Label>
                    <p className="mb-4 text-sm text-muted-foreground">
                      Select your preferred language.
                    </p>
                    <select className="w-full rounded-md border bg-background p-2">
                      <option value="en">English</option>
                      <option value="es">Español</option>
                      <option value="fr">Français</option>
                      <option value="de">Deutsch</option>
                    </select>
                  </div>

                  <Button className="gap-2">
                    <Save className="h-4 w-4" />
                    Save Preferences
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
