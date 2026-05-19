import { createFileRoute, Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useOrders } from '@/hooks/use-orders';
import type { OrderStatus } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { formatPrice, formatDate } from '@/lib/utils';
import { Package, ChevronRight, ShoppingBag } from 'lucide-react';

export const Route = createFileRoute('/orders/')({
  component: OrdersPage,
});

const STATUS_TABS: { label: string; value: OrderStatus | undefined }[] = [
  { label: 'All', value: undefined },
  { label: 'Pending', value: 'pending' },
  { label: 'Processing', value: 'processing' },
  { label: 'Shipped', value: 'shipped' },
  { label: 'Delivered', value: 'delivered' },
  { label: 'Cancelled', value: 'cancelled' },
];

const STATUS_COLORS: Record<OrderStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  confirmed: 'bg-blue-100 text-blue-700 border-blue-200',
  processing: 'bg-purple-100 text-purple-700 border-purple-200',
  shipped: 'bg-orange-100 text-orange-700 border-orange-200',
  delivered: 'bg-green-100 text-green-700 border-green-200',
  cancelled: 'bg-red-100 text-red-700 border-red-200',
  refunded: 'bg-gray-100 text-gray-700 border-gray-200',
};

function StatusBadge({ status }: { status: OrderStatus }) {
  return (
    <Badge className={`capitalize border ${STATUS_COLORS[status]}`}>
      {status}
    </Badge>
  );
}

function OrdersPage() {
  const [activeStatus, setActiveStatus] = useState<OrderStatus | undefined>(undefined);
  const { data, isLoading } = useOrders({ status: activeStatus });

  const orders = data?.items ?? [];

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-4 py-8 max-w-3xl">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">My Orders</h1>

        {/* Status Tabs */}
        <div className="flex gap-2 flex-wrap mb-6">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.label}
              onClick={() => setActiveStatus(tab.value)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                activeStatus === tab.value
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-600'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Orders List */}
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
          </div>
        ) : orders.length === 0 ? (
          <div className="text-center py-20">
            <ShoppingBag className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600 font-medium text-lg">No orders found</p>
            <p className="text-slate-400 mt-1">
              {activeStatus ? `No ${activeStatus} orders` : "You haven't placed any orders yet"}
            </p>
            <Link to="/products">
              <Button className="mt-4 bg-indigo-600 hover:bg-indigo-700">
                Start Shopping
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {orders.map((order) => (
              <Link
                key={order.id}
                to="/orders/$orderId"
                params={{ orderId: order.id }}
                className="block"
              >
                <div className="bg-white rounded-xl border border-slate-200 p-4 hover:border-indigo-300 hover:shadow-sm transition-all">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Package className="w-5 h-5 text-slate-400" />
                      </div>
                      <div>
                        <p className="font-semibold text-slate-900">
                          Order #{order.id.slice(0, 8).toUpperCase()}
                        </p>
                        <p className="text-sm text-slate-500 mt-0.5">
                          {formatDate(order.createdAt)} &middot; {order.items.length} item{order.items.length !== 1 ? 's' : ''}
                        </p>
                        <StatusBadge status={order.status} />
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-slate-900">{formatPrice(order.total)}</span>
                      <ChevronRight className="w-4 h-4 text-slate-400" />
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
