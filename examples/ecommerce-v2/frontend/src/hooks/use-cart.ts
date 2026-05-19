import { cartApi } from '@/api/cart';
import { useAuth, useCartStore } from '@/lib/store';
import type { AddToCart } from '@/types';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

export const useCart = () => {
  const { isAuthenticated } = useAuth();
  const { setCart } = useCartStore();

  return useQuery({
    queryKey: ['cart'],
    queryFn: async () => {
      const cart = await cartApi.getCart();
      setCart(cart);
      return cart;
    },
    enabled: isAuthenticated,
  });
};

export const useAddToCart = () => {
  const queryClient = useQueryClient();
  const { setCartOpen } = useCartStore();

  return useMutation({
    mutationFn: (data: AddToCart) => cartApi.addItem(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cart'] });
      setCartOpen(true);
      toast.success('Added to cart');
    },
    onError: (error: Error) => toast.error(error.message),
  });
};

export const useUpdateCartItem = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: string; quantity: number }) =>
      cartApi.updateItem(itemId, quantity),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cart'] }),
    onError: (error: Error) => toast.error(error.message),
  });
};

export const useRemoveCartItem = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => cartApi.removeItem(itemId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cart'] }),
    onError: (error: Error) => toast.error(error.message),
  });
};

export const useClearCart = () => {
  const queryClient = useQueryClient();
  const { clearLocalCart } = useCartStore();
  return useMutation({
    mutationFn: cartApi.clearCart,
    onSuccess: () => {
      clearLocalCart();
      queryClient.invalidateQueries({ queryKey: ['cart'] });
    },
  });
};
