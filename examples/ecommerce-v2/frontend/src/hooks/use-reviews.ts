import { reviewsApi } from '@/api/reviews';
import type { ReviewCreate } from '@/types';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

export const useReviews = (productId: string, params?: { limit?: number; offset?: number }) => useQuery({
  queryKey: ['reviews', productId, params],
  queryFn: () => reviewsApi.list(productId, params),
  enabled: !!productId,
});

export const useReviewSummary = (productId: string) => useQuery({
  queryKey: ['reviews', productId, 'summary'],
  queryFn: () => reviewsApi.getSummary(productId),
  enabled: !!productId,
});

export const useCreateReview = (productId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ReviewCreate) => reviewsApi.create(productId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviews', productId] });
      toast.success('Review submitted');
    },
    onError: (error: Error) => toast.error(error.message),
  });
};
