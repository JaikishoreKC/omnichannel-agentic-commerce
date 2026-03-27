# Frontend Development Instructions

> React + TypeScript + Vite conventions for omnichannel-agentic-commerce.

## Stack And Scope
- Framework: React 18 with TypeScript
- Build: Vite
- Styling: Tailwind CSS
- Tests: Vitest + React Testing Library + Playwright
- API integration: Axios client + Context hooks

## Provider Hierarchy (Required)
Use this exact wrapping order in frontend/src/main.tsx:

```tsx
<SessionProvider>
  <AuthProvider>
    <CartProvider>
      <ChatProvider>
        <ToastProvider>
          <ThemeProvider>
            <App />
          </ThemeProvider>
        </ToastProvider>
      </ChatProvider>
    </CartProvider>
  </AuthProvider>
</SessionProvider>
```

Why this order matters:
1. Session initializes identifiers used downstream.
2. Auth consumes session context and hydrates user state.
3. Cart depends on auth/session for routing and ownership.
4. Chat and Toast consume upstream state.
5. Theme is UI-only and can be innermost.

## Project Layout

```text
frontend/
  src/
    main.tsx
    App.tsx
    styles.css
    api/
    components/
    context/
    pages/
    utils/
    types/
  tests/
    e2e/
```

Keep route-level code in pages, reusable UI in components, state in context, and all HTTP logic in api.

## Environment
Create frontend/.env from frontend/.env.example.

Recommended local values:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_VOICE_AGENT=false
VITE_ENABLE_PAYMENT_FORM=true
VITE_DEBUG_MODE=false
```

## Commands
From repo root:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend run test
npm --prefix frontend run test:e2e
```

## API Client Rules
In frontend/src/api/client.ts:
- Keep token hydration behavior intact (memory + localStorage).
- Inject Authorization and X-Session-ID headers in request interceptors.
- Handle 401 by clearing invalid auth and redirecting to login flow.
- Avoid direct fetch usage in components; call api helpers/hooks instead.

## State Management Rules
- Context state updates must be immutable.
- Keep context values typed and expose dedicated hooks (useAuth, useCart, useSession).
- Route modules should not own data-fetching side effects that belong in context/api hooks.

## Testing Guidance
- Component tests should assert behavior, not implementation details.
- Add Playwright tests for checkout, cart persistence, and auth hydration.
- If E2E fails, check provider order and session header propagation first.

## Common Pitfalls
- CORS errors: verify backend allows frontend origin.
- Empty cart after refresh: check session continuity and X-Session-ID propagation.
- Auth appears logged out after reload: check token hydration in api client and auth context.
- E2E flaky startup: ensure backend is healthy before launching Playwright.

## Quick Checklist
- [ ] frontend/.env exists with VITE_API_BASE_URL
- [ ] Dev server runs on port 5173
- [ ] Lint/build/tests pass
- [ ] Provider nesting in main.tsx matches required order
- [ ] Axios client preserves auth + session headers
