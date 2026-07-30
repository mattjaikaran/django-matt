import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';
import {
  PaymentElement,
  useStripe,
  useElements,
} from '@stripe/react-stripe-js';
import { ShoppingCart, Lock, Loader2, ArrowLeft } from 'lucide-react';
import { useCart } from '@/hooks/useCart';
import api from '@/lib/api';

export const Route = createFileRoute('/checkout')({
  component: CheckoutPage,
});

interface ShippingForm {
  firstName: string;
  lastName: string;
  addressLine1: string;
  addressLine2: string;
  city: string;
  state: string;
  postalCode: string;
  country: string;
}

function CheckoutPage() {
  const { items, total } = useCart();

  if (items.length === 0) {
    const navigate = useNavigate();
    return (
      <div className="text-center py-16">
        <ShoppingCart className="w-16 h-16 text-slate-300 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Your Cart is Empty</h1>
        <p className="text-slate-500 mb-6">Add items to your cart before checking out.</p>
        <button
          onClick={() => navigate({ to: '/products' })}
          className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition-colors"
        >
          Browse Products
        </button>
      </div>
    );
  }

  return <CheckoutForm items={items} total={total} />;
}

interface CheckoutFormProps {
  items: { id: string; name: string; price: number; quantity: number }[];
  total: number;
}

function CheckoutForm({ items, total }: CheckoutFormProps) {
  const navigate = useNavigate();
  const stripe = useStripe();
  const elements = useElements();
  const { clearCart } = useCart();

  const [step, setStep] = useState<'shipping' | 'payment' | 'processing'>('shipping');
  const [error, setError] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [orderId, setOrderId] = useState('');
  const [shipping, setShipping] = useState<ShippingForm>({
    firstName: '',
    lastName: '',
    addressLine1: '',
    addressLine2: '',
    city: '',
    state: '',
    postalCode: '',
    country: 'US',
  });

  // Strip context not available (key not configured)
  if (!stripe || !elements) {
    return (
      <div>
        <div className="mb-6">
          <button
            onClick={() => navigate({ to: '/cart' })}
            className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Cart
          </button>
          <h1 className="text-2xl font-bold text-slate-900 mt-2">Checkout</h1>
        </div>
        <div className="bg-white rounded-xl border p-8 text-center">
          <h2 className="text-lg font-bold text-slate-900 mb-2">Payment Not Configured</h2>
          <p className="text-slate-500">
            Stripe publishable key is not set. Please configure{' '}
            <code className="bg-slate-100 px-1.5 py-0.5 rounded text-sm">VITE_STRIPE_PUBLISHABLE_KEY</code>{' '}
            in your <code className="bg-slate-100 px-1.5 py-0.5 rounded text-sm">.env</code> file.
          </p>
        </div>
      </div>
    );
  }

  const handleShippingSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    const { firstName, lastName, addressLine1, addressLine2, city, state: st, postalCode, country } = shipping;

    if (!firstName || !lastName || !addressLine1 || !city || !st || !postalCode) {
      setError('Please fill in all required fields.');
      return;
    }

    try {
      setStep('processing');

      const { data } = await api.post('/orders/checkout', {
        email: '',
        billing_address: {
          first_name: firstName,
          last_name: lastName,
          address_line_1: addressLine1,
          address_line_2: addressLine2,
          city,
          state: st,
          postal_code: postalCode,
          country,
        },
        same_as_billing: true,
      });

      setClientSecret(data.payment_intent_client_secret);
      setOrderId(data.order_id);
      setStep('payment');
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to create order'
          : 'Failed to create order';
      setError(message);
      setStep('shipping');
    }
  };

  const handlePaymentSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) {
      setError('Stripe has not loaded yet. Please try again.');
      return;
    }

    setStep('processing');
    setError('');

    try {
      const { error: submitError } = await elements.submit();
      if (submitError) {
        setError(submitError.message || 'Payment failed');
        setStep('payment');
        return;
      }

      const { error: confirmError } = await stripe.confirmPayment({
        elements,
        clientSecret,
        confirmParams: {
          return_url: `${window.location.origin}/checkout/success?order_id=${orderId}`,
        },
        redirect: 'if_required',
      });

      if (confirmError) {
        setError(confirmError.message || 'Payment failed');
        setStep('payment');
        return;
      }

      // Payment succeeded without redirect
      clearCart();
      navigate({ to: '/checkout/success', search: { order_id: orderId } });
    } catch {
      setError('An unexpected error occurred. Please try again.');
      setStep('payment');
    }
  };

  const updateShipping = (field: keyof ShippingForm, value: string) => {
    setShipping((prev) => ({ ...prev, [field]: value }));
  };

  if (step === 'processing' && !clientSecret) {
    return (
      <div className="max-w-md mx-auto py-16 text-center">
        <Loader2 className="w-12 h-12 text-indigo-600 animate-spin mx-auto mb-4" />
        <h2 className="text-lg font-bold text-slate-900 mb-1">Creating Your Order</h2>
        <p className="text-sm text-slate-500">Please wait while we prepare your checkout...</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <button
          onClick={() => navigate({ to: '/cart' })}
          className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Cart
        </button>
        <h1 className="text-2xl font-bold text-slate-900 mt-2">Checkout</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main checkout form */}
        <div className="lg:col-span-2">
          {/* Progress steps */}
          <div className="flex items-center gap-2 mb-8">
            <div
              className={`flex items-center gap-2 text-sm font-medium ${
                step === 'shipping' ? 'text-indigo-600' : 'text-slate-400'
              }`}
            >
              <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs border ${
                step === 'shipping'
                  ? 'border-indigo-600 bg-indigo-600 text-white'
                  : 'border-slate-300 text-slate-500'
              }`}>
                1
              </span>
              Shipping
            </div>
            <div className="flex-1 h-px bg-slate-200" />
            <div
              className={`flex items-center gap-2 text-sm font-medium ${
                step === 'payment' ? 'text-indigo-600' : 'text-slate-400'
              }`}
            >
              <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs border ${
                step === 'payment'
                  ? 'border-indigo-600 bg-indigo-600 text-white'
                  : 'border-slate-300 text-slate-500'
              }`}>
                2
              </span>
              Payment
            </div>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          {step === 'shipping' && (
            <form onSubmit={handleShippingSubmit} className="bg-white rounded-xl border p-6">
              <h2 className="text-lg font-bold text-slate-900 mb-4">Shipping Address</h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    First Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={shipping.firstName}
                    onChange={(e) => updateShipping('firstName', e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Last Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={shipping.lastName}
                    onChange={(e) => updateShipping('lastName', e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Address Line 1 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={shipping.addressLine1}
                  onChange={(e) => updateShipping('addressLine1', e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  required
                />
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Address Line 2
                </label>
                <input
                  type="text"
                  value={shipping.addressLine2}
                  onChange={(e) => updateShipping('addressLine2', e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    City <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={shipping.city}
                    onChange={(e) => updateShipping('city', e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    State <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={shipping.state}
                    onChange={(e) => updateShipping('state', e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    ZIP Code <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={shipping.postalCode}
                    onChange={(e) => updateShipping('postalCode', e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium text-slate-700 mb-1">Country</label>
                <select
                  value={shipping.country}
                  onChange={(e) => updateShipping('country', e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
                >
                  <option value="US">United States</option>
                  <option value="CA">Canada</option>
                  <option value="GB">United Kingdom</option>
                  <option value="AU">Australia</option>
                </select>
              </div>

              <button
                type="submit"
                className="mt-6 w-full py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition-colors"
              >
                Continue to Payment
              </button>
            </form>
          )}

          {step === 'payment' && (
            <form onSubmit={handlePaymentSubmit} className="bg-white rounded-xl border p-6">
              <h2 className="text-lg font-bold text-slate-900 mb-4">Payment Details</h2>

              <div className="mb-4 p-3 bg-slate-50 rounded-lg text-sm text-slate-600">
                <p className="font-medium text-slate-700">
                  {shipping.firstName} {shipping.lastName}
                </p>
                <p>{shipping.addressLine1}</p>
                {shipping.addressLine2 && <p>{shipping.addressLine2}</p>}
                <p>
                  {shipping.city}, {shipping.state} {shipping.postalCode}
                </p>
                <p>{shipping.country}</p>
              </div>

              {clientSecret ? (
                <PaymentElement
                  options={{
                    layout: 'tabs',
                  }}
                />
              ) : (
                <div className="text-center py-8 text-slate-500">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                  Loading payment form...
                </div>
              )}

              <div className="flex items-center gap-2 mt-4 text-xs text-slate-400">
                <Lock className="w-3 h-3" />
                <span>Payments secured by Stripe</span>
              </div>

              <button
                type="submit"
                disabled={!stripe || !clientSecret || step === 'processing'}
                className="mt-4 w-full py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {step === 'processing' ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  `Pay $${total.toFixed(2)}`
                )}
              </button>
            </form>
          )}
        </div>

        {/* Order summary sidebar */}
        <div className="bg-white rounded-xl border p-6 h-fit sticky top-24">
          <h2 className="text-lg font-bold text-slate-900 mb-4">Order Summary</h2>

          <div className="space-y-3 max-h-64 overflow-y-auto">
            {items.map((item) => (
              <div key={item.id} className="flex justify-between text-sm">
                <span className="text-slate-600">
                  {item.name}
                  <span className="text-slate-400 ml-1">&times;{item.quantity}</span>
                </span>
                <span className="font-medium text-slate-900">
                  ${(item.price * item.quantity).toFixed(2)}
                </span>
              </div>
            ))}
          </div>

          <div className="border-t mt-4 pt-4 space-y-2">
            <div className="flex justify-between text-sm text-slate-600">
              <span>Subtotal</span>
              <span>${total.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm text-slate-600">
              <span>Shipping</span>
              <span>Free</span>
            </div>
          </div>

          <div className="border-t mt-4 pt-4">
            <div className="flex justify-between font-bold text-slate-900 text-lg">
              <span>Total</span>
              <span>${total.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
