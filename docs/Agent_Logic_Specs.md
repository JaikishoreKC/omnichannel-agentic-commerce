# Agent Logic Specifications

## Overview

This document defines the responsibilities, inputs, outputs, and interaction patterns for all agents in the system.

## Agent Architecture

### Agent Base Class

All agents inherit from a base agent class that standardizes:
- Action execution (`execute(action, context)`)
- Context-aware domain invocation
- Error handling and safe fallback response shaping
- Agent response structure (`success`, `message`, `data`, `next_actions`)

## Specialized Agents

### 1. Product Agent

**Responsibilities:**
- Search products by query, category, attributes
- Provide product details and specifications
- Generate personalized product recommendations
- Handle variant selection (size, color, etc.)
- Manage inventory availability queries

**Inputs:**
- User query string
- Context object (session data, user preferences)
- Filters (category, price range, attributes)
- Pagination parameters

**Outputs:**
- List of matching products with metadata
- Product detail object
- Recommendation list with reasoning

**Example Interactions:**
```
User: "Show me running shoes"
→ Product Agent: Returns filtered product list

User: "What's the return policy for this jacket?"
→ Product Agent: Returns product-specific policy

User: "I need a gift for my wife"
→ Product Agent: Generates recommendations based on gift context
```

### 2. Cart Agent

**Responsibilities:**
- Add items to shopping cart
- Update item quantities
- Remove items from cart
- Apply discount codes
- Calculate totals and taxes
- Persist cart across sessions

**Inputs:**
- Product ID and variant
- Quantity
- User ID (from session)
- Discount code (optional)

**Outputs:**
- Updated cart object
- Price breakdown (subtotal, tax, shipping, total)
- Action confirmation messages

**Example Interactions:**
```
User: "Add this to my cart"
→ Cart Agent: Adds item, returns updated cart

User: "I need 3 of these instead of 1"
→ Cart Agent: Updates quantity, recalculates total

User: "Do I have any items in my cart?"
→ Cart Agent: Returns current cart contents
```

### 3. Order Agent

**Responsibilities:**
- Process checkout workflow
- Create orders from cart
- Retrieve order history
- Track order status
- Handle order modifications (if allowed)
- Process refunds and cancellations

**Inputs:**
- Cart ID
- Shipping address
- Payment information
- User ID

**Outputs:**
- Order confirmation with ID
- Order status updates
- Tracking information
- Order history list

**Example Interactions:**
```
User: "I want to checkout"
→ Order Agent: Initiates checkout, validates cart

User: "Where is my order?"
→ Order Agent: Returns current tracking status

User: "I need to cancel my order"
→ Order Agent: Processes cancellation if allowed
```

### 4. Support Agent

**Responsibilities:**
- Answer product-related questions
- Handle order issues
- Provide sizing guidance
- Troubleshoot problems
- Escalate complex issues to human agents

**Inputs:**
- User question or issue description
- Context (order history, recent interactions)
- Urgency level (explicit or inferred)

**Outputs:**
- Helpful response message
- Suggested actions
- Escalation ticket (if needed)

**Example Interactions:**
```
User: "My order hasn't arrived"
→ Support Agent: Checks status, provides resolution

User: "Which size should I get?"
→ Support Agent: Provides sizing guidance based on user measurements

User: "The website isn't loading"
→ Support Agent: Troubleshoots, escalates if needed
```

## Agent Interaction Patterns

### 1. Sequential Processing
When a user request requires multiple agents, they execute in sequence:
```
User: "Find me blue running shoes under $100 and add to cart"
→ Product Agent: Filters products
→ Cart Agent: Adds selected product to cart
→ Response: Confirmation with both results
```

### 2. Parallel Processing
Independent agent tasks can run concurrently:
```
User: "Show my cart and order status"
→ Cart Agent: Fetches cart (parallel)
→ Order Agent: Fetches orders (parallel)
→ Response: Combined status
```

### 3. Handoff Pattern
Complex requests may require agent handoffs:
```
User: "I want to buy this but need help with sizing"
→ Product Agent: Provides product info
→ Support Agent: Takes over for sizing assistance
```

## Context Structure

Each agent receives a standardized context object:

```typescript
interface AgentContext {
  session: {
    id: string;
    userId: string | null;
    channel: 'web' | 'websocket' | 'api';
    startedAt: Date;
  };
  user: {
    id: string;
    preferences: UserPreferences;
    history: InteractionSummary;
  } | null;
  conversation: {
    messages: Message[];
    lastIntent: string;
    entities: ExtractedEntities;
  };
  cart: CartSummary | null;
}
```

## Response Format

All agents return standardized responses:

```typescript
interface AgentResponse {
  success: boolean;
  data: unknown;
  message?: string;
  nextActions?: SuggestedAction[];
  metadata?: {
    agent: string;
    processingTime: number;
    confidence?: number;
  };
}
```

## Error Handling

Agents should handle errors gracefully:
- Validation errors: Return clear message to user
- Service unavailable: Return fallback response or queue for retry
- Ambiguous intent: Ask clarifying questions

## Intent-to-Agent Mapping

| Intent Category | Primary Agent | Fallback |
|-----------------|---------------|----------|
| product_search | Product Agent | Support Agent |
| product_details | Product Agent | - |
| add_to_cart | Cart Agent | Product Agent |
| update_cart | Cart Agent | - |
| checkout | Order Agent | Cart Agent |
| order_status | Order Agent | - |
| general_question | Support Agent | Product Agent |

## Agent Caching

Agents may cache responses for:
- Frequently requested product details
- User preference lookups
- Recommendation results (with TTL)

Cache invalidation occurs on:
- Product inventory changes
- User preference updates
- TTL expiration
