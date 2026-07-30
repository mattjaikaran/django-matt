import { createFileRoute, Link } from '@tanstack/react-router';
import { ArrowRight, Star } from 'lucide-react';

const FEATURED = [
  { id: '1', name: 'Wireless Headphones', price: 79.99, image: 'https://picsum.photos/seed/headphones/400/400', rating: 4 },
  { id: '2', name: 'Mechanical Keyboard', price: 129.99, image: 'https://picsum.photos/seed/keyboard/400/400', rating: 5 },
  { id: '3', name: 'USB-C Hub', price: 34.99, image: 'https://picsum.photos/seed/hub/400/400', rating: 4 },
  { id: '4', name: 'Laptop Stand', price: 49.99, image: 'https://picsum.photos/seed/stand/400/400', rating: 3 },
];

export const Route = createFileRoute('/')({
  component: HomePage,
});

function HomePage() {
  return (
    <div>
      {/* Hero */}
      <section className="text-center py-16 md:py-24">
        <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-4">
          Discover Great Products
        </h1>
        <p className="text-lg text-slate-500 max-w-xl mx-auto mb-8">
          Curated selection of premium gear for work and play. Fast shipping, easy returns.
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            to="/products"
            className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium inline-flex items-center gap-2"
          >
            Shop Now
            <ArrowRight className="w-4 h-4" />
          </Link>
          <a
            href="/api/docs"
            target="_blank"
            className="px-6 py-3 border border-slate-300 rounded-lg hover:bg-slate-100 font-medium"
            rel="noreferrer"
          >
            API Docs
          </a>
        </div>
      </section>

      {/* Featured Products */}
      <section className="py-12">
        <h2 className="text-2xl font-bold text-slate-900 mb-6">Featured Products</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {FEATURED.map((product) => (
            <Link
              key={product.id}
              to="/products/$id"
              params={{ id: product.id }}
              className="bg-white rounded-xl border shadow-sm hover:shadow-md transition-shadow overflow-hidden group"
            >
              <div className="aspect-square bg-slate-100 overflow-hidden">
                <img
                  src={product.image}
                  alt={product.name}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                />
              </div>
              <div className="p-4">
                <h3 className="font-semibold text-slate-900">{product.name}</h3>
                <div className="flex items-center gap-1 mt-1">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Star
                      key={i}
                      className={`w-3.5 h-3.5 ${i < product.rating ? 'text-amber-400 fill-amber-400' : 'text-slate-200'}`}
                    />
                  ))}
                </div>
                <p className="text-lg font-bold text-slate-900 mt-2">${product.price.toFixed(2)}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
