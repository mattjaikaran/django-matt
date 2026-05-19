// ─── Auth ────────────────────────────────────────────────────────────────────

export interface User {
  id: number;
  email: string;
  username: string;
  firstName: string;
  lastName: string;
  avatarUrl?: string;
  bio?: string;
  phone?: string;
  dateJoined: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  username: string;
  password: string;
  firstName?: string;
  lastName?: string;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

// ─── Stores ──────────────────────────────────────────────────────────────────

export interface Store {
  id: string;
  name: string;
  slug: string;
  description?: string;
  logoUrl?: string;
  isActive: boolean;
  rating: number;
  ownerId: number;
  createdAt: string;
  updatedAt: string;
}

export interface StoreCreate {
  name: string;
  slug: string;
  description?: string;
  logoUrl?: string;
}

export interface StoreUpdate {
  name?: string;
  slug?: string;
  description?: string;
  logoUrl?: string;
  isActive?: boolean;
}

// ─── Catalog ─────────────────────────────────────────────────────────────────

export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string;
  parentId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Product {
  id: string;
  storeId: string;
  categoryId?: string;
  name: string;
  slug: string;
  description?: string;
  price: string;
  compareAtPrice?: string;
  isActive: boolean;
  imageUrl?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Variant {
  id: string;
  productId: string;
  name: string;
  sku: string;
  priceOverride?: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ProductCreate {
  storeId: string;
  categoryId?: string;
  name: string;
  slug: string;
  description?: string;
  price: string;
  compareAtPrice?: string;
  imageUrl?: string;
}

export interface ProductUpdate {
  categoryId?: string;
  name?: string;
  slug?: string;
  description?: string;
  price?: string;
  compareAtPrice?: string;
  imageUrl?: string;
  isActive?: boolean;
}

// ─── Cart ────────────────────────────────────────────────────────────────────

export interface CartItem {
  id: string;
  productId: string;
  variantId?: string;
  quantity: number;
  createdAt: string;
  product?: Product;
}

export interface Cart {
  id: string;
  items: CartItem[];
  itemCount: number;
  createdAt: string;
}

export interface AddToCart {
  productId: string;
  variantId?: string;
  quantity: number;
}

// ─── Orders ──────────────────────────────────────────────────────────────────

export type OrderStatus =
  | 'pending'
  | 'confirmed'
  | 'processing'
  | 'shipped'
  | 'delivered'
  | 'cancelled'
  | 'refunded';

export interface OrderItem {
  id: string;
  productId: string;
  variantId?: string;
  quantity: number;
  unitPrice: string;
  totalPrice: string;
  product?: Product;
}

export interface Order {
  id: string;
  userId: number;
  storeId: string;
  status: OrderStatus;
  subtotal: string;
  tax: string;
  shippingCost: string;
  total: string;
  currency: string;
  shippingAddress: string;
  billingAddress: string;
  notes?: string;
  stripePaymentIntentId?: string;
  items: OrderItem[];
  createdAt: string;
  updatedAt: string;
}

export interface OrderCreate {
  storeId: string;
  items: { productId: string; variantId?: string; quantity: number }[];
  shippingAddress: string;
  billingAddress: string;
  notes?: string;
}

// ─── Payments ────────────────────────────────────────────────────────────────

export interface PaymentIntent {
  clientSecret: string;
  paymentIntentId: string;
  amount: number;
  currency: string;
}

// ─── Reviews ─────────────────────────────────────────────────────────────────

export interface Review {
  id: string;
  userId: number;
  productId: string;
  rating: number;
  title: string;
  body: string;
  isVerifiedPurchase: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ReviewSummary {
  averageRating: number;
  totalReviews: number;
  ratingDistribution: Record<string, number>;
}

export interface ReviewCreate {
  rating: number;
  title: string;
  body: string;
}

// ─── Search ──────────────────────────────────────────────────────────────────

export interface SearchResult {
  id: string;
  name: string;
  type: string;
  description?: string;
  price?: number;
  imageUrl?: string;
  url: string;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

// ─── Pagination ──────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit?: number;
  offset?: number;
  page?: number;
  pageSize?: number;
}

// ─── UI State ────────────────────────────────────────────────────────────────

export type Theme = 'light' | 'dark' | 'system';

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
}
