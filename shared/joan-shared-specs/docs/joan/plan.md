# Joan Development Plan

This document outlines planned features and milestones for Joan - Your Perfect Assistant.

---

## Authentication Enhancements

### Password Reset Flow
**Status:** Not Started | **Priority:** High

Implement forgot password functionality to allow users to reset their passwords via email.

- [ ] Create password reset request endpoint (backend)
- [ ] Create password reset confirmation endpoint (backend)
- [ ] Send password reset emails via Resend
- [ ] Create ForgotPasswordPage.tsx with email input form
- [ ] Create ResetPasswordPage.tsx with new password form
- [ ] Add password reset token storage and validation
- [ ] Add rate limiting to prevent abuse
- [ ] Update login page with working "Forgot password?" link

### Social Authentication
**Status:** Not Started | **Priority:** Medium

Enable users to sign in with third-party providers for frictionless onboarding.

**Providers:**
- [ ] Google OAuth 2.0
- [ ] Apple Sign In
- [ ] GitHub OAuth

**Tasks:**
- [ ] Set up OAuth credentials with each provider
- [ ] Create OAuth callback endpoints (backend)
- [ ] Implement account linking (social + email/password)
- [ ] Handle first-time social sign-in (auto-create account)
- [ ] Update login page social buttons with real functionality

### Remember Me Functionality
**Status:** Not Started | **Priority:** Low

Extend session duration when "Remember me" is checked during login.

- [ ] Implement longer-lived refresh tokens
- [ ] Update JWT token generation based on remember me flag
- [ ] Handle token refresh flow gracefully

---

## Design System Refinements

### Global Component Updates
**Status:** In Progress | **Priority:** Medium

Roll out the new Joan design system (glassmorphism, coral accent colors) across all pages.

**Completed:**
- [x] Updated Tailwind config with Joan color palette (coral, amber, teal, dark)
- [x] Created glassmorphism utility classes (glass-card, glass-input, glass-button-*)
- [x] Created JoanLogo SVG component (pixel art style)
- [x] Redesigned LoginPage with new aesthetic
- [x] Redesigned VerifyEmailPage with new aesthetic

**Remaining:**
- [ ] Update navigation components with new design tokens
- [ ] Update modal components with glassmorphism
- [ ] Update form components throughout app
- [ ] Create consistent button component library
- [ ] Update loading states and spinners
- [ ] Review and update all page backgrounds

### Light Mode Polish
**Status:** Not Started | **Priority:** Low

Ensure light mode looks equally stunning with the new design system.

- [ ] Review all glassmorphism components in light mode
- [ ] Adjust opacity and blur values for light backgrounds
- [ ] Test contrast ratios for accessibility

---

## Mobile Experience

### Progressive Web App (PWA)
**Status:** Not Started | **Priority:** Medium

Make Joan installable as a PWA for mobile devices.

- [ ] Create manifest.json with app metadata
- [ ] Generate app icons in required sizes
- [ ] Implement service worker for offline support
- [ ] Add install prompt handling
- [ ] Test on iOS and Android devices

### Push Notifications
**Status:** Not Started | **Priority:** Medium

Enable push notifications for timer completion, task reminders, etc.

- [ ] Implement push notification subscription (backend)
- [ ] Set up web push with Cloudflare Workers
- [ ] Create notification permission request flow
- [ ] Add notification preferences in settings
- [ ] Implement timer completion notifications
- [ ] Implement task due date reminders

---

## Technical Hardening & Resilience

- Add a global error boundary with route-level suspense/skeleton fallbacks and abortable fetches to prevent blank screens and stale state.
- Introduce mutation helpers with optimistic updates, retries, and clear toasts for project/client/task changes.
- Add pagination or infinite scroll plus server-side filtering/sorting for large project/client lists.
- Implement permission-aware UI states (disable/hide mutation actions when user lacks access).
- Improve accessibility: focus traps/restore on modals and menus, aria labels for icon-only controls, and keyboard-first navigation.
- Add client-side observability (error reporting + performance telemetry) around key flows.
- Virtualize large lists (projects, session history) to keep mobile smooth.
- Add integration tests for auth redirects, project CRUD, timer logging, and ceremony flows.

---

## Notes

- All authentication changes should maintain backward compatibility
- Social auth should not be mandatory - email/password always available
- Design changes should be incremental to avoid breaking existing user workflows
- Mobile-first approach for all new features
