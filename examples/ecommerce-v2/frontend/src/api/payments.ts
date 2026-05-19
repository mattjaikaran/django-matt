import type { PaymentIntent } from '@/types';
import { api } from './client';

export const paymentsApi = {
  createIntent: async (orderId: string): Promise<PaymentIntent> => {
    const res = await api.post<PaymentIntent>('/payments/create-intent', { orderId });
    return res.data;
  },
};
