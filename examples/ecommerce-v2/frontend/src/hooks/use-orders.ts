import { ordersApi } from '@/api/orders';
import type { OrderCreate, OrderStatus } from '@/types';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

export const useOrders = (params?: { status?: OrderStatus; page?: number }) => useQuery({
  queryKey: ['orders', params],
  queryFn: () => ordersApi.list(params),
});

export const useOrder = (orderId: string) => useQuery({
  queryKey: ['orders', orderId],
  queryFn: () => ordersApi.get(orderId),
  enabled: !!orderId,
});

export const useCreateOrder = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderCreate) => ordersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      queryClient.invalidateQueries({ queryKey: ['cart'] });
      toast.success('Order placed!');
    },
    onError: (error: Error) => toast.error(error.message),
  });
};

export const useCancelOrder = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: string) => ordersApi.cancel(orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      toast.success('Order cancelled');
    },
    onError: (error: Error) => toast.error(error.message),
  });
};
