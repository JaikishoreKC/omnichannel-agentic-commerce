# Database Schema Specification

## Overview

This document defines the database collections, fields, relationships, and design considerations for the omnichannel agentic commerce platform.

Authoritative note:
- This document is a design-level schema reference.
- Runtime source of truth for persisted fields is the repository layer (`backend/app/repositories/*`) and index/bootstrap scripts (`backend/app/scripts/*`, `backend/app/infrastructure/mongo_indexes.py`).

## Database: MongoDB

### Design Principles

1. **Embedded Documents**: Use embedded documents for data that is always accessed together
2. **References**: Use references for data that can grow independently or be shared
3. **Denormalization**: Denormalize for read-heavy access patterns
4. **Indexing**: Create indexes for frequently queried fields

### Contract Mapping Conventions

- External API payloads use `camelCase`.
- Python service/domain objects use `snake_case`.
- Repository layer is responsible for explicit field mapping between API DTOs and persisted documents.

---

## Collections

### 1. users

Stores customer information and authentication data.

```javascript
{
  _id: ObjectId,
  email: String (unique, indexed),
  passwordHash: String,
  name: String,
  
  // Profile
  profile: {
    phone: String,
    avatar: String,
    dateOfBirth: Date,
    defaultShippingAddress: ObjectId
  },
  
  // Preferences
  preferences: {
    size: String,
    brandPreferences: [String],
    categories: [String],
    priceRange: {
      min: Number,
      max: Number
    },
    notifications: {
      email: Boolean,
      sms: Boolean,
      push: Boolean
    }
  },
  
  // Identity
  identity: {
    anonymousId: String,
    linkedChannels: [{
      provider: String,
      externalId: String
    }]
  },
  
  // Metadata
  status: String (enum: ['active', 'suspended', 'deleted']),
  createdAt: Date,
  updatedAt: Date,
  lastLoginAt: Date
}
```

**Indexes:**
- `email` (unique)
- `status`
- `createdAt`

---

### 2. sessions

Stores active user sessions across channels.

```javascript
{
  _id: ObjectId,
  sessionId: String (unique, indexed),
  
  // Identity
  userId: ObjectId (ref: users, nullable),
  anonymousId: String,
  
  // Channel info
  channel: String (enum: ['web', 'websocket', 'mobile', 'api']),
  userAgent: String,
  ipAddress: String,
  
  // State
  state: {
    currentIntent: String,
    conversationContext: {
      lastAgent: String,
      lastMessage: String,
      pendingAction: Object
    },
    cartId: ObjectId (ref: carts),
    viewedProducts: [ObjectId],
    searchHistory: [String]
  },
  
  // Lifecycle
  createdAt: Date,
  lastActivityAt: Date,
  expiresAt: Date,
  
  // Metadata
  metadata: {
    source: String,
    referrer: String
  }
}
```

**Indexes:**
- `sessionId` (unique)
- `userId`
- `expiresAt`
- `lastActivityAt`

---

### 3. products

Stores product catalog information.

```javascript
{
  _id: ObjectId,
  productId: String (unique),
  
  // Core
  name: String,
  description: String,
  category: String (indexed),
  subcategory: String,
  
  // Pricing
  basePrice: Number,
  currency: String,
  
  // Media
  images: [{
    url: String,
    alt: String,
    isPrimary: Boolean
  }],
  videos: [{
    url: String,
    thumbnail: String
  }],
  
  // Variants
  variants: [{
    variantId: String,
    sku: String,
    attributes: {
      size: String,
      color: String,
      material: String
    },
    price: Number,
    inventory: {
      quantity: Number,
      reserved: Number,
      available: Number
    }
  }],
  
  // Specifications
  specifications: Object,
  features: [String],
  
  // SEO
  slug: String,
  metaTitle: String,
  metaDescription: String,
  
  // Commerce
  brand: String (indexed),
  tags: [String],
  
  // Ratings
  rating: {
    average: Number,
    count: Number
  },
  
  // Policy
  returnPolicy: String,
  warrantyMonths: Number,
  
  // Status
  status: String (enum: ['active', 'draft', 'archived']),
  createdAt: Date,
  updatedAt: Date
}
```

**Indexes:**
- `productId` (unique)
- `category`
- `brand`
- `name` (text search)
- `status`

---

### 4. carts

Stores shopping cart data.

```javascript
{
  _id: ObjectId,
  cartId: String (unique),
  
  // Owner
  userId: ObjectId (ref: users, nullable),
  sessionId: String,
  anonymousId: String,
  
  // Items
  items: [{
    itemId: String,
    productId: String,
    variantId: String,
    name: String,
    price: Number,
    quantity: Number,
    image: String,
    metadata: Object
  }],
  
  // Pricing
  pricing: {
    subtotal: Number,
    tax: Number,
    shipping: Number,
    discount: Number,
    total: Number,
    currency: String
  },
  
  // Discount
  appliedDiscount: {
    code: String,
    type: String,
    value: Number,
    amount: Number
  } | null,
  
  // Status
  status: String (enum: ['active', 'converted', 'abandoned']),
  
  // Lifecycle
  createdAt: Date,
  updatedAt: Date,
  expiresAt: Date
}
```

**Indexes:**
- `cartId` (unique)
- `userId`
- `sessionId`
- `expiresAt`

---

### 5. orders

Stores order and transaction data.

```javascript
{
  _id: ObjectId,
  orderId: String (unique),
  
  // Owner
  userId: ObjectId (ref: users, required in v1),
  sessionId: String,
  
  // Items
  items: [{
    productId: String,
    variantId: String,
    name: String,
    price: Number,
    quantity: Number,
    image: String
  }],
  
  // Pricing
  pricing: {
    subtotal: Number,
    tax: Number,
    shipping: Number,
    discount: Number,
    total: Number,
    currency: String
  },
  
  // Fulfillment
  shippingAddress: {
    name: String,
    line1: String,
    line2: String,
    city: String,
    state: String,
    postalCode: String,
    country: String
  },
  
  billingAddress: {
    // Same structure as shipping
  },
  
  // Tracking
  tracking: {
    carrier: String,
    trackingNumber: String,
    status: String,
    updates: [{
      status: String,
      location: String,
      timestamp: Date
    }]
  },
  
  // Status
  status: String (enum: ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']),
  
  // Timeline
  timeline: [{
    status: String,
    timestamp: Date,
    note: String
  }],
  
  // Payment
  payment: {
    method: String,
    transactionId: String,
    status: String
  },
  
  // Metadata
  metadata: Object,
  
  // Timestamps
  createdAt: Date,
  updatedAt: Date
}
```

**Indexes:**
- `orderId` (unique)
- `userId`
- `status`
- `createdAt`

---

### 6. memories

Stores long-term user memory and preferences.

```javascript
{
  _id: ObjectId,
  userId: ObjectId (unique, indexed),
  
  // Preferences (cached from users collection)
  preferences: {
    size: String,
    brandPreferences: [String],
    categories: [String],
    priceRange: {
      min: Number,
      max: Number
    }
  },
  
  // Interaction history (summarized)
  interactionHistory: [{
    type: String,
    timestamp: Date,
    summary: {
      query: String,
      productId: String,
      action: String
    }
  }],
  
  // Product affinities
  productAffinities: [{
    productId: String,
    category: String,
    brand: String,
    score: Number,
    lastInteraction: Date
  }],
  
  // Conversation patterns
  conversationPatterns: {
    commonQueries: [String],
    preferredPhrasing: [String]
  },
  
  // Updated
  lastUpdated: Date
}
```

**Indexes:**
- `userId` (unique)

---

### 7. messages

Stores conversation messages for context and history.

```javascript
{
  _id: ObjectId,
  
  // Context
  sessionId: String (indexed),
  userId: ObjectId (ref: users, nullable),
  
  // Message
  role: String (enum: ['user', 'assistant', 'system']),
  content: String,
  intent: String,
  entities: [{
    type: String,
    value: String,
    confidence: Number
  }],
  
  // Agent
  agent: String,
  
  // Response
  response: {
    message: String,
    data: Object,
    actions: [String]
  },
  
  // Metadata
  metadata: {
    model: String,
    processingTime: Number,
    tokens: Number
  },
  
  // Timestamp
  timestamp: Date
}
```

**Indexes:**
- `sessionId`
- `userId`
- `timestamp`
- `intent`

---

### 8. inventory

Stores inventory levels and reservations.

```javascript
{
  _id: ObjectId,
  productId: String (indexed),
  variantId: String,
  
  // Levels
  totalQuantity: Number,
  reservedQuantity: Number,
  availableQuantity: Number,
  
  // Reservations
  reservations: [{
    reservationId: String,
    quantity: Number,
    expiresAt: Date,
    status: String
  }],
  
  // Warehouse
  warehouseLocation: String,
  
  // Updated
  updatedAt: Date
}
```

**Indexes:**
- `productId` + `variantId` (compound, unique)

---

### 9. admin_activity_logs

Audit log for administrative actions.

```javascript
{
  _id: ObjectId,
  
  // Admin
  adminId: ObjectId,
  adminEmail: String,
  
  // Action
  action: String,
  resource: String,
  resourceId: String,
  
  // Details
  changes: {
    before: Object,
    after: Object
  },
  
  // Context
  ipAddress: String,
  userAgent: String,
  
  // Timestamp
  timestamp: Date
}
```

**Indexes:**
- `adminId`
- `timestamp`
- `resource` + `resourceId`

---

## Relationships

```
users (1) ────< (N) sessions
users (1) ────< (N) carts
users (1) ────< (N) orders
users (1) ────< (1) memories
users (1) ────< (N) messages
sessions (1) ────< (N) messages
sessions (1) ────< (1) carts
carts (1) ────< (1) orders
```

---

## Data Retention

| Collection | Retention | Reason |
|------------|-----------|--------|
| sessions | 24 hours | Short-lived, stateless |
| carts | 7 days | Allow cart recovery |
| messages | 90 days | Context window |
| memories | Indefinite | User preference |
| orders | 2 years (default) | Historical analytics and customer support |
| admin_activity_logs | 1 year (default) | Operational auditing |

---

## Caching Strategy

| Data | Cache Strategy | TTL |
|------|-----------------|-----|
| Products | Redis | 1 hour |
| Categories | Redis | 24 hours |
| User sessions | Redis | Session expiry |
| Cart totals | Redis | 5 minutes |
| Inventory | Redis | 1 minute |
