# Database Instructions

> **MongoDB Persistence & Indexing** — Schema patterns, index strategies, and data consistency for omnichannel-agentic-commerce.

## Collection Schema Design

### Core Collections
Designs follow MongoDB best practices with application validation (Pydantic for backend):

```javascript
// sessions collection
{
    _id: ObjectId,
    id: "session_abc123...",  // Application-level ID
    userId: null | "user_123",
    anonymousId: "anon_session_...",
    channel: "web" | "mobile" | "voice",
    context: {
        conversation: { lastIntent, lastAgent, lastMessage, entities },
        shopping: { cartId, viewedProducts, searchHistory, currentCategory }
    },
    state: {
        currentIntent, conversationContext, cartId, viewedProducts, searchHistory
    },
    userAgent: "Mozilla/5.0...",
    ipAddress: "192.168.x.x",
    createdAt: ISODate("2026-03-27T..."),
    lastActivity: ISODate("2026-03-27T..."),
    expiresAt: ISODate("2026-03-27T..."),
    metadata: { source, referrer }
}

// carts collection
{
    _id: ObjectId,
    id: "cart_xyz789...",
    userId: null | "user_123",  // null for guest carts
    sessionId: "session_...",
    anonymousId: "anon_...",
    items: [
        {
            itemId: "item_...",
            productId: "prod_...",
            variantId: "var_...",
            name: "Product Name",
            price: 19.99,
            quantity: 2,
            image: "url",
            metadata: { brand }
        }
    ],
    subtotal: 39.98,
    discount: 0,
    tax: 3.20,
    shipping: 5.00,
    total: 48.18,
    itemCount: 2,
    currency: "USD",
    appliedDiscount: null | { code, type, value },
    status: "active" | "abandoned" | "converted",
    createdAt: ISODate("2026-03-27T..."),
    updatedAt: ISODate("2026-03-27T..."),
    expiresAt: ISODate("2026-03-27T...")
}

// users collection
{
    _id: ObjectId,
    id: "user_123...",
    email: "user@example.com",
    name: "John Doe",
    passwordHash: "salt$hash_pbkdf2_sha256",
    role: "customer" | "admin",
    status: "active" | "inactive",
    identity: {
        anonymousId: "anon_..." | null,
        linkedChannels: ["web", "mobile"]
    },
    phone: "+1234567890" | null,
    timezone: "America/New_York" | null,
    defaultShippingAddress: {
        name, line1, line2, city, state, postalCode, country
    } | null,
    profileComplete: false,
    createdAt: ISODate("2026-03-27T..."),
    updatedAt: ISODate("2026-03-27T..."),
    lastLoginAt: ISODate("2026-03-27T...")
}

// orders collection
{
    _id: ObjectId,
    id: "order_...",
    userId: "user_123",
    status: "confirmed" | "shipped" | "delivered" | "cancelled",
    items: [ /* cart items snapshot */ ],
    subtotal, tax, shipping, discount, total,
    currency: "USD",
    shippingAddress: { name, line1, line2, city, state, postalCode, country },
    paymentMethod: { type, last4, expiry },
    paymentStatus: "authorized" | "captured" | "failed",
    paymentReference: "tx_...",
    estimatedDelivery: ISODate("2026-04-01T..."),
    createdAt: ISODate("2026-03-27T..."),
    updatedAt: ISODate("2026-03-27T...")
}
```

### Validation (Backend + Database)
- **Model Validation:** Pydantic models in `backend/app/models/schemas.py`
- **Backend Validation:** Service layer checks constraints before persist
- **Database Validation:** Schema validation rules (optional, for consistency)

```python
# Example: backend/app/models/schemas.py
class AddCartItemRequest(BaseModel):
    productId: str
    variantId: str
    quantity: int = Field(ge=1, le=50)  # ← Enforced at model level

# Example: backend/app/services/cart_service.py
def add_item(self, quantity: int) -> dict[str, Any]:
    if not (1 <= quantity <= 50):
        raise HTTPException(status_code=400, detail="Quantity must be 1-50")
    # ... rest of logic
```

---

## Index Strategy

### Critical Indexes (MUST CREATE)

```javascript
// Collections: sessions
db.sessions.createIndex({ userId: 1, createdAt: -1 })      // Find latest user session
db.sessions.createIndex({ sessionId: 1 }, { unique: true }) // Enforce session uniqueness
db.sessions.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 })  // Auto-delete

// Collections: carts
db.carts.createIndex({ userId: 1 })                        // User carts
db.carts.createIndex({ sessionId: 1 })                     // Session carts
db.carts.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 })  // Auto-delete

// Collections: users
db.users.createIndex({ email: 1 }, { unique: true })       // Email uniqueness
db.users.createIndex({ createdAt: -1 })                    // Date range queries

// Collections: orders
db.orders.createIndex({ userId: 1, createdAt: -1 })       // User order history
db.orders.createIndex({ status: 1 })                       // Filter by status
db.orders.createIndex({ paymentReference: 1 })             // Payment lookup
```

### Index Maintenance

**Monthly Review:**
1. Check query performance with explain plans:
   ```javascript
   db.carts.find({ userId: "user_123" }).explain("executionStats")
   // Should see executionStage: COLLSCAN → convert to indexed query
   ```

2. Remove unused indexes:
   ```javascript
   db.carts.dropIndex("sessionId_1")  // If query logs show no usage
   ```

3. Monitor index size:
   ```javascript
   db.carts.aggregate([{ $indexStats: {} }])
   ```

---

## TTL & Cleanup

### Automatic Expiry (TTL Indexes)
Sessions and carts auto-delete after expiration using MongoDB TTL:

```javascript
// Sessions expire after 30 minutes of no activity
db.sessions.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 })

// Carts expire after 24 hours
db.carts.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 })
```

**How It Works:**
1. Document has `expiresAt: ISODate("2026-03-27T12:00:00Z")`
2. Mongo runs TTL cleanup job (default every 60 seconds)
3. When `now() > expiresAt`, document deleted

**Important:** The `expireAfterSeconds: 0` means MongoDB compares `expiresAt` field directly to current time (not adding seconds). Set actual expiry time in application logic (`_next_cart_expiry()` in cart service).

### Manual Cleanup (Fallback)
For testing or forced cleanup:

```javascript
// Delete expired sessions
db.sessions.deleteMany({ expiresAt: { $lt: new Date() } })

// Delete abandoned carts
db.carts.deleteMany({ status: "abandoned", updatedAt: { $lt: new Date(Date.now() - 7*24*60*60*1000) } })
```

---

## Data Consistency

### Guest → User Cart Transfer

When user registers, guest cart must attach to user account. **No data loss allowed.**

**Flow:**
```
1. User registers → user_id created
2. backend/app/api/routes/auth_routes.py:_resolve_user_session_context() called
3. cart_service.merge_guest_cart_into_user(session_id, user_id) executes
4. If guest cart exists:
   - Set userId = user_id
   - Merge items: sum quantities if same product exists
   - Update cart status = "active"
   - Delete guest cart (session_id) version
5. Return merged user cart
```

**Potential Failure Points:**
- Network timeout during merge → Retry on next request (idempotent operation)
- Duplicate item keys → Merge logic handles (sums quantities)
- User cart already exists → Keep user cart, only add new items from guest

**Guarantee:** No guest cart items lost during auth transition.

---

## Query Patterns

### High-Volume Queries
Optimize with indexes + pagination:

```javascript
// ✅ Efficient: Use index on userId + sort by createdAt desc
db.orders
  .find({ userId: "user_123" })
  .sort({ createdAt: -1 })
  .limit(20)
  .skip(0)
  .explain("executionStats")
  // executionStage should show: IXSCAN (index scan, not COLLSCAN)

// ✅ Efficient: Use indexed fields
db.sessions
  .find({ userId: "user_123", createdAt: { $gt: ISODate("2026-03-20T...") } })
  .limit(1)
  .sort({ createdAt: -1 })

// ❌ INEFFICIENT: No index on arbitrary field
db.orders.find({ notes: "refund requested" })  // Full collection scan
// Fix: If needed frequently, add index: db.orders.createIndex({ notes: "text" })
```

### Aggregation Pipeline
For complex reports:

```javascript
// Find user's total spending
db.orders.aggregate([
  { $match: { userId: "user_123", status: { $in: ["shipped", "delivered"] } } },
  { $group: { _id: "$userId", totalSpent: { $sum: "$total" }, orderCount: { $sum: 1 } } },
  { $project: { _id: 0, userId: "$_id", totalSpent: 1, orderCount: 1 } }
])
```

---

## Backup & Recovery

### Backup Strategy (REQUIRED for Production)

```bash
# Daily incremental backups
mongodump --uri "mongodb://user:pass@host:27017/commerce" \
  --out ./backups/$(date +%Y%m%d_%H%M%S) \
  --gzip

# Weekly full backup + compression
tar -czf /archive/commerce_$(date +%Y%m%d).tar.gz ./backups/latest/

# Verify backup integrity
mongorestore --dry-run --uri "mongodb://localhost:27017/commerce_test" ./backups/latest/
```

### Recovery Procedure
```bash
# 1. Stop application
systemctl stop commerce-backend

# 2. Restore to point-in-time
mongorestore --uri "mongodb://localhost:27017/commerce" \
  --archive=/archive/commerce_20260320.tar.gz \
  --gzip \
  --drop  # ← Caution: overwrites current data

# 3. Verify data integrity
mongo commerce --eval "db.orders.countDocuments()"

# 4. Restart application
systemctl start commerce-backend
```

---

## Troubleshooting

### Common Issues & Fixes

| Issue | Symptom | Fix |
|-------|---------|-----|
| **Duplicate Email on Register** | `E11000 duplicate key error` | Email unique index exists; check for race condition |
| **Cart Not Found After Add** | Cart returns from API but empty on refresh | Session ID changed mid-request; verify header propagation |
| **Orders Stuck in "Confirmed"** | Payment authorized but status never updates | Check order_service.mark_order_shipped(); may need manual trigger |
| **Session TTL Not Working** | Old sessions still in DB | Verify `expiresAt` field exists and uses TTL index; run `db.sessions.createIndex(...)` |
| **Slow Cart Queries** | `getCart()` takes >500ms | Check index exists: `db.carts.getIndexes()` should show userId + sessionId |
| **MongoDB Disk Full** | Writes fail with "capacity exceeded" | Archive old orders/sessions to cold storage; add disk space |

### Debugging Queries

```javascript
// 1. Check execution plan
db.carts.find({ userId: "user_123" }).explain("executionStats")
// Look for: executionStage.stage == "IXSCAN" (good) or "COLLSCAN" (bad)

// 2. Profile slow queries
db.setProfilingLevel(1, { slowms: 100 })  // Log queries > 100ms
db.system.profile.find().sort({ ts: -1 }).limit(5)

// 3. Monitor connections
db.serverStatus().connections
```

---

## Migration Strategy (Future)

### Schema Versioning (Recommended Pattern)
When adding fields, use versioning to track schema evolution:

```javascript
// Add to all documents
{
    schemaVersion: 2,  // Increment on breaking changes
    data: { /* existing fields */ }
}

// In application code: handle both v1 and v2
function normalizeCart(doc) {
    if (doc.schemaVersion === undefined) {
        // Upgrade v1 → v2: add itemCount if missing
        doc.itemCount = doc.items.reduce((sum, item) => sum + item.quantity, 0);
        doc.schemaVersion = 2;
    }
    return doc;
}
```

### Zero-Downtime Migrations
1. Deploy code that handles **both old and new schema** (dual-read)
2. Run migration script **in background** (batch update)
3. Once complete, deploy code that **only reads new schema**

---

## Quick Checklist: Database Setup

- [ ] Collections created with validation
- [ ] Indexes created: sessions (userId, sessionId), carts (userId, sessionId), users (email), orders (userId)
- [ ] TTL index on sessions + carts for auto-cleanup
- [ ] Backup automation configured (daily incremental, weekly full)
- [ ] Connection string uses SSL/TLS in production
- [ ] Admin credentials strong (not default)
- [ ] Query performance validated with explain plans
- [ ] Monitoring configured (slow query log, disk usage)
- [ ] Restore procedure tested and documented
- [ ] Data cleanup job runs for expired sessions/carts

