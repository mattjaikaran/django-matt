import { createFileRoute, useNavigate, redirect } from '@tanstack/react-router';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useCart } from '@/hooks/use-cart';
import { useCreateOrder } from '@/hooks/use-orders';
import { useAuth } from '@/lib/store';
import { paymentsApi } from '@/api/payments';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { formatPrice } from '@/lib/utils';
import { Package, CreditCard, CheckCircle, ChevronLeft, ChevronRight, AlertCircle } from 'lucide-react';

export const Route = createFileRoute('/checkout')({
  beforeLoad: () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      throw redirect({ to: '/auth/login' });
    }
  },
  component: CheckoutPage,
});

const addressSchema = z.object({
  shippingAddress: z.string().min(10, 'Please enter a complete shipping address'),
  billingAddress: z.string().min(10, 'Please enter a complete billing address'),
  notes: z.string().optional(),
});
type AddressFormData = z.infer<typeof addressSchema>;

type CheckoutStep = 'address' | 'payment' | 'success';

function CheckoutPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [step, setStep] = useState<CheckoutStep>('address');
  const [orderId, setOrderId] = useState<string | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [paymentLoading, setPaymentLoading] = useState(false);

  const { data: cart, isLoading: cartLoading } = useCart();
  const createOrder = useCreateOrder();

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<AddressFormData>({
    resolver: zodResolver(addressSchema),
    defaultValues: { shippingAddress: '', billingAddress: '', notes: '' },
  });

  const items = cart?.items ?? [];
  const subtotal = items.reduce((sum, item) => {
    const price = parseFloat(item.product?.price ?? '0');
    return sum + price * item.quantity;
  }, 0);

  if (!isAuthenticated) {
    navigate({ to: '/auth/login' });
    return null;
  }

  async function onAddressSubmit(data: AddressFormData) {
    if (items.length === 0) return;
    const storeId = items[0]?.product?.storeId;
    if (!storeId) return;

    createOrder.mutate(
      {
        storeId,
        items: items.map((item) => ({
          productId: item.productId,
          variantId: item.variantId,
          quantity: item.quantity,
        })),
        shippingAddress: data.shippingAddress,
        billingAddress: data.billingAddress,
        notes: data.notes,
      },
      {
        onSuccess: (order) => {
          setOrderId(order.id);
          setStep('payment');
        },
      }
    );
  }

  async function handlePayment() {
    if (!orderId) return;
    setPaymentLoading(true);
    setPaymentError(null);
    try {
      await paymentsApi.createIntent(orderId);
      setStep('success');
    } catch (err) {
      setPaymentError(err instanceof Error ? err.message : 'Payment failed. Please try again.');
    } finally {
      setPaymentLoading(false);
    }
  }

  if (cartLoading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="container mx-auto px-4 py-8 max-w-2xl">
          <Skeleton className="h-8 w-48 mb-6" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </div>
    );
  }

  // Step Indicator
  const steps = [
    { id: 'address', label: 'Address', icon: Package },
    { id: 'payment', label: 'Payment', icon: CreditCard },
    { id: 'success', label: 'Confirmed', icon: CheckCircle },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">Checkout</h1>

        {/* Step Indicator */}
        <div className="flex items-center mb-8">
          {steps.map((s, i) => {
            const Icon = s.icon;
            const isActive = s.id === step;
            const isDone = steps.findIndex((x) => x.id === step) > i;
            return (
              <div key={s.id} className="flex items-center">
                <div
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-indigo-600 text-white'
                      : isDone
                      ? 'bg-green-100 text-green-700'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {s.label}
                </div>
                {i < steps.length - 1 && (
                  <ChevronRight className="w-4 h-4 text-slate-300 mx-2" />
                )}
              </div>
            );
          })}
        </div>

        {/* Step 1: Address */}
        {step === 'address' && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-5">Shipping & Billing</h2>

            {/* Order preview */}
            {items.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-slate-500">Your cart is empty.</p>
                <Button variant="outline" onClick={() => navigate({ to: '/products' })} className="mt-3">
                  Browse Products
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit(onAddressSubmit)} className="space-y-5">
                <div className="bg-slate-50 rounded-lg p-4 space-y-2 mb-5">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Order Summary</p>
                  {items.map((item) => (
                    <div key={item.id} className="flex justify-between text-sm">
                      <span className="text-slate-700">
                        {item.product?.name ?? 'Product'} × {item.quantity}
                      </span>
                      <span className="font-medium">
                        {formatPrice(parseFloat(item.product?.price ?? '0') * item.quantity)}
                      </span>
                    </div>
                  ))}
                  <Separator />
                  <div className="flex justify-between font-bold">
                    <span>Total</span>
                    <span>{formatPrice(subtotal)}</span>
                  </div>
                </div>

                <div>
                  <Label htmlFor="shippingAddress">Shipping Address</Label>
                  <Textarea
                    id="shippingAddress"
                    placeholder="123 Main St, Apt 4B&#10;New York, NY 10001&#10;United States"
                    rows={3}
                    {...register('shippingAddress')}
                    className="mt-1"
                  />
                  {errors.shippingAddress && (
                    <p className="text-red-500 text-xs mt-1">{errors.shippingAddress.message}</p>
                  )}
                </div>

                <div>
                  <Label htmlFor="billingAddress">Billing Address</Label>
                  <Textarea
                    id="billingAddress"
                    placeholder="Same as shipping or different billing address"
                    rows={3}
                    {...register('billingAddress')}
                    className="mt-1"
                  />
                  {errors.billingAddress && (
                    <p className="text-red-500 text-xs mt-1">{errors.billingAddress.message}</p>
                  )}
                </div>

                <div>
                  <Label htmlFor="notes">Order Notes (optional)</Label>
                  <Textarea
                    id="notes"
                    placeholder="Special delivery instructions..."
                    rows={2}
                    {...register('notes')}
                    className="mt-1"
                  />
                </div>

                <Button
                  type="submit"
                  className="w-full bg-indigo-600 hover:bg-indigo-700 gap-2"
                  size="lg"
                  disabled={createOrder.isPending}
                >
                  {createOrder.isPending ? 'Placing Order...' : 'Continue to Payment'}
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </form>
            )}
          </div>
        )}

        {/* Step 2: Payment */}
        {step === 'payment' && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-5">Payment</h2>

            <div className="bg-slate-50 rounded-lg p-4 mb-6">
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-600">Order total</span>
                <span className="font-bold text-lg">{formatPrice(subtotal)}</span>
              </div>
              {orderId && (
                <p className="text-xs text-slate-400 mt-1">
                  Order #{orderId.slice(0, 8).toUpperCase()}
                </p>
              )}
            </div>

            {/* Simulated payment form */}
            <div className="border border-dashed border-slate-300 rounded-lg p-6 mb-6 text-center">
              <CreditCard className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-slate-500 text-sm">Stripe payment form would render here</p>
              <p className="text-slate-400 text-xs mt-1">Secured by Stripe</p>
            </div>

            {paymentError && (
              <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
                <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{paymentError}</p>
              </div>
            )}

            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => setStep('address')}
                className="gap-1"
              >
                <ChevronLeft className="w-4 h-4" />
                Back
              </Button>
              <Button
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 gap-2"
                size="lg"
                disabled={paymentLoading}
                onClick={handlePayment}
              >
                <CreditCard className="w-4 h-4" />
                {paymentLoading ? 'Processing...' : `Pay ${formatPrice(subtotal)}`}
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Success */}
        {step === 'success' && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 mb-2">Order Confirmed!</h2>
            <p className="text-slate-500 mb-2">
              Thank you for your purchase. Your order has been placed successfully.
            </p>
            {orderId && (
              <p className="text-sm text-slate-400 mb-6">
                Order ID: <span className="font-mono font-medium text-slate-600">#{orderId.slice(0, 8).toUpperCase()}</span>
              </p>
            )}
            <div className="flex gap-3 justify-center">
              <Button
                onClick={() => navigate({ to: '/orders' })}
                className="bg-indigo-600 hover:bg-indigo-700"
              >
                View My Orders
              </Button>
              <Button variant="outline" onClick={() => navigate({ to: '/products' })}>
                Continue Shopping
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
