Tracked frontend files: 47

## Module dependency graph findings
- Layer edges (top 12): [('api->api', 19), ('app-shell->page', 11), ('composition-root->state', 6), ('state->state', 4), ('app-shell->layout', 1), ('app-shell->state', 1), ('layout->layout', 1), ('composition-root->app-shell', 1), ('composition-root->style', 1)]
- Circular dependencies detected: 0
- Highest fan-out modules: ['frontend/src/App.tsx', 'frontend/src/api/index.ts', 'frontend/src/main.tsx', 'frontend/src/context/CartContext.tsx', 'frontend/src/components/layout/Shell.tsx', 'frontend/src/context/ChatContext.tsx', 'frontend/src/api/auth.ts', 'frontend/src/api/cart.ts', 'frontend/src/api/interactions.ts', 'frontend/src/api/orders.ts', 'frontend/src/api/products.ts', 'frontend/src/api/admin.ts']
- Highest fan-in modules: ['frontend/src/api/client.ts', 'frontend/src/context/AuthContext.tsx', 'frontend/src/context/SessionContext.tsx', 'frontend/src/api/types.ts', 'frontend/src/context/ToastContext.tsx', 'frontend/src/components/layout/Shell.tsx', 'frontend/src/pages/AccountPage.tsx', 'frontend/src/pages/AdminDashboard.tsx', 'frontend/src/pages/AdminLoginPage.tsx', 'frontend/src/pages/AuthPage.tsx', 'frontend/src/pages/CartPage.tsx', 'frontend/src/pages/ForgotPasswordPage.tsx']
- Duplicate filename stems: {'types': ['frontend/src/api/types.ts', 'frontend/src/types.ts']}
- Potential duplicate logic buckets: {'auth': ['frontend/src/api/auth.ts', 'frontend/src/context/AuthContext.tsx', 'frontend/src/pages/AuthPage.tsx'], 'cart': ['frontend/src/api/cart.ts', 'frontend/src/context/CartContext.tsx', 'frontend/src/pages/CartPage.tsx']}

### frontend/src/App.tsx
- Purpose/layer: module `App` in `app-shell`.
- Key symbols + direct internal deps: AdminRoute, App, useAuth; deps: components.layout.Shell, context.AuthContext, pages.AccountPage, pages.AdminDashboard, pages.AdminLoginPage, pages.AuthPage.
- Architecture validation + notable risks: valid; high_internal_fan_out.

### frontend/src/api/admin.ts
- Purpose/layer: module `api.admin` in `api`.
- Key symbols + direct internal deps: AdminStats, AdminOrder, AdminProduct, AdminUser, ActivityLog, HealthStatus; deps: api.client.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/api/auth.ts
- Purpose/layer: module `api.auth` in `api`.
- Key symbols + direct internal deps: none; deps: api.client.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/api/cart.ts
- Purpose/layer: module `api.cart` in `api`.
- Key symbols + direct internal deps: none; deps: api.client.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/api/client.ts
- Purpose/layer: module `api.client` in `api`.
- Key symbols + direct internal deps: API_BASE, WS_BASE, SESSION_KEY, AUTH_KEY, REFRESH_KEY, token; deps: api.types.
- Architecture validation + notable risks: valid; console_logging.

### frontend/src/api/index.ts
- Purpose/layer: module `api.index` in `api`.
- Key symbols + direct internal deps: none; deps: api.admin, api.auth, api.cart, api.client, api.interactions, api.memory.
- Architecture validation + notable risks: valid; high_internal_fan_out.

### frontend/src/api/interactions.ts
- Purpose/layer: module `api.interactions` in `api`.
- Key symbols + direct internal deps: ChatHistoryPayload; deps: api.client.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/api/memory.ts
- Purpose/layer: module `api.memory` in `api`.
- Key symbols + direct internal deps: MemorySnapshot, MemoryHistoryEvent; deps: api.client.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/api/orders.ts
- Purpose/layer: module `api.orders` in `api`.
- Key symbols + direct internal deps: none; deps: api.client.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/api/products.ts
- Purpose/layer: module `api.products` in `api`.
- Key symbols + direct internal deps: PaginatedProducts; deps: api.client.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/api/sessions.ts
- Purpose/layer: module `api.sessions` in `api`.
- Key symbols + direct internal deps: none; deps: api.client.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/api/types.ts
- Purpose/layer: module `api.types` in `api`.
- Key symbols + direct internal deps: ChatResponsePayload; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/components/account/AiMemoryTab.tsx
- Purpose/layer: module `components.account.AiMemoryTab` in `feature-component`.
- Key symbols + direct internal deps: AiMemoryTab, useToast; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/components/account/SupportTicketsTab.tsx
- Purpose/layer: module `components.account.SupportTicketsTab` in `feature-component`.
- Key symbols + direct internal deps: SupportTicketsTab; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/components/account/WishlistTab.tsx
- Purpose/layer: module `components.account.WishlistTab` in `feature-component`.
- Key symbols + direct internal deps: WishlistTab; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/components/features/ChatPanel.tsx
- Purpose/layer: module `components.features.ChatPanel` in `feature-component`.
- Key symbols + direct internal deps: ChatPanel, useChat; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/components/features/ProductCard.tsx
- Purpose/layer: module `components.features.ProductCard` in `feature-component`.
- Key symbols + direct internal deps: ProductCard, useCart; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/components/layout/Navbar.tsx
- Purpose/layer: module `components.layout.Navbar` in `layout`.
- Key symbols + direct internal deps: Navbar, useAuth, useCart; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/components/layout/Shell.tsx
- Purpose/layer: module `components.layout.Shell` in `layout`.
- Key symbols + direct internal deps: Shell; deps: components.layout.Navbar.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/components/ui/Badge.tsx
- Purpose/layer: module `components.ui.Badge` in `ui`.
- Key symbols + direct internal deps: BadgeProps, Badge; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/components/ui/Button.tsx
- Purpose/layer: module `components.ui.Button` in `ui`.
- Key symbols + direct internal deps: ButtonProps, Button; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/components/ui/Input.tsx
- Purpose/layer: module `components.ui.Input` in `ui`.
- Key symbols + direct internal deps: InputProps, Input; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/components/ui/Modal.tsx
- Purpose/layer: module `components.ui.Modal` in `ui`.
- Key symbols + direct internal deps: Modal; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/components/ui/Skeleton.tsx
- Purpose/layer: module `components.ui.Skeleton` in `ui`.
- Key symbols + direct internal deps: Skeleton; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/components/ui/Toast.tsx
- Purpose/layer: module `components.ui.Toast` in `ui`.
- Key symbols + direct internal deps: Toast; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/context/AuthContext.tsx
- Purpose/layer: module `context.AuthContext` in `state`.
- Key symbols + direct internal deps: AuthContext, AuthProvider, useAuth; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/context/CartContext.tsx
- Purpose/layer: module `context.CartContext` in `state`.
- Key symbols + direct internal deps: CartContext, CartProvider, useCart, useAuth, useSession, useToast; deps: context.AuthContext, context.SessionContext, context.ToastContext.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/context/ChatContext.tsx
- Purpose/layer: module `context.ChatContext` in `state`.
- Key symbols + direct internal deps: Message, ChatContext, ChatProvider, useChat, useSession; deps: context.SessionContext.
- Architecture validation + notable risks: valid; type_safety_any_usage, console_logging.

### frontend/src/context/SessionContext.tsx
- Purpose/layer: module `context.SessionContext` in `state`.
- Key symbols + direct internal deps: SessionContext, SessionProvider, useSession; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/context/ThemeContext.tsx
- Purpose/layer: module `context.ThemeContext` in `state`.
- Key symbols + direct internal deps: ThemeContext, ThemeProvider, useTheme; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/context/ToastContext.tsx
- Purpose/layer: module `context.ToastContext` in `state`.
- Key symbols + direct internal deps: ToastType, ToastMessage, ToastContext, ToastProvider, useToast; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/main.tsx
- Purpose/layer: module `main` in `composition-root`.
- Key symbols + direct internal deps: none; deps: App, context.AuthContext, context.CartContext, context.ChatContext, context.SessionContext, context.ThemeContext.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/pages/AccountPage.tsx
- Purpose/layer: module `pages.AccountPage` in `page`.
- Key symbols + direct internal deps: AccountPage, useAuth; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/pages/AdminDashboard.tsx
- Purpose/layer: module `pages.AdminDashboard` in `page`.
- Key symbols + direct internal deps: StatusBadge, Skeleton, AdminDashboard, useAuth; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/pages/AdminLoginPage.tsx
- Purpose/layer: module `pages.AdminLoginPage` in `page`.
- Key symbols + direct internal deps: AdminLoginPage, useAuth; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/pages/AuthPage.tsx
- Purpose/layer: module `pages.AuthPage` in `page`.
- Key symbols + direct internal deps: AuthPage, useAuth; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/pages/CartPage.tsx
- Purpose/layer: module `pages.CartPage` in `page`.
- Key symbols + direct internal deps: CartPage, useAuth, useCart, useToast; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/pages/ForgotPasswordPage.tsx
- Purpose/layer: module `pages.ForgotPasswordPage` in `page`.
- Key symbols + direct internal deps: ForgotPasswordPage, useToast; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/pages/HomePage.tsx
- Purpose/layer: module `pages.HomePage` in `page`.
- Key symbols + direct internal deps: HomePage; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/pages/OrderDetailPage.tsx
- Purpose/layer: module `pages.OrderDetailPage` in `page`.
- Key symbols + direct internal deps: OrderDetailPage, useToast; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/pages/ProductDetailPage.tsx
- Purpose/layer: module `pages.ProductDetailPage` in `page`.
- Key symbols + direct internal deps: ProductDetailPage, useAuth, useCart, useToast; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/pages/ProductsPage.tsx
- Purpose/layer: module `pages.ProductsPage` in `page`.
- Key symbols + direct internal deps: ProductsPage; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/pages/ResetPasswordPage.tsx
- Purpose/layer: module `pages.ResetPasswordPage` in `page`.
- Key symbols + direct internal deps: ResetPasswordPage, useToast; deps: none.
- Architecture validation + notable risks: valid; type_safety_any_usage.

### frontend/src/styles.css
- Purpose/layer: module `styles` in `style`.
- Key symbols + direct internal deps: none; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/types.ts
- Purpose/layer: module `types` in `model`.
- Key symbols + direct internal deps: ProductVariant, Product, CartItem, Cart, AuthUser, AuthResponse; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/utils/cn.ts
- Purpose/layer: module `utils.cn` in `util`.
- Key symbols + direct internal deps: cn; deps: none.
- Architecture validation + notable risks: valid; none notable.

### frontend/src/vite-env.d.ts
- Purpose/layer: module `vite-env` in `config`.
- Key symbols + direct internal deps: none; deps: none.
- Architecture validation + notable risks: valid; none notable.
