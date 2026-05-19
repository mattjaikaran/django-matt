import { useCart, useRemoveCartItem, useUpdateCartItem } from '@/hooks/use-cart';
import { useCartStore } from '@/lib/store';
import { formatPrice } from '@/lib/utils';
import type { CartItem } from '@/types';
import { Link } from '@tanstack/react-router';
import { Minus, Plus, ShoppingCart, Trash2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

function CartItemRow({ item }: { item: CartItem }) {
  const updateItem = useUpdateCartItem();
  const removeItem = useRemoveCartItem();

  return (
    <div className="flex items-center gap-3 py-3 border-b last:border-0">
      <div className="w-12 h-12 bg-muted rounded flex-shrink-0 overflow-hidden">
        {item.product?.imageUrl ? (
          <img src={item.product.imageUrl} alt={item.product.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
            <ShoppingCart className="h-5 w-5" />
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{item.product?.name ?? 'Product'}</p>
        <p className="text-sm text-muted-foreground">
          {item.product ? formatPrice(item.product.price) : ''}
        </p>
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => updateItem.mutate({ itemId: item.id, quantity: item.quantity - 1 })}
          disabled={updateItem.isPending}
        >
          <Minus className="h-3 w-3" />
        </Button>
        <span className="text-sm w-6 text-center">{item.quantity}</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => updateItem.mutate({ itemId: item.id, quantity: item.quantity + 1 })}
          disabled={updateItem.isPending}
        >
          <Plus className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-destructive"
          onClick={() => removeItem.mutate(item.id)}
          disabled={removeItem.isPending}
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

export function CartDrawer() {
  const { cart, cartOpen, setCartOpen } = useCartStore();
  const { isLoading } = useCart();

  const total = cart?.items.reduce((sum, item) => {
    const price = item.product ? parseFloat(item.product.price) : 0;
    return sum + price * item.quantity;
  }, 0) ?? 0;

  if (!cartOpen) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/50"
        onClick={() => setCartOpen(false)}
      />
      <div className="fixed right-0 top-0 z-50 h-full w-80 bg-background shadow-xl flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-lg flex items-center gap-2">
            <ShoppingCart className="h-5 w-5" />
            Cart {cart?.itemCount ? `(${cart.itemCount})` : ''}
          </h2>
          <Button variant="ghost" size="icon" onClick={() => setCartOpen(false)}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <p className="text-muted-foreground text-sm text-center py-8">Loading...</p>
          ) : !cart?.items.length ? (
            <div className="text-center py-8">
              <ShoppingCart className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground">Your cart is empty</p>
            </div>
          ) : (
            cart.items.map(item => <CartItemRow key={item.id} item={item} />)
          )}
        </div>

        {!!cart?.items.length && (
          <div className="p-4 border-t space-y-3">
            <div className="flex justify-between font-medium">
              <span>Total</span>
              <span>{formatPrice(total)}</span>
            </div>
            <Button className="w-full" asChild onClick={() => setCartOpen(false)}>
              <Link to="/checkout">Checkout</Link>
            </Button>
          </div>
        )}
      </div>
    </>
  );
}
