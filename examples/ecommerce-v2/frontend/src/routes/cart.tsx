import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useCart, useUpdateCartItem, useRemoveCartItem, useClearCart } from '@/hooks/use-cart';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { formatPrice } from '@/lib/utils';
import { ShoppingCart, Trash2, Plus, Minus, ArrowRight, Package } from 'lucide-react';

export const Route = createFileRoute('/cart')({
  component: CartPage,
});

function CartPage() {
  const navigate = useNavigate();
  const { data: cart, isLoading } = useCart();
  const updateItem = useUpdateCartItem();
  const removeItem = useRemoveCartItem();
  const clearCart = useClearCart();

  const items = cart?.items ?? [];

  const subtotal = items.reduce((sum, item) => {
    const price = parseFloat(item.product?.price ?? '0');
    return sum + price * item.quantity;
  }, 0);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="container mx-auto px-4 py-8 max-w-4xl">
          <h1 className="text-2xl font-bold text-slate-900 mb-6">Shopping Cart</h1>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="md:col-span-2 space-y-4">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
            </div>
            <Skeleton className="h-48 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="container mx-auto px-4 py-20 max-w-md text-center">
          <ShoppingCart className="w-16 h-16 text-slate-300 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">Your cart is empty</h2>
          <p className="text-slate-500 mb-6">Add some products to get started</p>
          <Link to="/products">
            <Button className="bg-indigo-600 hover:bg-indigo-700 gap-2">
              <ShoppingCart className="w-4 h-4" />
              Browse Products
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-4 py-8 max-w-5xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-slate-900">
            Shopping Cart
            <span className="ml-2 text-base font-normal text-slate-400">
              ({items.length} item{items.length !== 1 ? 's' : ''})
            </span>
          </h1>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => clearCart.mutate()}
            disabled={clearCart.isPending}
            className="text-slate-500 hover:text-red-600"
          >
            <Trash2 className="w-4 h-4 mr-1" />
            Clear All
          </Button>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Items */}
          <div className="md:col-span-2 space-y-3">
            {items.map((item) => (
              <div key={item.id} className="bg-white rounded-xl border border-slate-200 p-4 flex gap-4">
                {/* Product image */}
                <div className="w-20 h-20 bg-slate-100 rounded-lg flex-shrink-0 overflow-hidden">
                  {item.product?.imageUrl ? (
                    <img
                      src={item.product.imageUrl}
                      alt={item.product.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Package className="w-8 h-8 text-slate-300" />
                    </div>
                  )}
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  <Link
                    to="/products/$productId"
                    params={{ productId: item.productId }}
                    className="font-medium text-slate-900 hover:text-indigo-600 truncate block"
                  >
                    {item.product?.name ?? 'Product'}
                  </Link>
                  <p className="text-sm text-slate-500 mt-0.5">
                    {formatPrice(item.product?.price ?? '0')} each
                  </p>

                  <div className="flex items-center justify-between mt-3">
                    {/* Quantity controls */}
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 w-7 p-0"
                        disabled={item.quantity <= 1 || updateItem.isPending}
                        onClick={() => updateItem.mutate({ itemId: item.id, quantity: item.quantity - 1 })}
                      >
                        <Minus className="w-3 h-3" />
                      </Button>
                      <span className="w-8 text-center text-sm font-medium">{item.quantity}</span>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 w-7 p-0"
                        disabled={updateItem.isPending}
                        onClick={() => updateItem.mutate({ itemId: item.id, quantity: item.quantity + 1 })}
                      >
                        <Plus className="w-3 h-3" />
                      </Button>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-slate-900">
                        {formatPrice(parseFloat(item.product?.price ?? '0') * item.quantity)}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-slate-400 hover:text-red-500"
                        onClick={() => removeItem.mutate(item.id)}
                        disabled={removeItem.isPending}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Order Summary */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 h-fit sticky top-4">
            <h2 className="font-bold text-slate-900 text-lg mb-4">Order Summary</h2>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between text-slate-600">
                <span>Subtotal ({items.length} items)</span>
                <span>{formatPrice(subtotal)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Shipping</span>
                <span className="text-green-600">Calculated at checkout</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Tax</span>
                <span className="text-slate-400">Calculated at checkout</span>
              </div>
              <Separator />
              <div className="flex justify-between font-bold text-slate-900 text-base">
                <span>Estimated Total</span>
                <span>{formatPrice(subtotal)}</span>
              </div>
            </div>

            <Button
              className="w-full mt-6 bg-indigo-600 hover:bg-indigo-700 gap-2"
              size="lg"
              onClick={() => navigate({ to: '/checkout' })}
            >
              Proceed to Checkout
              <ArrowRight className="w-4 h-4" />
            </Button>

            <Link to="/products" className="block text-center text-sm text-indigo-600 hover:underline mt-3">
              Continue Shopping
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
