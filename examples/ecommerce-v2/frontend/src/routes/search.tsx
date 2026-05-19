import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { searchApi } from '@/api/search';
import { ProductGrid } from '@/components/products/ProductGrid';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { Product } from '@/types';
import { Search, SlidersHorizontal, X } from 'lucide-react';

interface SearchParams {
  q?: string;
  minPrice?: number;
  maxPrice?: number;
}

export const Route = createFileRoute('/search')({
  validateSearch: (search): SearchParams => ({
    q: (search.q as string) || undefined,
    minPrice: search.minPrice ? Number(search.minPrice) : undefined,
    maxPrice: search.maxPrice ? Number(search.maxPrice) : undefined,
  }),
  component: SearchPage,
});

function SearchPage() {
  const navigate = useNavigate({ from: '/search' });
  const { q, minPrice, maxPrice } = Route.useSearch();

  const [inputValue, setInputValue] = useState(q ?? '');
  const [minInput, setMinInput] = useState(minPrice?.toString() ?? '');
  const [maxInput, setMaxInput] = useState(maxPrice?.toString() ?? '');

  useEffect(() => {
    setInputValue(q ?? '');
  }, [q]);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['search', q, minPrice, maxPrice],
    queryFn: () =>
      searchApi.search({
        q,
        minPrice,
        maxPrice,
        limit: 24,
      }),
    enabled: !!(q || minPrice || maxPrice),
  });

  const results = data?.results ?? [];
  const total = data?.total ?? 0;

  // Map SearchResult to Product shape for ProductGrid
  const products: Product[] = results
    .filter((r) => r.type === 'product')
    .map((r) => ({
      id: r.id,
      storeId: '',
      name: r.name,
      slug: r.id,
      description: r.description,
      price: r.price?.toString() ?? '0',
      isActive: true,
      imageUrl: r.imageUrl,
      createdAt: '',
      updatedAt: '',
    }));

  function applySearch() {
    navigate({
      search: {
        q: inputValue || undefined,
        minPrice: minInput ? Number(minInput) : undefined,
        maxPrice: maxInput ? Number(maxInput) : undefined,
      },
    });
  }

  function clearSearch() {
    setInputValue('');
    setMinInput('');
    setMaxInput('');
    navigate({ search: {} });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') applySearch();
  }

  const hasFilters = q || minPrice || maxPrice;

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Search</h1>
          {q && (
            <p className="text-slate-500 mt-1">
              {isLoading || isFetching ? 'Searching...' : `${total} results for "${q}"`}
            </p>
          )}
        </div>

        {/* Search Controls */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
          <div className="flex flex-wrap gap-3 items-end">
            {/* Query */}
            <div className="flex-1 min-w-[220px]">
              <label className="text-xs font-medium text-slate-600 mb-1 block">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input
                  placeholder="Search products, categories..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="pl-9"
                  autoFocus
                />
              </div>
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
              <Button onClick={applySearch} className="bg-indigo-600 hover:bg-indigo-700 gap-2">
                <SlidersHorizontal className="w-4 h-4" />
                Search
              </Button>
              {hasFilters && (
                <Button variant="outline" onClick={clearSearch} className="gap-1">
                  <X className="w-4 h-4" />
                  Clear
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Results */}
        {!hasFilters ? (
          <div className="text-center py-20">
            <Search className="w-14 h-14 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600 font-medium text-lg">Start searching</p>
            <p className="text-slate-400 mt-1">Enter a search term above to find products</p>
          </div>
        ) : isLoading || isFetching ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-6">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-72 rounded-xl" />
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="text-center py-20">
            <Search className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600 font-medium text-lg">No results found</p>
            <p className="text-slate-400 mt-1">Try different keywords or remove filters</p>
            <Button variant="outline" onClick={clearSearch} className="mt-4">
              Clear Filters
            </Button>
          </div>
        ) : (
          <ProductGrid products={products} />
        )}
      </div>
    </div>
  );
}
