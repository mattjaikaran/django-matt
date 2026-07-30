import { createFileRoute } from '@tanstack/react-router';
import { useParams } from '@tanstack/react-router';
import { ArrowLeft, Minus, Plus } from 'lucide-react';
import { useCart } from '@/hooks/useCart';

const MOCK_DETAIL: Record<string, { name: string; description: string; price: number; category: string; image: string; stock: number }> = {
  '1': { name: 'Wireless Headphones', description: 'Premium noise-cancelling Bluetooth headphones with 30-hour battery life. Features active noise cancellation, comfortable over-ear design, and rich, immersive sound.', price: 79.99, category: 'Electronics', image: 'https://picsum.photos/seed/headphones/600/600', stock: 10 },
  '2': { name: 'Mechanical Keyboard', description: 'Full-size mechanical keyboard with Cherry MX Blue switches. Per-key RGB lighting, aircraft-grade aluminum frame, and detachable USB-C cable.', price: 129.99, category: 'Electronics', image: 'https://picsum.photos/seed/keyboard/600/600', stock: 5 },
  '3': { name: 'USB-C Hub', description: '7-in-1 USB-C hub featuring HDMI 4K output, SD card reader, 3 USB-A ports, and 100W power delivery passthrough. Compatible with laptops, tablets, and phones.', price: 34.99, category: 'Accessories', image: 'https://picsum.photos/seed/hub/600/600', stock: 20 },
  '4': { name: 'Laptop Stand', description: 'Adjustable aluminum laptop stand with ergonomic design. Raises screen to eye level, improves airflow, and folds flat for travel.', price: 49.99, category: 'Accessories', image: 'https://picsum.photos/seed/stand/600/600', stock: 15 },
  '5': { name: 'Desk Lamp', description: 'LED desk lamp with 5 brightness levels and 3 color temperatures. Touch control, flexible arm, and built-in USB charging port.', price: 39.99, category: 'Office', image: 'https://picsum.photos/seed/lamp/600/600', stock: 8 },
  '6': { name: 'Ergonomic Mouse', description: 'Vertical ergonomic mouse designed to reduce wrist strain. Wireless, rechargeable, with adjustable DPI and silent clicks.', price: 59.99, category: 'Accessories', image: 'https://picsum.photos/seed/mouse/600/600', stock: 12 },
  '7': { name: 'Monitor Arm', description: 'Gas-spring monitor arm supporting 17-32" displays. Full motion articulation, integrated cable management, and C-clamp or grommet mounting.', price: 89.99, category: 'Office', image: 'https://picsum.photos/seed/arm/600/600', stock: 6 },
  '8': { name: 'Webcam Cover', description: 'Ultra-thin privacy shutter for laptops and external webcams. Adhesive mount, sliding mechanism, protects against unauthorized viewing.', price: 4.99, category: 'Accessories', image: 'https://picsum.photos/seed/webcam/600/600', stock: 50 },
};

export const Route = createFileRoute('/products/$id')({
  component: ProductDetailPage,
});

function ProductDetailPage() {
  const { id } = useParams({ from: '/products/$id' });
  const { addItem } = useCart();
  const product = MOCK_DETAIL[id];

  if (!product) {
    return (
      <div className="text-center py-16">
        <p className="text-slate-500">Product not found.</p>
      </div>
    );
  }

  const handleAddToCart = () => {
    addItem({ id, name: product.name, price: product.price, quantity: 1, image: product.image });
  };

  return (
    <div>
      <a
        href="/products"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 mb-6"
        onClick={(e) => { e.preventDefault(); window.history.back(); }}
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Products
      </a>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="aspect-square bg-slate-100 rounded-xl overflow-hidden">
          <img
            src={product.image}
            alt={product.name}
            className="w-full h-full object-cover"
          />
        </div>

        <div>
          <span className="text-xs font-medium text-indigo-600 uppercase tracking-wide">{product.category}</span>
          <h1 className="text-3xl font-bold text-slate-900 mt-2">{product.name}</h1>
          <p className="text-2xl font-bold text-slate-900 mt-4">${product.price.toFixed(2)}</p>

          <p className="text-slate-600 mt-6 leading-relaxed">{product.description}</p>

          <div className="mt-6 flex items-center gap-2 text-sm text-slate-500">
            <span className={`inline-block w-2 h-2 rounded-full ${product.stock > 0 ? 'bg-green-500' : 'bg-red-500'}`} />
            {product.stock > 0 ? `${product.stock} in stock` : 'Out of stock'}
          </div>

          <button
            onClick={handleAddToCart}
            disabled={product.stock === 0}
            className="mt-6 w-full md:w-auto px-8 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            Add to Cart
          </button>
        </div>
      </div>
    </div>
  );
}
