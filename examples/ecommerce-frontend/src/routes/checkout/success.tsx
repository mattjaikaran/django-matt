import { createFileRoute, Link, useSearch } from '@tanstack/react-router';
import { CheckCircle, ArrowRight } from 'lucide-react';

interface CheckoutSuccessSearch {
  order_id?: string;
}

export const Route = createFileRoute('/checkout/success')({
  component: CheckoutSuccessPage,
  validateSearch: (search: Record<string, unknown>): CheckoutSuccessSearch => ({
    order_id: typeof search.order_id === 'string' ? search.order_id : undefined,
  }),
});

function CheckoutSuccessPage() {
  const { order_id } = useSearch({ from: '/checkout/success' });

  return (
    <div className="max-w-md mx-auto py-16 text-center">
      <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <CheckCircle className="w-8 h-8 text-green-600" />
      </div>
      <h1 className="text-2xl font-bold text-slate-900 mb-2">Order Confirmed!</h1>
      <p className="text-slate-500 mb-2">
        Thank you for your purchase. Your order has been placed successfully.
      </p>
      {order_id && (
        <p className="text-sm text-slate-400 mb-6">
          Order reference: <span className="font-mono text-slate-600">{order_id.slice(0, 8)}...</span>
        </p>
      )}
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Link
          to="/orders"
          className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition-colors inline-flex items-center justify-center gap-2"
        >
          View Orders
          <ArrowRight className="w-4 h-4" />
        </Link>
        <Link
          to="/products"
          className="px-6 py-2.5 bg-white border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 font-medium transition-colors"
        >
          Continue Shopping
        </Link>
      </div>
    </div>
  );
}
