import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { useAddToCart } from '@/hooks/use-cart';
import { useAuth } from '@/lib/store';
import { formatPrice } from '@/lib/utils';
import type { Product } from '@/types';
import { Link } from '@tanstack/react-router';
import { ShoppingCart } from 'lucide-react';

export function ProductCard({ product }: { product: Product }) {
  const { isAuthenticated } = useAuth();
  const addToCart = useAddToCart();

  return (
    <Card className="overflow-hidden hover:shadow-md transition-shadow">
      <Link to="/products/$productId" params={{ productId: product.id }}>
        <div className="aspect-square bg-muted overflow-hidden">
          {product.imageUrl ? (
            <img src={product.imageUrl} alt={product.name} className="w-full h-full object-cover hover:scale-105 transition-transform" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-muted-foreground">
              <ShoppingCart className="h-12 w-12" />
            </div>
          )}
        </div>
      </Link>
      <CardContent className="p-3">
        <Link to="/products/$productId" params={{ productId: product.id }}>
          <h3 className="font-medium text-sm truncate hover:text-primary transition-colors">{product.name}</h3>
        </Link>
        <div className="flex items-center gap-2 mt-1">
          <span className="font-semibold text-sm">{formatPrice(product.price)}</span>
          {product.compareAtPrice && (
            <span className="text-xs text-muted-foreground line-through">{formatPrice(product.compareAtPrice)}</span>
          )}
        </div>
      </CardContent>
      {isAuthenticated && (
        <CardFooter className="p-3 pt-0">
          <Button
            size="sm"
            className="w-full"
            onClick={() => addToCart.mutate({ productId: product.id, quantity: 1 })}
            disabled={addToCart.isPending}
          >
            <ShoppingCart className="h-4 w-4 mr-1" />
            Add to Cart
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}
