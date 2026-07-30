import { createFileRoute } from '@tanstack/react-router';
import { Package } from 'lucide-react';

const MOCK_ORDERS = [
  { id: 'ORD-001', date: '2026-07-28', status: 'delivered', total: 179.98 },
  { id: 'ORD-002', date: '2026-07-25', status: 'shipped', total: 49.99 },
  { id: 'ORD-003', date: '2026-07-20', status: 'processing', total: 214.97 },
  { id: 'ORD-004', date: '2026-07-15', status: 'delivered', total: 89.99 },
  { id: 'ORD-005', date: '2026-07-10', status: 'cancelled', total: 34.99 },
];

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-800',
  processing: 'bg-blue-100 text-blue-800',
  shipped: 'bg-purple-100 text-purple-800',
  delivered: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
};

export const Route = createFileRoute('/orders')({
  component: OrdersPage,
});

function OrdersPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Order History</h1>

      {/* Desktop table */}
      <div className="hidden md:block bg-white rounded-xl border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Order</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
              <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
              <th className="text-right px-6 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {MOCK_ORDERS.map((order) => (
              <tr key={order.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-6 py-4 font-medium text-slate-900">{order.id}</td>
                <td className="px-6 py-4 text-slate-600">{order.date}</td>
                <td className="px-6 py-4">
                  <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[order.status]}`}>
                    {order.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-right font-medium text-slate-900">${order.total.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3">
        {MOCK_ORDERS.map((order) => (
          <div key={order.id} className="bg-white rounded-xl border p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium text-slate-900">{order.id}</span>
              <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[order.status]}`}>
                {order.status}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm text-slate-600">
              <div className="flex items-center gap-1">
                <Package className="w-3.5 h-3.5" />
                {order.date}
              </div>
              <span className="font-medium text-slate-900">${order.total.toFixed(2)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
