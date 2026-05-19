import { createFileRoute, Link } from '@tanstack/react-router';
import { useCategories, useProducts } from '@/hooks/use-products';
import { ProductGrid } from '@/components/products/ProductGrid';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ShoppingBag, ArrowRight, Tag } from 'lucide-react';

export const Route = createFileRoute('/')({
  component: HomePage,
});

function HomePage() {
  const { data: categoriesData, isLoading: categoriesLoading } = useCategories();
  const { data: productsData, isLoading: productsLoading } = useProducts({ limit: 8 });

  const categories = categoriesData?.items?.slice(0, 6) ?? [];
  const products = productsData?.items ?? [];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-900/40 via-transparent to-transparent" />
        <div className="container mx-auto px-4 py-24 relative z-10">
          <div className="max-w-3xl">
            <Badge className="mb-4 bg-indigo-500/20 text-indigo-300 border-indigo-500/30 hover:bg-indigo-500/30">
              New Arrivals Every Week
            </Badge>
            <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6 bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
              Shop the Best Products
            </h1>
            <p className="text-lg text-slate-300 mb-8 leading-relaxed">
              Discover thousands of products from verified sellers. Quality guaranteed,
              fast shipping, and hassle-free returns on every order.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link to="/products">
                <Button size="lg" className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2">
                  <ShoppingBag className="w-5 h-5" />
                  Browse Products
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
              <Link to="/auth/register">
                <Button size="lg" variant="outline" className="border-slate-500 text-slate-200 hover:bg-slate-800 hover:text-white">
                  Create Account
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Categories */}
      <section className="py-16 bg-slate-50">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">Shop by Category</h2>
              <p className="text-slate-500 mt-1">Find exactly what you're looking for</p>
            </div>
            <Link to="/products">
              <Button variant="ghost" className="gap-1 text-indigo-600 hover:text-indigo-700">
                View all <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          </div>

          {categoriesLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-28 rounded-xl" />
              ))}
            </div>
          ) : categories.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
              {categories.map((category) => (
                <Link
                  key={category.id}
                  to="/products"
                  search={{ category: category.slug }}
                  className="group"
                >
                  <div className="bg-white rounded-xl p-4 flex flex-col items-center justify-center gap-2 border border-slate-200 hover:border-indigo-400 hover:shadow-md transition-all duration-200 h-28 cursor-pointer">
                    <Tag className="w-6 h-6 text-indigo-500 group-hover:scale-110 transition-transform" />
                    <span className="text-sm font-medium text-slate-700 text-center leading-tight">
                      {category.name}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-8">No categories available</p>
          )}
        </div>
      </section>

      {/* Featured Products */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">Featured Products</h2>
              <p className="text-slate-500 mt-1">Handpicked selections just for you</p>
            </div>
            <Link to="/products">
              <Button variant="ghost" className="gap-1 text-indigo-600 hover:text-indigo-700">
                See all <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          </div>

          {productsLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-6">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-72 rounded-xl" />
              ))}
            </div>
          ) : (
            <ProductGrid products={products} />
          )}
        </div>
      </section>

      {/* CTA Banner */}
      <section className="py-16 bg-indigo-600">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">Ready to start selling?</h2>
          <p className="text-indigo-200 mb-8 text-lg">
            Join thousands of sellers and reach millions of customers
          </p>
          <Link to="/auth/register">
            <Button size="lg" className="bg-white text-indigo-600 hover:bg-indigo-50 font-semibold">
              Start Your Store Today
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
