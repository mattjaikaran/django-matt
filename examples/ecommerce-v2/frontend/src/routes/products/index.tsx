import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import { useProducts, useCategories } from '@/hooks/use-products';
import { ProductGrid } from '@/components/products/ProductGrid';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Search, SlidersHorizontal, X } from 'lucide-react';

interface ProductsSearch {
  category?: string;
  minPrice?: number;
  maxPrice?: number;
  search?: string;
}

export const Route = createFileRoute('/products/')({
  validateSearch: (search): ProductsSearch => ({
    category: (search.category as string) || undefined,
    minPrice: search.minPrice ? Number(search.minPrice) : undefined,
    maxPrice: search.maxPrice ? Number(search.maxPrice) : undefined,
    search: (search.search as string) || undefined,
  }),
  component: ProductsPage,
});

const LIMIT = 20;

function ProductsPage() {
  const navigate = useNavigate({ from: '/products/' });
  const { category, minPrice, maxPrice, search } = Route.useSearch();

  const [offset, setOffset] = useState(0);
  const [searchInput, setSearchInput] = useState(search ?? '');
  const [minInput, setMinInput] = useState(minPrice?.toString() ?? '');
  const [maxInput, setMaxInput] = useState(maxPrice?.toString() ?? '');

  const { data: categoriesData } = useCategories();
  const { data: productsData, isLoading } = useProducts({
    category,
    minPrice,
    maxPrice,
    search,
    limit: LIMIT,
    offset,
  });

  const products = productsData?.items ?? [];
  const total = productsData?.total ?? 0;
  const categories = categoriesData?.items ?? [];
  const hasMore = products.length < total;

  const activeFiltersCount = [category, minPrice, maxPrice, search].filter(Boolean).length;

  function applyFilters() {
    setOffset(0);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    navigate({ search: { category, search: searchInput || undefined, minPrice: minInput ? Number(minInput) : undefined, maxPrice: maxInput ? Number(maxInput) : undefined } as any });
  }

  function clearFilters() {
    setSearchInput('');
    setMinInput('');
    setMaxInput('');
    setOffset(0);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    navigate({ search: {} as any });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') applyFilters();
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Products</h1>
          <p className="text-slate-500 mt-1">
            {total > 0 ? `${total} products found` : 'Browse our collection'}
          </p>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
          <div className="flex flex-wrap gap-3 items-end">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs font-medium text-slate-600 mb-1 block">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  placeholder="Search products..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="pl-9"
                />
              </div>
            </div>

            {/* Category */}
            <div className="w-40">
              <label className="text-xs font-medium text-slate-600 mb-1 block">Category</label>
              <Select
                value={category ?? 'all'}
                onValueChange={(val) => {
                  setOffset(0);
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  navigate({ search: { category: val === 'all' ? undefined : val, search, minPrice, maxPrice } as any });
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {categories.map((cat) => (
                    <SelectItem key={cat.id} value={cat.slug}>
                      {cat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Price Range */}
            <div className="w-32">
              <label className="text-xs font-medium text-slate-600 mb-1 block">Min Price</label>
              <Input
                type="number"
                placeholder="$0"
                value={minInput}
                onChange={(e) => setMinInput(e.target.value)}
                onKeyDown={handleKeyDown}
                min={0}
              />
            </div>
            <div className="w-32">
              <label className="text-xs font-medium text-slate-600 mb-1 block">Max Price</label>
              <Input
                type="number"
                placeholder="Any"
                value={maxInput}
                onChange={(e) => setMaxInput(e.target.value)}
                onKeyDown={handleKeyDown}
                min={0}
              />
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <Button onClick={applyFilters} className="bg-indigo-600 hover:bg-indigo-700 gap-2">
                <SlidersHorizontal className="w-4 h-4" />
                Apply
              </Button>
              {activeFiltersCount > 0 && (
                <Button variant="outline" onClick={clearFilters} className="gap-1">
                  <X className="w-4 h-4" />
                  Clear
                  <Badge className="ml-1 bg-indigo-100 text-indigo-700 text-xs px-1.5 py-0">
                    {activeFiltersCount}
                  </Badge>
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Results */}
        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-6">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-72 rounded-xl" />
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="text-center py-20">
            <Search className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600 font-medium text-lg">No products found</p>
            <p className="text-slate-400 mt-1">Try adjusting your filters</p>
            <Button variant="outline" onClick={clearFilters} className="mt-4">
              Clear Filters
            </Button>
          </div>
        ) : (
          <>
            <ProductGrid products={products} />
            {hasMore && (
              <div className="text-center mt-8">
                <Button
                  variant="outline"
                  size="lg"
                  onClick={() => setOffset((prev) => prev + LIMIT)}
                  className="px-8"
                >
                  Load More ({total - products.length} remaining)
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
