export interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  image?: string;
  category: string;
  stock: number;
  created_at: string;
}

export interface CartItem {
  id: string;
  name: string;
  price: number;
  quantity: number;
  image?: string;
}

export interface Order {
  id: string;
  status: 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled';
  total: number;
  created_at: string;
  items: OrderItem[];
}

export interface OrderItem {
  product_id: string;
  product_name: string;
  quantity: number;
  price: number;
}
