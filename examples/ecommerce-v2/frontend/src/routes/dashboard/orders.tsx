import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useOrders } from '@/hooks/use-orders';
import { ordersApi } from '@/api/orders';
import { useAuth } from '@/lib/store';
import { DashboardLayout } from '@/components/layouts/DashboardLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { formatPrice, formatDate } from '@/lib/utils';
import type { OrderStatus } from '@/types';
import { Package, ChevronDown, ChevronRight, ShoppingBag } from 'lucide-react';

export const Route = createFileRoute('/dashboard/orders')({
  component: DashboardOrdersPage,
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

const ALL_STATUSES: OrderStatus[] = [
  'pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded',
];

const TRANSITION_MAP: Partial<Record<OrderStatus, OrderStatus[]>> = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['processing', 'cancelled'],
  processing: ['shipped'],
  shipped: ['delivered'],
};

function DashboardOrdersPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [expandedOrder, setExpandedOrder] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<OrderStatus | undefined>(undefined);

  useEffect(() => {
    if (!isAuthenticated) navigate({ to: '/auth/login' });
  }, [isAuthenticated, navigate]);

  const { data, isLoading } = useOrders({ status: filterStatus });
  const orders = data?.items ?? [];

  const updateStatusMutation = useMutation({
    mutationFn: ({ orderId, status }: { orderId: string; status: OrderStatus }) =>
      ordersApi.update(orderId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      toast.success('Order status updated');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  if (!isAuthenticated) return null;

  return (
    <DashboardLayout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Orders</h1>
            <p className="text-slate-500 mt-1">Manage your store orders</p>
          </div>

          {/* Filter */}
          <Select
            value={filterStatus ?? 'all'}
            onValueChange={(v) => setFilterStatus(v === 'all' ? undefined : (v as OrderStatus))}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              {ALL_STATUSES.map((s) => (
                <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
          </div>
        ) : orders.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
            <ShoppingBag className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600 font-medium">No orders found</p>
            <p className="text-slate-400 text-sm mt-1">
              {filterStatus ? `No ${filterStatus} orders` : 'Orders will appear here once customers start purchasing'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {orders.map((order) => {
              const isExpanded = expandedOrder === order.id;
              const availableTransitions = TRANSITION_MAP[order.status] ?? [];

              return (
                <div key={order.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  {/* Order Row */}
                  <div
                    className="flex items-center gap-4 p-4 cursor-pointer hover:bg-slate-50 transition-colors"
                    onClick={() => setExpandedOrder(isExpanded ? null : order.id)}
                  >
                    <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Package className="w-5 h-5 text-slate-400" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-semibold text-slate-900">
                          #{order.id.slice(0, 8).toUpperCase()}
                        </p>
                        <Badge className={`text-xs capitalize border ${STATUS_COLORS[order.status]}`}>
                          {order.status}
                        </Badge>
                      </div>
                      <p className="text-sm text-slate-500 mt-0.5">
                        {formatDate(order.createdAt)} &middot; {order.items.length} item{order.items.length !== 1 ? 's' : ''}
                      </p>
                    </div>

                    <div className="flex items-center gap-4">
                      <span className="font-bold text-slate-900">{formatPrice(order.total)}</span>

                      {/* Status update */}
                      {availableTransitions.length > 0 && (
                        <Select
                          value={order.status}
                          onValueChange={(val) => {
                            updateStatusMutation.mutate({ orderId: order.id, status: val as OrderStatus });
                          }}
                          disabled={updateStatusMutation.isPending}
                        >
                          <SelectTrigger
                            className="w-36 text-xs h-8"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={order.status} className="capitalize">{order.status} (current)</SelectItem>
                            {availableTransitions.map((s) => (
                              <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}

                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {/* Expanded: Order Items */}
                  {isExpanded && (
                    <>
                      <Separator />
                      <div className="p-4 bg-slate-50">
                        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">Items</p>
                        <div className="space-y-3">
                          {order.items.map((item) => (
                            <div key={item.id} className="flex items-center gap-3">
                              <div className="w-10 h-10 bg-white rounded-lg border border-slate-200 flex-shrink-0 overflow-hidden flex items-center justify-center">
                                {item.product?.imageUrl ? (
                                  <img src={item.product.imageUrl} alt={item.product.name} className="w-full h-full object-cover" />
                                ) : (
                                  <Package className="w-4 h-4 text-slate-300" />
                                )}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-slate-900 truncate">
                                  {item.product?.name ?? 'Product'}
                                </p>
                                <p className="text-xs text-slate-500">
                                  Qty: {item.quantity} × {formatPrice(item.unitPrice)}
                                </p>
                              </div>
                              <p className="text-sm font-semibold text-slate-900">{formatPrice(item.totalPrice)}</p>
                            </div>
                          ))}
                        </div>

                        <Separator className="my-3" />

                        <div className="flex items-center justify-between text-sm">
                          <span className="text-slate-600">Order Total</span>
                          <span className="font-bold text-slate-900">{formatPrice(order.total)}</span>
                        </div>

                        <div className="mt-3">
                          <Link
                            to="/orders/$orderId"
                            params={{ orderId: order.id }}
                            className="text-indigo-600 text-sm hover:underline"
                          >
                            View full order →
                          </Link>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
