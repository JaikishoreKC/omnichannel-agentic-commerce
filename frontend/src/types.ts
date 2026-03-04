export interface ProductVariant {
  id: string;
  size: string;
  color: string;
  inStock: boolean;
}

export interface Product {
  id: string;
  name: string;
  description: string;
  category: string;
  subcategory?: string;
  brand?: string;
  price: number;
  currency: string;
  images: string[];
  variants: ProductVariant[];
  rating: number;
  reviewCount?: number;
  tags?: string[];
  features?: string[];
  specifications?: Record<string, unknown>;
  status?: string;
  reviews?: any[];
}

export interface CartItem {
  itemId: string;
  productId: string;
  variantId: string;
  name: string;
  price: number;
  quantity: number;
  image: string;
}

export interface Cart {
  id: string;
  userId: string | null;
  sessionId: string;
  items: CartItem[];
  subtotal: number;
  tax: number;
  shipping: number;
  discount: number;
  total: number;
  itemCount: number;
  currency: string;
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
  status?: string;
  createdAt: string;
  identity?: {
    anonymousId: string | null;
    linkedChannels: Array<{ provider: string; externalId: string }>;
  } | null;
}

export interface AuthResponse {
  user: AuthUser;
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  sessionId?: string;
}

export interface InteractionHistoryMessage {
  id: string;
  sessionId: string;
  userId: string | null;
  message: string;
  intent: string;
  agent: string;
  response: {
    message?: string;
    agent?: string;
    [key: string]: unknown;
  };
  timestamp: string;
}

export interface Order {
  id: string;
  status: string;
  total: number;
  itemCount: number;
  createdAt: string;
}

export interface TimelineEvent {
  status: string;
  timestamp: string;
  note?: string;
}

export interface OrderItem {
  productId: string;
  variantId: string;
  name: string;
  price: number;
  quantity: number;
  image: string;
}

export interface OrderDetail extends Order {
  userId: string;
  items: OrderItem[];
  subtotal: number;
  tax: number;
  shipping: number;
  discount: number;
  shippingAddress: {
    name: string;
    line1: string;
    city: string;
    state: string;
    postalCode: string;
    country: string;
  };
  payment: {
    method: string;
    transactionId?: string;
    status: string;
  };
  timeline: TimelineEvent[];
  tracking: {
    carrier?: string;
    trackingNumber?: string;
    status: string;
    updates: any[];
  };
  estimatedDelivery?: string;
  updatedAt: string;
}
