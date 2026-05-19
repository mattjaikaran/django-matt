import { authApi } from '@/api/auth';
import { useAuth } from '@/lib/store';
import type { LoginCredentials, RegisterCredentials, User } from '@/types';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

export const useLogin = () => {
  const { login } = useAuth();
  return useMutation({
    mutationFn: (credentials: LoginCredentials) => login(credentials),
    onSuccess: () => toast.success('Welcome back!'),
    onError: (error: Error) => toast.error(error.message),
  });
};

export const useRegister = () => {
  const { register } = useAuth();
  return useMutation({
    mutationFn: (credentials: RegisterCredentials) => register(credentials),
    onSuccess: () => toast.success('Account created!'),
    onError: (error: Error) => toast.error(error.message),
  });
};

export const useLogout = () => {
  const { logout } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => { logout(); queryClient.clear(); },
    onSuccess: () => toast.success('Logged out'),
  });
};

export const useProfile = () => {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ['auth', 'profile'],
    queryFn: authApi.getProfile,
    enabled: isAuthenticated,
  });
};

export const useUpdateProfile = () => {
  const queryClient = useQueryClient();
  const { setUser } = useAuth();
  return useMutation({
    mutationFn: (data: Partial<User>) => authApi.updateProfile(data),
    onSuccess: (user) => {
      setUser(user);
      queryClient.invalidateQueries({ queryKey: ['auth', 'profile'] });
      toast.success('Profile updated');
    },
    onError: (error: Error) => toast.error(error.message),
  });
};
