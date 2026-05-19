import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useEffect } from 'react';
import { useOrders } from '@/hooks/use-orders';
import { useAuth } from '@/lib/store';
import { DashboardLayout } from '@/components/layouts/DashboardLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { formatPrice, formatDate } from '@/lib/utils';
import type { OrderStatus } from '@/types';
import {
  ShoppingBag,
  Package,
  TrendingUp,
  ChevronRight,
  Store,
  ArrowRight,
} from 'lucide-react';

export const Route = createFileRoute('/dashboard/')({
  component: DashboardPage,
});

const STATUS_COLORS: Record<OrderStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  confirmed: 'bg-blue-100 text-blue-700',
  processing: 'bg-purple-100 text-purple-700',
  shipped: 'bg-orange-100 text-orange-700',
  delivered: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-700',
  refunded: 'bg-gray-100 text-gray-700',
};

function DashboardPage() {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const { data: ordersData, isLoading: ordersLoading } = useOrders({ page: 1 });

  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ to: '/auth/login' });
    }
  }, [isAuthenticated, navigate]);

  if (!isAuthenticated) return null;

  const orders = ordersData?.items ?? [];
  const totalOrders = ordersData?.total ?? 0;
  const recentOrders = orders.slice(0, 5);

  const totalRevenue = orders
    .filter((o) => o.status === 'delivered')
    .reduce((sum, o) => sum + parseFloat(o.total), 0);

  const pendingOrders = orders.filter((o) => o.status === 'pending').length;

  return (
    <DashboardLayout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">
            Welcome back{user?.firstName ? `, ${user.firstName}` : ''}!
          </h1>
          <p className="text-slate-500 mt-1">Here's what's happening with your account</p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                <ShoppingBag className="w-5 h-5 text-indigo-600" />
              </div>
              <Badge className="bg-indigo-50 text-indigo-700 text-xs">Total</Badge>
            </div>
            <p className="text-2xl font-bold text-slate-900">{totalOrders}</p>
            <p className="text-sm text-slate-500 mt-1">Orders Placed</p>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
                <Package className="w-5 h-5 text-yellow-600" />
              </div>
              <Badge className="bg-yellow-50 text-yellow-700 text-xs">Active</Badge>
            </div>
            <p className="text-2xl font-bold text-slate-900">{pendingOrders}</p>
            <p className="text-sm text-slate-500 mt-1">Pending Orders</p>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-green-600" />
              </div>
              <Badge className="bg-green-50 text-green-700 text-xs">Delivered</Badge>
            </div>
            <p className="text-2xl font-bold text-slate-900">{formatPrice(totalRevenue)}</p>
            <p className="text-sm text-slate-500 mt-1">Total Spent</p>
          </div>
        </div>

        {/* Quick Links */}
        <div className="grid sm:grid-cols-3 gap-3 mb-8">
          <Link to="/dashboard/store">
            <div className="bg-white rounded-xl border border-slate-200 p-4 hover:border-indigo-300 hover:shadow-sm transition-all flex items-center justify-between group">
              <div className="flex items-center gap-3">
                <Store className="w-5 h-5 text-indigo-500" />
                <span className="font-medium text-slate-700">My Store</span>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-500 transition-colors" />
            </div>
          </Link>
          <Link to="/dashboard/products">
            <div className="bg-white rounded-xl border border-slate-200 p-4 hover:border-indigo-300 hover:shadow-sm transition-all flex items-center justify-between group">
              <div className="flex items-center gap-3">
                <Package className="w-5 h-5 text-indigo-500" />
                <span className="font-medium text-slate-700">Products</span>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-500 transition-colors" />
            </div>
          </Link>
          <Link to="/dashboard/orders">
            <div className="bg-white rounded-xl border border-slate-200 p-4 hover:border-indigo-300 hover:shadow-sm transition-all flex items-center justify-between group">
              <div className="flex items-center gap-3">
                <ShoppingBag className="w-5 h-5 text-indigo-500" />
                <span className="font-medium text-slate-700">Orders</span>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-500 transition-colors" />
            </div>
          </Link>
        </div>

        {/* Recent Orders */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-semibold text-slate-900">Recent Orders</h2>
            <Link to="/orders">
              <Button variant="ghost" size="sm" className="gap-1 text-indigo-600 hover:text-indigo-700 text-xs">
                View all <ArrowRight className="w-3 h-3" />
              </Button>
            </Link>
          </div>

          {ordersLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}
            </div>
          ) : recentOrders.length === 0 ? (
            <div className="text-center py-8">
              <ShoppingBag className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-slate-500 text-sm">No orders yet</p>
              <Link to="/products">
                <Button size="sm" className="mt-3 bg-indigo-600 hover:bg-indigo-700">
                  Start Shopping
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {recentOrders.map((order) => (
                <Link
                  key={order.id}
                  to="/orders/$orderId"
                  params={{ orderId: order.id }}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center">
                      <Package className="w-4 h-4 text-slate-400" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-900">
                        #{order.id.slice(0, 8).toUpperCase()}
                      </p>
                      <p className="text-xs text-slate-400">{formatDate(order.createdAt)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge className={`text-xs capitalize ${STATUS_COLORS[order.status]}`}>
                      {order.status}
                    </Badge>
                    <span className="text-sm font-semibold text-slate-900">
                      {formatPrice(order.total)}
                    </span>
                    <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-500 transition-colors" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
