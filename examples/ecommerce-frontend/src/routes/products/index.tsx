import { createFileRoute, Link } from '@tanstack/react-router';
import { useState } from 'react';
import { Search } from 'lucide-react';
import { useCart } from '@/hooks/useCart';

const MOCK_PRODUCTS = [
  { id: '1', name: 'Wireless Headphones', description: 'Noise-cancelling Bluetooth headphones', price: 79.99, category: 'Electronics', image: 'https://picsum.photos/seed/headphones/400/400', stock: 10 },
  { id: '2', name: 'Mechanical Keyboard', description: 'RGB mechanical keyboard with Cherry MX switches', price: 129.99, category: 'Electronics', image: 'https://picsum.photos/seed/keyboard/400/400', stock: 5 },
  { id: '3', name: 'USB-C Hub', description: '7-in-1 USB-C hub with HDMI and SD card', price: 34.99, category: 'Accessories', image: 'https://picsum.photos/seed/hub/400/400', stock: 20 },
  { id: '4', name: 'Laptop Stand', description: 'Adjustable aluminum laptop stand', price: 49.99, category: 'Accessories', image: 'https://picsum.photos/seed/stand/400/400', stock: 15 },
  { id: '5', name: 'Desk Lamp', description: 'LED desk lamp with adjustable brightness', price: 39.99, category: 'Office', image: 'https://picsum.photos/seed/lamp/400/400', stock: 8 },
  { id: '6', name: 'Ergonomic Mouse', description: 'Vertical ergonomic mouse for wrist comfort', price: 59.99, category: 'Accessories', image: 'https://picsum.photos/seed/mouse/400/400', stock: 12 },
  { id: '7', name: 'Monitor Arm', description: 'Gas-spring monitor arm for 17-32" screens', price: 89.99, category: 'Office', image: 'https://picsum.photos/seed/arm/400/400', stock: 6 },
  { id: '8', name: 'Webcam Cover', description: 'Privacy shutter for webcams', price: 4.99, category: 'Accessories', image: 'https://picsum.photos/seed/webcam/400/400', stock: 50 },
];

const CATEGORIES = ['All', 'Electronics', 'Accessories', 'Office'];

export const Route = createFileRoute('/products/')({
  component: ProductsPage,
});

function ProductsPage() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const { addItem } = useCart();

  const filtered = MOCK_PRODUCTS.filter((p) => {
    const matchSearch = !search || p.name.toLowerCase().includes(search.toLowerCase());
    const matchCategory = category === 'All' || p.category === category;
    return matchSearch && matchCategory;
  });

  const handleAddToCart = (e: React.MouseEvent, product: (typeof MOCK_PRODUCTS)[0]) => {
    e.preventDefault();
    addItem({ id: product.id, name: product.name, price: product.price, quantity: 1, image: product.image });
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Products</h1>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <input
          type="text"
          placeholder="Search products..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        />
      </div>

      {/* Category filter */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              category === cat
                ? 'bg-indigo-600 text-white'
                : 'bg-white border border-slate-300 text-slate-600 hover:bg-slate-100'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Product grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {filtered.map((product) => (
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
              <span className="text-xs font-medium text-indigo-600 uppercase tracking-wide">{product.category}</span>
              <h3 className="font-semibold text-slate-900 mt-1">{product.name}</h3>
              <p className="text-sm text-slate-500 mt-1 line-clamp-2">{product.description}</p>
              <div className="flex items-center justify-between mt-3">
                <span className="text-lg font-bold text-slate-900">${product.price.toFixed(2)}</span>
                <button
                  onClick={(e) => handleAddToCart(e, product)}
                  className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
                >
                  Add to Cart
                </button>
              </div>
            </div>
          </Link>
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-center text-slate-500 py-12">No products found.</p>
      )}
    </div>
  );
}
