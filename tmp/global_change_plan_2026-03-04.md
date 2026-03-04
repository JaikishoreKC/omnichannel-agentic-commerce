# Global Change Plan (2026-03-04)

## Scope principle
- Minimal, architecture-safe stabilization only.
- No architecture redesign, no framework additions, no schema changes.

## Affected files and coordinated plan

### frontend/src/components/account/AiMemoryTab.tsx
- Reason: Icon-only delete button lacks discernible accessible text.
- Changes:
  - Add `aria-label` and `title` for delete-memory action button.
- Dependency impact: None (DOM semantics only).
- Coordinated updates needed: None.

### frontend/src/pages/CartPage.tsx
- Reason: Multiple icon-only action buttons (quantity controls, remove item, close modal) lack discernible accessible text.
- Changes:
  - Add `aria-label` and `title` to icon-only buttons.
- Dependency impact: None (UI semantics only).
- Coordinated updates needed: None.

### frontend/src/pages/ProductsPage.tsx
- Reason: Icon-only controls for filters/view toggles lack accessible text.
- Changes:
  - Add `aria-label` and `title` to icon-only buttons.
- Dependency impact: None.
- Coordinated updates needed: None.

### frontend/src/pages/AdminLoginPage.tsx
- Reason: OTP per-digit inputs are missing explicit labels.
- Changes:
  - Add `aria-label` and `title` for each OTP digit input based on index.
- Dependency impact: None.
- Coordinated updates needed: None.

### backend/app/infrastructure/persistence_clients.py
- Reason: Runtime `print` statements for connectivity warnings bypass centralized logging.
- Changes:
  - Introduce module logger and replace `print` with `logger.warning`.
- Dependency impact: None (standard library logging).
- Coordinated updates needed: None.
