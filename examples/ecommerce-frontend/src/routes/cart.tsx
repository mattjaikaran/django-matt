import { useState } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import { useCart } from '@/hooks/useCart';
import { Trash2, Minus, Plus, ShoppingCart, ArrowRight, CreditCard, Lock, CheckCircle, Loader2, X } from 'lucide-react';

export const Route = createFileRoute('/cart')({
  component: CartPage,
});

function CartPage() {
  const { items, removeItem, updateQuantity, clearCart, total } = useCart();
  const [showCheckout, setShowCheckout] = useState(false);
  const [checkoutStep, setCheckoutStep] = useState<'summary' | 'processing' | 'confirmed'>('summary');

  if (items.length === 0) {
    return (
      <div className="text-center py-16">
        <ShoppingCart className="w-16 h-16 text-slate-300 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Your Cart is Empty</h1>
        <p className="text-slate-500 mb-6">Looks like you haven't added anything yet.</p>
        <Link
          to="/products"
          className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium inline-flex items-center gap-2"
        >
          Browse Products
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Shopping Cart</h1>
        <button
          onClick={clearCart}
          className="text-sm text-red-600 hover:text-red-700 font-medium"
        >
          Clear Cart
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Cart items */}
        <div className="lg:col-span-2 space-y-4">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-xl border p-4 flex gap-4 items-center"
            >
              <div className="w-20 h-20 bg-slate-100 rounded-lg overflow-hidden flex-shrink-0">
                {item.image && (
                  <img src={item.image} alt={item.name} className="w-full h-full object-cover" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-slate-900 truncate">{item.name}</h3>
                <p className="text-sm text-slate-500">${item.price.toFixed(2)} each</p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => updateQuantity(item.id, item.quantity - 1)}
                  className="w-8 h-8 flex items-center justify-center border rounded-lg hover:bg-slate-50"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
                <span className="w-8 text-center font-medium">{item.quantity}</span>
                <button
                  onClick={() => updateQuantity(item.id, item.quantity + 1)}
                  className="w-8 h-8 flex items-center justify-center border rounded-lg hover:bg-slate-50"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>

              <span className="font-semibold text-slate-900 w-20 text-right">
                ${(item.price * item.quantity).toFixed(2)}
              </span>

              <button
                onClick={() => removeItem(item.id)}
                className="text-slate-400 hover:text-red-600 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        {/* Summary */}
        <div className="bg-white rounded-xl border p-6 h-fit sticky top-24">
          <h2 className="text-lg font-bold text-slate-900 mb-4">Order Summary</h2>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-slate-600">
              <span>Subtotal</span>
              <span>${total.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-slate-600">
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

          <button
            onClick={() => { setShowCheckout(true); setCheckoutStep('summary'); }}
            className="mt-6 w-full py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition-colors"
          >
            Proceed to Checkout
          </button>
        </div>
      </div>

      {/* Checkout Modal */}
      {showCheckout && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => {
              if (checkoutStep === 'confirmed') {
                setShowCheckout(false);
                clearCart();
              } else {
                setShowCheckout(false);
              }
            }}
          />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
            {/* Stripe header bar */}
            <div className="bg-[#635BFF] px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-white" />
                <span className="text-white font-semibold text-sm tracking-wide">
                  Checkout powered by Stripe
                </span>
              </div>
              <button
                onClick={() => {
                  setShowCheckout(false);
                  if (checkoutStep === 'confirmed') clearCart();
                }}
                className="text-white/80 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6">
              {checkoutStep === 'summary' && (
                <>
                  <h2 className="text-lg font-bold text-slate-900 mb-4">Order Summary</h2>

                  <div className="space-y-3 max-h-64 overflow-y-auto mb-4">
                    {items.map((item) => (
                      <div key={item.id} className="flex justify-between text-sm">
                        <span className="text-slate-600">
                          {item.name}
                          <span className="text-slate-400 ml-1">×{item.quantity}</span>
                        </span>
                        <span className="font-medium text-slate-900">
                          ${(item.price * item.quantity).toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="border-t pt-4 space-y-2">
                    <div className="flex justify-between text-sm text-slate-600">
                      <span>Subtotal</span>
                      <span>${total.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm text-slate-600">
                      <span>Shipping</span>
                      <span>Free</span>
                    </div>
                    <div className="flex justify-between font-bold text-slate-900 pt-2 border-t">
                      <span>Total</span>
                      <span>${total.toFixed(2)}</span>
                    </div>
                  </div>

                  {/* Stripe payment section */}
                  <div className="mt-6 p-4 bg-[#F6F9FC] rounded-xl border border-[#E6E9EF]">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-6 bg-[#635BFF] rounded flex items-center justify-center">
                        <CreditCard className="w-4 h-4 text-white" />
                      </div>
                      <span className="font-medium text-slate-700 text-sm">Pay with Stripe</span>
                    </div>
                    <div className="space-y-3">
                      <div className="h-10 bg-white rounded-lg border border-slate-200 px-3 flex items-center gap-2">
                        <CreditCard className="w-4 h-4 text-slate-400" />
                        <span className="text-sm text-slate-400">4242 4242 4242 4242</span>
                      </div>
                      <div className="flex gap-3">
                        <div className="flex-1 h-10 bg-white rounded-lg border border-slate-200 px-3 flex items-center">
                          <span className="text-sm text-slate-400">MM / YY</span>
                        </div>
                        <div className="flex-1 h-10 bg-white rounded-lg border border-slate-200 px-3 flex items-center">
                          <span className="text-sm text-slate-400">CVC</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-3 text-xs text-slate-400">
                      <Lock className="w-3 h-3" />
                      <span>Secured by Stripe</span>
                    </div>
                  </div>

                  <button
                    onClick={() => {
                      setCheckoutStep('processing');
                      setTimeout(() => setCheckoutStep('confirmed'), 2000);
                    }}
                    className="mt-4 w-full py-3 bg-[#635BFF] text-white rounded-lg hover:bg-[#4F46E5] font-medium transition-colors"
                  >
                    Pay ${total.toFixed(2)}
                  </button>
                </>
              )}

              {checkoutStep === 'processing' && (
                <div className="py-12 flex flex-col items-center justify-center">
                  <div className="relative mb-6">
                    <div className="w-16 h-16 border-4 border-[#635BFF]/20 rounded-full" />
                    <Loader2 className="w-16 h-16 text-[#635BFF] absolute inset-0 animate-spin p-3" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-900 mb-1">Processing Payment</h3>
                  <p className="text-sm text-slate-500">Please don't close this window...</p>
                  <div className="mt-4 text-xs text-slate-400 flex items-center gap-1">
                    <Lock className="w-3 h-3" />
                    <span>Stripe secure checkout</span>
                  </div>
                </div>
              )}

              {checkoutStep === 'confirmed' && (
                <div className="py-12 flex flex-col items-center justify-center">
                  <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-6">
                    <CheckCircle className="w-8 h-8 text-green-600" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-900 mb-1">Order Confirmed!</h3>
                  <p className="text-sm text-slate-500 text-center">
                    Thank you for your purchase. Your order has been placed successfully.
                  </p>
                  <button
                    onClick={() => {
                      setShowCheckout(false);
                      clearCart();
                    }}
                    className="mt-6 px-8 py-2.5 bg-[#635BFF] text-white rounded-lg hover:bg-[#4F46E5] font-medium transition-colors"
                  >
                    Continue Shopping
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
