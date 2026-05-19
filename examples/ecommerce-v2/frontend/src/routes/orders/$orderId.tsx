import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useOrder, useCancelOrder } from '@/hooks/use-orders';
import type { OrderStatus } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { formatPrice, formatDate } from '@/lib/utils';
import {
  Package,
  ChevronLeft,
  MapPin,
  CheckCircle,
  Clock,
  Truck,
  XCircle,
  RefreshCw,
} from 'lucide-react';

export const Route = createFileRoute('/orders/$orderId')({
  component: OrderDetailPage,
});

const STATUS_COLORS: Record<OrderStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  confirmed: 'bg-blue-100 text-blue-700 border-blue-200',
  processing: 'bg-purple-100 text-purple-700 border-purple-200',
  shipped: 'bg-orange-100 text-orange-700 border-orange-200',
  delivered: 'bg-green-100 text-green-700 border-green-200',
  cancelled: 'bg-red-100 text-red-700 border-red-200',
  refunded: 'bg-gray-100 text-gray-700 border-gray-200',
};

const STATUS_TIMELINE: { status: OrderStatus; label: string; icon: React.FC<{ className?: string }> }[] = [
  { status: 'pending', label: 'Order Placed', icon: Clock },
  { status: 'confirmed', label: 'Order Confirmed', icon: CheckCircle },
  { status: 'processing', label: 'Processing', icon: RefreshCw },
  { status: 'shipped', label: 'Shipped', icon: Truck },
  { status: 'delivered', label: 'Delivered', icon: CheckCircle },
];

const STATUS_ORDER = ['pending', 'confirmed', 'processing', 'shipped', 'delivered'];

const CANCELLABLE_STATUSES: OrderStatus[] = ['pending', 'confirmed'];

function OrderDetailPage() {
  const { orderId } = Route.useParams();
  const navigate = useNavigate();
  const { data: order, isLoading } = useOrder(orderId);
  const cancelOrder = useCancelOrder();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="container mx-auto px-4 py-8 max-w-3xl">
          <Skeleton className="h-6 w-32 mb-6" />
          <div className="space-y-4">
            <Skeleton className="h-24 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
            <Skeleton className="h-32 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="container mx-auto px-4 py-20 max-w-3xl text-center">
          <Package className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-600 text-lg">Order not found</p>
          <Link to="/orders">
            <Button variant="outline" className="mt-4">Back to Orders</Button>
          </Link>
        </div>
      </div>
    );
  }

  const isCancellable = CANCELLABLE_STATUSES.includes(order.status);
  const currentStepIndex = STATUS_ORDER.indexOf(order.status);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-4 py-8 max-w-3xl">
        {/* Back */}
        <Link
          to="/orders"
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-6"
        >
          <ChevronLeft className="w-4 h-4" />
          Back to Orders
        </Link>

        {/* Header */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
          <div className="flex items-start justify-between flex-wrap gap-3">
            <div>
              <h1 className="text-xl font-bold text-slate-900">
                Order #{order.id.slice(0, 8).toUpperCase()}
              </h1>
              <p className="text-sm text-slate-500 mt-1">Placed on {formatDate(order.createdAt)}</p>
            </div>
            <div className="flex items-center gap-3">
              <Badge className={`capitalize border ${STATUS_COLORS[order.status]}`}>
                {order.status}
              </Badge>
              {isCancellable && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-red-600 border-red-200 hover:bg-red-50"
                  disabled={cancelOrder.isPending}
                  onClick={() => {
                    cancelOrder.mutate(order.id, {
                      onSuccess: () => navigate({ to: '/orders' }),
                    });
                  }}
                >
                  <XCircle className="w-4 h-4 mr-1" />
                  Cancel Order
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Status Timeline */}
        {order.status !== 'cancelled' && order.status !== 'refunded' && (
          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
            <h2 className="font-semibold text-slate-900 mb-5">Order Status</h2>
            <div className="flex items-start justify-between relative">
              {/* Progress line */}
              <div className="absolute top-4 left-0 right-0 h-0.5 bg-slate-100 z-0">
                <div
                  className="h-full bg-indigo-500 transition-all"
                  style={{
                    width: `${Math.min(100, (currentStepIndex / (STATUS_TIMELINE.length - 1)) * 100)}%`,
                  }}
                />
              </div>

              {STATUS_TIMELINE.map((step, i) => {
                const Icon = step.icon;
                const isDone = i <= currentStepIndex;
                const isCurrent = i === currentStepIndex;
                return (
                  <div key={step.status} className="flex flex-col items-center z-10 flex-1">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center mb-2 transition-colors ${
                        isDone ? 'bg-indigo-600' : 'bg-slate-100'
                      } ${isCurrent ? 'ring-2 ring-indigo-300 ring-offset-2' : ''}`}
                    >
                      <Icon className={`w-4 h-4 ${isDone ? 'text-white' : 'text-slate-400'}`} />
                    </div>
                    <span
                      className={`text-xs text-center leading-tight ${
                        isDone ? 'font-medium text-slate-700' : 'text-slate-400'
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Order Items */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
          <h2 className="font-semibold text-slate-900 mb-4">
            Items ({order.items.length})
          </h2>
          <div className="space-y-4">
            {order.items.map((item) => (
              <div key={item.id} className="flex gap-3">
                <div className="w-14 h-14 bg-slate-100 rounded-lg flex-shrink-0 overflow-hidden">
                  {item.product?.imageUrl ? (
                    <img
                      src={item.product.imageUrl}
                      alt={item.product.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Package className="w-6 h-6 text-slate-300" />
                    </div>
                  )}
                </div>
                <div className="flex-1 flex justify-between items-start">
                  <div>
                    <p className="font-medium text-slate-900">{item.product?.name ?? 'Product'}</p>
                    <p className="text-sm text-slate-500">Qty: {item.quantity}</p>
                    <p className="text-sm text-slate-400">
                      {formatPrice(item.unitPrice)} each
                    </p>
                  </div>
                  <p className="font-semibold text-slate-900">{formatPrice(item.totalPrice)}</p>
                </div>
              </div>
            ))}
          </div>

          <Separator className="my-4" />

          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-slate-600">
              <span>Subtotal</span>
              <span>{formatPrice(order.subtotal)}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Tax</span>
              <span>{formatPrice(order.tax)}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Shipping</span>
              <span>{formatPrice(order.shippingCost)}</span>
            </div>
            <Separator />
            <div className="flex justify-between font-bold text-base text-slate-900">
              <span>Total</span>
              <span>{formatPrice(order.total)}</span>
            </div>
          </div>
        </div>

        {/* Addresses */}
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center gap-2 mb-3">
              <MapPin className="w-4 h-4 text-slate-400" />
              <h3 className="font-semibold text-slate-900 text-sm">Shipping Address</h3>
            </div>
            <p className="text-slate-600 text-sm whitespace-pre-line">{order.shippingAddress}</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center gap-2 mb-3">
              <MapPin className="w-4 h-4 text-slate-400" />
              <h3 className="font-semibold text-slate-900 text-sm">Billing Address</h3>
            </div>
            <p className="text-slate-600 text-sm whitespace-pre-line">{order.billingAddress}</p>
          </div>
        </div>

        {order.notes && (
          <div className="bg-white rounded-xl border border-slate-200 p-5 mt-4">
            <h3 className="font-semibold text-slate-900 text-sm mb-2">Order Notes</h3>
            <p className="text-slate-600 text-sm">{order.notes}</p>
          </div>
        )}
      </div>
    </div>
  );
}
