# Product Requirements Document  
## E-Commerce Full-Stack Application

| Field | Value |
|---|---|
| Document Version | 1.0 |
| Status | Draft |
| Author | Engineering Team |
| Date | April 24, 2026 |
| Frontend Ref | `/module6-project` (React 19 · TypeScript · Vite · Tailwind CSS 4) |
| QA Ref | `/module8-project/cursorAI-module8-gperez` |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)  
2. [Product Goals & Success Metrics](#2-product-goals--success-metrics)  
3. [User Personas](#3-user-personas)  
4. [System Architecture Overview](#4-system-architecture-overview)  
5. [Functional Requirements](#5-functional-requirements)  
   - 5.1 Authentication & User Management  
   - 5.2 Product Catalog  
   - 5.3 Shopping Cart  
   - 5.4 Discount & Promotions  
   - 5.5 Checkout & Payment Processing  
   - 5.6 Order Management  
   - 5.7 Email Notifications  
   - 5.8 Dashboard & Analytics  
   - 5.9 Kanban Board  
   - 5.10 Social Feed  
   - 5.11 Settings & Preferences  
6. [Non-Functional Requirements](#6-non-functional-requirements)  
7. [Proposed API Endpoints](#7-proposed-api-endpoints)  
8. [Test Coverage Alignment](#8-test-coverage-alignment)  
9. [Security Requirements](#9-security-requirements)  
10. [Out of Scope (MVP)](#10-out-of-scope-mvp)  
11. [Open Questions](#11-open-questions)  

---

## 1. Executive Summary

This document defines the product requirements for a **full-stack e-commerce application** whose frontend is built with React 19/TypeScript (module6-project) and whose quality is validated by a comprehensive automated QA system (module8-project). The application must be production-ready, free of critical bugs, and expose a well-defined REST API (`/api/v1`) that satisfies all test cases in the module8 test suite.

The core commerce functionality covers user registration and authentication, a searchable product catalog, a persistent shopping cart, discount codes, multi-method payment processing (credit card / PayPal / saved card), order lifecycle management, and transactional email notifications. Secondary functional areas — a metrics dashboard, analytics charts, a Kanban board, a social feed, and a settings panel — complete the application surface.

---

## 2. Product Goals & Success Metrics

### 2.1 Goals

| # | Goal |
|---|---|
| G-1 | Deliver a fully functional e-commerce checkout flow with zero critical bugs. |
| G-2 | All 45 checkout test cases in `Exercise_1/test-cases/checkout_test_cases.md` pass in CI. |
| G-3 | All API tests in `Exercise_2/tests/api.test.js` pass against the live backend. |
| G-4 | All E2E tests in `Exercise_4/tests/e2e/checkout.e2e.test.js` pass against the running app. |
| G-5 | API response time < 500 ms for all listed endpoints (PERF-001–005). |
| G-6 | Zero critical security vulnerabilities (OWASP Top 10 coverage, PCI-DSS compliance for payment data). |
| G-7 | Code quality: test coverage ≥ 80 %, cyclomatic complexity < 10, error rate < 1 %. |

### 2.2 Success Metrics

| Metric | Target |
|---|---|
| Test suite pass rate | 100 % (active test cases only) |
| API p95 response time | < 500 ms |
| Payment success rate (valid cards) | ≥ 99.5 % |
| Cart-to-purchase conversion (test env) | Measurable & tracked |
| Security scan critical findings | 0 |
| CI pipeline duration | ≤ original baseline × 0.50 |

---

## 3. User Personas

### 3.1 Guest Shopper
- Not logged in.
- Can browse the product catalog, search, filter, and sort.
- Can add items to a session cart.
- Must register or log in to complete checkout.

### 3.2 Registered Customer
- Logged-in user (`role: "user"`).
- Can do everything a Guest Shopper can, plus:
  - Complete checkout with credit card, PayPal, or a saved payment method.
  - Apply discount codes.
  - View order history and track order status.
  - Manage profile, saved addresses, and saved payment methods.
  - Access the dashboard, analytics, Kanban board, social feed, and settings pages.

### 3.3 Admin / Store Manager
- Logged-in user (`role: "admin"`).
- All Registered Customer capabilities, plus:
  - Create, update, and delete products (including price, stock, category, images).
  - View and manage all users.
  - Update order status (Processing → Shipped → Delivered → Cancelled).
  - Access protected admin-only endpoints.

---

## 4. System Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│                    Client (Browser)                    │
│  React 19 · TypeScript · Vite 8 · Tailwind CSS 4       │
│  Hash-based router: /, /products, /dashboard,          │
│  /analytics, /kanban, /feed, /settings                 │
│  + /cart, /checkout, /login, /register, /orders        │
└──────────────────┬─────────────────────────────────────┘
                   │  HTTPS · REST JSON
                   ▼
┌────────────────────────────────────────────────────────┐
│                 Backend API Server                     │
│  Base path: /api/v1                                    │
│  Auth: JWT Bearer tokens                               │
│  Rate limiting, CSRF protection, input sanitization    │
└──────┬───────────────────────────┬─────────────────────┘
       │                           │
       ▼                           ▼
┌─────────────┐           ┌──────────────────┐
│  Database   │           │  Payment Gateway  │
│  (SQL/NoSQL)│           │  (Stripe / PayPal)│
│  Users      │           └──────────────────┘
│  Products   │                    │
│  Orders     │           ┌────────▼─────────┐
│  Cart       │           │  Email Service    │
│  Discounts  │           │  (order confirm,  │
└─────────────┘           │   shipping alerts)│
                          └──────────────────┘
```

**Tech constraints from the test suite:**
- API base URL: `http://localhost:3000/api/v1` (configurable via `BASE_URL` env var).
- JWT authentication with `Authorization: Bearer <token>` header.
- Response format: `Content-Type: application/json`.
- Idempotency key support on payment submission (prevents duplicate charges on browser back).

### Frontend reference implementation (`module6-project`)

| Area | Status |
|------|--------|
| Hash routes `#/cart`, `#/checkout`, `#/checkout/success` | Implemented in `App.tsx`. |
| Navbar cart control (`#/cart`), count badge, mobile menu cart link | Implemented. |
| Global cart (`CartContext`) with `localStorage` persistence; discount codes (demo: SAVE10, SAVE20, WELCOME) | Implemented. |
| Product catalog add-to-cart | Implemented (`ProductDemo` + `ProductCard`). |
| Checkout shipping step | Collects `firstName`, `lastName`, `email`, street address, city, state, ZIP, **ISO 3166-1 alpha-2** country (matches API `ShippingAddressSchema`). |
| Checkout payment step + `POST /api/v1/checkout` | Sends `paymentToken`, `idempotencyKey`, optional `discountCode`, `X-CSRF-Token` when present; **401/402/403/400** show an inline error; network or non-API environments use a **local confirmation fallback** so E2E and static hosting keep working. |
| API clients | `src/api/checkoutApi.ts`, `cartApi.ts`, `ordersApi.ts` align with `/api/v1` contracts. |
| Auth login compatibility | Accepts `token` or `access_token`; stores CSRF from login/register when provided. |

**Backend (this repo):** After a successful `POST /checkout`, an order-confirmation email task is **queued** via Celery (`send_order_confirmation`) when the broker is available; failures to queue are logged and do not roll back the order.

---

## 5. Functional Requirements

### 5.1 Authentication & User Management

#### Registration
| ID | Requirement |
|---|---|
| AUTH-FR-001 | The system shall allow any visitor to register with a unique email address and a password meeting complexity rules (min 8 chars, at least one digit, one special character). |
| AUTH-FR-002 | On successful registration the system shall respond with a JWT and the new user object (`id`, `email`, `role`). |
| AUTH-FR-003 | Registration with a duplicate email shall return `409 Conflict`. |
| AUTH-FR-004 | The registration form (frontend) shall validate email format and password strength client-side before submission, matching `tests/registration.spec.ts`. |

#### Login / Logout
| ID | Requirement |
|---|---|
| AUTH-FR-005 | `POST /auth/login` shall accept `{ email, password }` and return `{ token }` with HTTP 200 on valid credentials. |
| AUTH-FR-006 | Invalid credentials shall return HTTP 401 with no token in the response body. |
| AUTH-FR-007 | `POST /auth/logout` shall invalidate the supplied JWT server-side; subsequent requests with that token return 401. |
| AUTH-FR-008 | Expired or malformed JWTs shall return HTTP 401. |
| AUTH-FR-009 | Login endpoint shall enforce rate limiting; exceeding the threshold returns HTTP 429 with a `Retry-After` header. |

#### User Profile
| ID | Requirement |
|---|---|
| AUTH-FR-010 | `GET /users/me` shall return the authenticated user's profile (`id`, `email`, `firstName`, `lastName`, `role`, `savedCards`, `savedAddresses`). |
| AUTH-FR-011 | `PUT /users/me` shall allow the authenticated user to update `firstName`, `lastName`, and `savedAddresses`. Field length shall be validated (max 255 chars). |
| AUTH-FR-012 | Admin-only: `GET /users` shall return a paginated list of all users. |
| AUTH-FR-013 | Admin-only: `POST /users`, `GET /users/:id`, `PUT /users/:id`, `DELETE /users/:id` for full CRUD. |

---

### 5.2 Product Catalog

| ID | Requirement |
|---|---|
| PROD-FR-001 | The catalog page (`/products`) shall display all available products, 3 per page with Previous / Next pagination. |
| PROD-FR-002 | Users shall be able to search products by title or description (case-insensitive, debounced 300 ms in the navbar). |
| PROD-FR-003 | Users shall be able to filter by **category** (Electronics, Accessories, Footwear, Office) and **price range** (under $100 / $100–$200 / over $200). |
| PROD-FR-004 | Users shall be able to sort by: Featured, Price low→high, Price high→low, Rating, Name A–Z, Name Z–A. |
| PROD-FR-005 | Each product card shall display: `id`, `image`, `title`, `description`, `price`, `rating`, `reviewCount`, and optionally a `badge`. |
| PROD-FR-006 | `GET /products` shall support query parameters: `page`, `limit`, `search`, `category`, `minPrice`, `maxPrice`, `sortBy`, `sortOrder`. |
| PROD-FR-007 | `GET /products/:id` shall return a single product or `404` if not found. |
| PROD-FR-008 | Admin-only: `POST /products`, `PUT /products/:id`, `DELETE /products/:id` for catalog management. |
| PROD-FR-009 | Creating a product with a negative price shall return `400 Bad Request`. |
| PROD-FR-010 | Deleting a product shall not corrupt existing orders that reference it; the product name/price shall be snapshotted in the order line item. |

---

### 5.3 Shopping Cart

| ID | Requirement |
|---|---|
| CART-FR-001 | Any visitor (guest or authenticated) shall be able to add items to a cart; the cart count in the navbar updates immediately. |
| CART-FR-002 | Cart contents shall persist across page refreshes (server-side for authenticated users; `localStorage` / session for guests). |
| CART-FR-003 | `POST /cart/items` shall add an item (`productId`, `quantity`) to the active cart and return the updated cart. |
| CART-FR-004 | `PUT /cart/items/:itemId` shall update the quantity of a cart line item. Quantities ≤ 0 remove the item. |
| CART-FR-005 | `DELETE /cart/items/:itemId` shall remove a specific item from the cart. |
| CART-FR-006 | `GET /cart` shall return the current cart with `items[]`, `subtotal`, `discount`, `total`. |
| CART-FR-007 | Maximum quantity per line item is **10 units**; exceeding this shall return an error "Maximum quantity allowed is 10." |
| CART-FR-008 | Adding an out-of-stock item shall return an error and not add the item. |
| CART-FR-009 | If a previously added item goes out of stock before checkout, the checkout endpoint shall detect this and return an actionable error. |

---

### 5.4 Discount & Promotions

| ID | Requirement |
|---|---|
| DISC-FR-001 | `POST /cart/discount` shall accept a discount code and, if valid, apply it to the current cart. |
| DISC-FR-002 | `DELETE /cart/discount` shall remove the currently applied discount code, restoring the original subtotal. |
| DISC-FR-003 | The system shall support **percentage** discount codes (e.g., `SAVE10` → 10 % off) and **fixed-amount** codes (e.g., `FLAT5` → $5 off). |
| DISC-FR-004 | Expired discount codes shall return the error "This discount code has expired." |
| DISC-FR-005 | Non-existent discount codes shall return the error "Invalid discount code." |
| DISC-FR-006 | Single-use codes already redeemed by the user shall return the error "This code has already been used." |
| DISC-FR-007 | If a discount brings the order total below $0.00, the total shall be capped at **$0.00**; no negative charge shall be issued. |
| DISC-FR-008 | Input to the discount field shall be sanitized to prevent SQL injection (see TC-S-001). |

---

### 5.5 Checkout & Payment Processing

| ID | Requirement |
|---|---|
| CHK-FR-001 | A guest user who attempts to proceed to checkout shall be redirected to login/register. |
| CHK-FR-002 | An empty cart shall prevent checkout; the checkout button is disabled or the checkout route redirects with "Your cart is empty." |
| CHK-FR-003 | The checkout flow shall collect a **shipping address** (`firstName`, `lastName`, `email`, `street`, `city`, `state`, `zip`, `country`) before showing the payment step. |
| CHK-FR-004 | Missing shipping address shall block payment and return a validation error. |
| CHK-FR-005 | The payment step shall support: **Credit/Debit card** (Visa, Mastercard), **PayPal**, and **saved card on file**. |
| CHK-FR-006 | `POST /checkout` shall accept `{ items, shippingAddress, paymentToken | paypalToken | savedCardId, discountCode?, idempotencyKey }` and process the order atomically. |
| CHK-FR-007 | On success the endpoint shall return `{ orderId, confirmationNumber, estimatedDelivery, total }` with HTTP 201. |
| CHK-FR-008 | Payment failures shall return descriptive errors without creating an order: "insufficient funds", "expired card", "security code incorrect", "card declined". |
| CHK-FR-009 | The backend shall **always use server-side pricing**; any client-submitted `price` or `total` field shall be ignored to prevent price manipulation (TC-S-010). |
| CHK-FR-010 | Payment submissions shall require a valid **CSRF token**; requests without one return HTTP 403 (TC-S-007). |
| CHK-FR-011 | **Idempotency**: resubmitting a payment with the same `idempotencyKey` shall return the original order without creating a duplicate charge (TC-E-010). |
| CHK-FR-012 | If the cart total is exactly $0.00 (full discount), checkout shall complete without requiring a payment method (TC-E-008). |
| CHK-FR-013 | Card numbers and CVVs shall **never** be stored in plaintext; only the payment gateway token and last-4 digits are persisted (TC-S-004, TC-S-005). |

---

### 5.6 Order Management

| ID | Requirement |
|---|---|
| ORD-FR-001 | `GET /orders` shall return the authenticated user's order history (paginated). |
| ORD-FR-002 | `GET /orders/:id` shall return a single order; a user may only access their own orders. |
| ORD-FR-003 | Attempting to access another user's order shall return HTTP 403 or 404 (TC-S-008 — implementation required even if currently disabled in test suite). |
| ORD-FR-004 | Order objects shall include: `orderId`, `status`, `items[]`, `shippingAddress`, `paymentMethod { token, last4 }`, `subtotal`, `discount`, `total`, `estimatedDelivery`, `createdAt`. |
| ORD-FR-005 | Admin-only: `PUT /orders/:id` shall allow updating `status` (Processing → Shipped → Delivered → Cancelled). |
| ORD-FR-006 | Admin-only: `DELETE /orders/:id` shall cancel an order. |
| ORD-FR-007 | The frontend `/dashboard` and `/analytics` pages shall consume order and metrics data from the API. |
| ORD-FR-008 | Order status `"Processing"` shall be set immediately upon successful checkout. |

---

### 5.7 Email Notifications

| ID | Requirement |
|---|---|
| EMAIL-FR-001 | A **transactional order-confirmation email** shall be sent to the customer's email address within 2 minutes of a successful checkout (TC-P-014). |
| EMAIL-FR-002 | The confirmation email shall contain: order ID, itemized list, total, and a support link. |
| EMAIL-FR-003 | When an admin sets order status to `"Shipped"`, a **shipping notification email** shall be sent with a tracking number and carrier link (TC-P-015). |
| EMAIL-FR-004 | Email delivery shall be handled asynchronously (queue/background job) to avoid blocking the checkout response. |

---

### 5.8 Dashboard & Analytics

| ID | Requirement |
|---|---|
| DASH-FR-001 | The `/dashboard` route shall display key KPI cards: total orders, revenue, active users, and pending shipments. |
| DASH-FR-002 | `GET /dashboard/stats` shall return aggregated metrics consumed by the Dashboard page. |
| DASH-FR-003 | The `/analytics` route shall display time-series charts (orders per day, revenue per day). |
| DASH-FR-004 | `GET /analytics/timeseries` shall return date-bucketed data (configurable range via `from` and `to` query params). |
| DASH-FR-005 | Dashboard routes shall require authentication; unauthenticated access redirects to login. |

---

### 5.9 Kanban Board

| ID | Requirement |
|---|---|
| KANBAN-FR-001 | The `/kanban` route shall display a multi-column task board (e.g., Backlog, In Progress, Done). |
| KANBAN-FR-002 | `GET /kanban/boards/:boardId/tasks` shall return all tasks grouped by column. |
| KANBAN-FR-003 | `POST /kanban/boards/:boardId/tasks`, `PUT /kanban/tasks/:taskId`, `DELETE /kanban/tasks/:taskId` shall support full task CRUD. |
| KANBAN-FR-004 | `PUT /kanban/tasks/:taskId/move` shall move a task to a different column (drag-and-drop action). |

---

### 5.10 Social Feed

| ID | Requirement |
|---|---|
| FEED-FR-001 | The `/feed` route shall display a scrollable feed of user posts with avatar, author name, content, and interactions. |
| FEED-FR-002 | `GET /feed/posts` shall return a paginated list of posts (newest first). |
| FEED-FR-003 | `POST /feed/posts` shall allow authenticated users to create a post. |
| FEED-FR-004 | `POST /users/:id/follow` and `DELETE /users/:id/follow` shall manage follow relationships; a user's `stats.followers` count shall update accordingly. |
| FEED-FR-005 | User objects shall expose: `id`, `name`, `username`, `avatarUrl`, `bio`, `stats { posts, followers, following }`, `isFollowing`. |

---

### 5.11 Settings & Preferences

| ID | Requirement |
|---|---|
| SET-FR-001 | The `/settings` route shall allow users to update: display name, password, notification preferences, and privacy settings. |
| SET-FR-002 | `PUT /users/me/settings` shall persist user preferences (notification toggles, privacy options). |
| SET-FR-003 | **Dark / Light mode** preference shall be stored in `localStorage` on the client and applied before React mounts (no theme flash). |
| SET-FR-004 | `GET /users/me/settings` shall return the current user's persisted settings. |

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | All API endpoints must respond in < 500 ms at p95 (PERF-001–005). |
| **Scalability** | The backend should support horizontal scaling; no in-process session state. |
| **Availability** | Target 99.9 % uptime for production deployment. |
| **Security** | All checkout pages served over HTTPS. JWT expiry enforced. Input sanitization on all user-supplied fields. CSRF protection on state-changing endpoints. |
| **PCI-DSS** | Raw card numbers and CVVs must never be written to database or logs. Only gateway tokens and last-4 digits stored. |
| **Rate Limiting** | Login endpoint: max 10 requests / min per IP. General API: max 100 requests / min per token. Returns HTTP 429 with `Retry-After` header. |
| **Accessibility** | Frontend passes `tests/accessibility.spec.ts`; WCAG 2.1 AA compliance for all interactive elements. |
| **Code Quality** | ESLint rules pass with zero errors. Cyclomatic complexity < 10. Test coverage ≥ 80 %. |
| **Error Handling** | 5xx responses must include a safe `{ error: string }` body with no stack traces exposed to the client. |
| **Idempotency** | Payment submissions support an `idempotencyKey` to prevent duplicate charges on retry/back-button scenarios. |

---

## 7. Proposed API Endpoints

All endpoints are prefixed with `/api/v1`. Authentication is via `Authorization: Bearer <token>` unless marked **Public**.

### 7.1 Authentication

| Method | Path | Auth | Description | Test Reference |
|---|---|---|---|---|
| POST | `/auth/register` | Public | Register a new user. Body: `{ email, password, firstName?, lastName? }`. Returns `{ token, user }`. | registration.spec.ts |
| POST | `/auth/login` | Public | Authenticate and obtain JWT. Body: `{ email, password }`. Returns `{ token }`. | AUTH-001–007 |
| POST | `/auth/logout` | User | Invalidate the current JWT. | AUTH-007 |
| POST | `/auth/refresh` | User | Exchange a valid (non-expired) token for a new one with a reset TTL. | — |

---

### 7.2 Users

| Method | Path | Auth | Description | Test Reference |
|---|---|---|---|---|
| GET | `/users` | Admin | List all users (paginated). Query: `page`, `limit`, `search`. | AUTHZ-001, USER-001 |
| POST | `/users` | Admin | Create a user. Body: `{ email, password, role }`. | USER-001 |
| GET | `/users/me` | User | Get own profile. | AUTHZ-005, PERF-005 |
| PUT | `/users/me` | User | Update own profile (`firstName`, `lastName`). | USER-003 |
| GET | `/users/me/settings` | User | Get notification and privacy settings. | SET-FR-004 |
| PUT | `/users/me/settings` | User | Update notification and privacy settings. | SET-FR-002 |
| GET | `/users/:id` | Admin | Get any user by ID. | USER-002 |
| PUT | `/users/:id` | Admin | Update any user. | USER-003 |
| DELETE | `/users/:id` | Admin | Delete a user. | AUTHZ-003, USER-004 |
| GET | `/users/:id/orders` | Admin | List all orders for a specific user. | AUTHZ-006 |
| POST | `/users/:id/follow` | User | Follow a user. Updates follower/following counts. | FEED-FR-004 |
| DELETE | `/users/:id/follow` | User | Unfollow a user. | FEED-FR-004 |

---

### 7.3 Products

| Method | Path | Auth | Description | Test Reference |
|---|---|---|---|---|
| GET | `/products` | Public | List products. Query: `page`, `limit`, `search`, `category`, `minPrice`, `maxPrice`, `sortBy`, `sortOrder`. Returns `{ products[], total, page, limit }`. | PROD-001, PERF-001, RATE-003 |
| GET | `/products/:id` | Public | Get a single product. Returns `404` if not found. | PROD-002, ERR-001, PERF-002 |
| POST | `/products` | Admin | Create a product. Body: `{ name, description, price, stock, category, imageUrl, badge? }`. | AUTHZ-007, PROD-003 |
| PUT | `/products/:id` | Admin | Update a product (partial update supported). | PROD-004 |
| DELETE | `/products/:id` | Admin | Soft-delete a product (preserves order history). | PROD-005 |

---

### 7.4 Cart

| Method | Path | Auth | Description | Test Reference |
|---|---|---|---|---|
| GET | `/cart` | User/Guest | Get the current cart. Returns `{ items[], subtotal, discount, total }`. | TC-P-001–004 |
| POST | `/cart/items` | User/Guest | Add an item. Body: `{ productId, quantity }`. | TC-P-001–002 |
| PUT | `/cart/items/:itemId` | User/Guest | Update item quantity. Body: `{ quantity }`. Quantity 0 removes the item. | TC-P-003, TC-E-004 |
| DELETE | `/cart/items/:itemId` | User/Guest | Remove an item from the cart. | TC-P-004 |
| POST | `/cart/discount` | User | Apply a discount code. Body: `{ code }`. Returns updated totals or error. | TC-P-005–007, TC-N-005–007, TC-S-001 |
| DELETE | `/cart/discount` | User | Remove the active discount code. | TC-P-007 |

---

### 7.5 Checkout & Orders

| Method | Path | Auth | Description | Test Reference |
|---|---|---|---|---|
| POST | `/checkout` | User | Place an order. Body: `{ items[], shippingAddress, paymentToken \| paypalToken \| savedCardId, discountCode?, idempotencyKey }`. Returns `{ orderId, confirmationNumber, total, estimatedDelivery }`. | TC-P-008–013, TC-N-001–010, TC-E-001–010, TC-S-001–010, ORDER-001 |
| GET | `/orders` | User | List own orders (paginated). Returns `{ orders[], total }`. | ORDER-003, PERF-003 |
| GET | `/orders/:id` | User | Get a single order (own only). Returns `404` or `403` for other users' orders. | ORDER-002, TC-S-008 |
| PUT | `/orders/:id` | Admin | Update order status. Body: `{ status }`. Triggers shipping email when status → "Shipped". | ORDER-004, TC-P-015 |
| DELETE | `/orders/:id` | Admin | Cancel an order. | ORDER-005 |

---

### 7.6 Dashboard & Analytics

| Method | Path | Auth | Description | Test Reference |
|---|---|---|---|---|
| GET | `/dashboard/stats` | User | Aggregate KPIs: `{ totalOrders, revenue, activeUsers, pendingShipments }`. | DASH-FR-002 |
| GET | `/analytics/timeseries` | User | Time-series data. Query: `from`, `to`, `metric` (orders \| revenue). | DASH-FR-004 |

---

### 7.7 Kanban Board

| Method | Path | Auth | Description | Test Reference |
|---|---|---|---|---|
| GET | `/kanban/boards` | User | List all boards for the current user. | KANBAN-FR-002 |
| POST | `/kanban/boards` | User | Create a new board. Body: `{ name, columns[] }`. | KANBAN-FR-003 |
| GET | `/kanban/boards/:boardId/tasks` | User | Get all tasks grouped by column. | KANBAN-FR-002 |
| POST | `/kanban/boards/:boardId/tasks` | User | Create a task. Body: `{ title, description?, columnId, assignee? }`. | KANBAN-FR-003 |
| PUT | `/kanban/tasks/:taskId` | User | Update task title, description, or assignee. | KANBAN-FR-003 |
| PUT | `/kanban/tasks/:taskId/move` | User | Move task to a different column. Body: `{ columnId }`. | KANBAN-FR-004 |
| DELETE | `/kanban/tasks/:taskId` | User | Delete a task. | KANBAN-FR-003 |

---

### 7.8 Social Feed

| Method | Path | Auth | Description | Test Reference |
|---|---|---|---|---|
| GET | `/feed/posts` | User | Paginated feed of posts (newest first). Query: `page`, `limit`. | FEED-FR-002 |
| POST | `/feed/posts` | User | Create a post. Body: `{ content }`. | FEED-FR-003 |
| DELETE | `/feed/posts/:postId` | User/Admin | Delete own post (Admin can delete any). | FEED-FR-003 |

---

### 7.9 Admin Utilities

| Method | Path | Auth | Description | Test Reference |
|---|---|---|---|---|
| POST | `/admin/trigger-test-error` | Admin | Test endpoint that intentionally triggers a 500 response; verifies error format (no stack trace). | ERR-005 |

---

### 7.10 Endpoint Summary Table

| Domain | Endpoints | Public | User | Admin |
|---|---|---|---|---|
| Auth | 4 | 2 | 1 | 0 |
| Users | 12 | 0 | 6 | 6 |
| Products | 5 | 2 | 0 | 3 |
| Cart | 6 | 2 | 4 | 0 |
| Checkout / Orders | 5 | 0 | 3 | 2 |
| Dashboard / Analytics | 2 | 0 | 2 | 0 |
| Kanban | 7 | 0 | 7 | 0 |
| Social Feed | 3 | 0 | 2 | 1 |
| Admin Utilities | 1 | 0 | 0 | 1 |
| **Total** | **45** | **6** | **25** | **13** |

---

## 8. Test Coverage Alignment

### 8.1 Module 8 – Exercise 1: Checkout Test Cases

All 38 active test cases (out of 45 total) defined in `Exercise_1/test-cases/checkout_test_cases.md` must pass. The 7 disabled tests (TC-E-005, TC-E-006, TC-E-007, TC-E-009, TC-S-006, TC-S-008, TC-S-009) are deferred to a post-MVP sprint but the API must be architected to support them.

| Category | Active Cases | API Endpoints Required |
|---|---|---|
| Positive – Cart | TC-P-001 to TC-P-004 | `POST /cart/items`, `PUT /cart/items/:id`, `DELETE /cart/items/:id` |
| Positive – Discounts | TC-P-005 to TC-P-007 | `POST /cart/discount`, `DELETE /cart/discount` |
| Positive – Payment | TC-P-008 to TC-P-011 | `POST /checkout` |
| Positive – Orders/Email | TC-P-012 to TC-P-015 | `GET /orders/:id`, `PUT /orders/:id` (admin status update triggers email) |
| Negative – Payment | TC-N-001 to TC-N-004 | `POST /checkout` (payment gateway error handling) |
| Negative – Discounts | TC-N-005 to TC-N-007 | `POST /cart/discount` |
| Negative – Validation | TC-N-008 to TC-N-010 | `POST /checkout` (server-side validation) |
| Edge Cases | TC-E-001–004, TC-E-008, TC-E-010 | `POST /checkout`, `PUT /cart/items/:id` |
| Security | TC-S-001–005, TC-S-007, TC-S-010 | `POST /cart/discount`, `POST /checkout` |

### 8.2 Module 8 – Exercise 2: API Test Suite

All tests in `Exercise_2/tests/api.test.js` must pass. Key mapping:

| Test Group | Endpoints Covered |
|---|---|
| Authentication (AUTH-001–007) | `/auth/login`, `/auth/logout`, `/users/me` |
| Authorization (AUTHZ-001–008) | `/users`, `/users/:id`, `/products` |
| CRUD Users (USER-001–005) | `/users`, `/users/:id` |
| CRUD Products (PROD-001–005) | `/products`, `/products/:id` |
| CRUD Orders (ORDER-001–005) | `/orders`, `/orders/:id` |
| Input Validation (VAL-001–006) | `/users`, `/products`, `/orders` |
| Error Handling (ERR-001–005) | All endpoints + `/admin/trigger-test-error` |
| Performance (PERF-001–005) | `/products`, `/orders`, `/auth/login`, `/users/me` |
| Rate Limiting (RATE-001–003) | `/auth/login`, `/products` |

### 8.3 Module 8 – Exercise 4: E2E Checkout Tests (POM)

The Page Object Model tests in `Exercise_4/tests/e2e/checkout.e2e.test.js` require the following pages to be implemented in the frontend (extending the existing module6-project router):

| POM Test Group | Required Frontend Routes | Required API Calls |
|---|---|---|
| POM-P: Positive Checkout | `/login`, `/` (home/products), `/cart`, `/checkout`, `/checkout/success` | Login, cart, checkout endpoints |
| POM-N: Negative Checkout | Same routes; error state rendering | Checkout error handling |
| POM-E: Edge Cases | Empty cart state, search no-results | `GET /products?search=...` |
| POM-S: Security | XSS sanitization, HTTPS enforcement | All |

### 8.4 Module 6 – Existing Frontend Test Coverage

The existing Playwright tests in `module6-project/tests/` must continue to pass after backend integration:

| Test File | Feature | Backend Dependency |
|---|---|---|
| `search.spec.ts` | Product search | `GET /products?search=` |
| `filters.spec.ts` | Category / price filters | `GET /products?category=&minPrice=&maxPrice=` |
| `sort.spec.ts` | Sort order | `GET /products?sortBy=&sortOrder=` |
| `pagination.spec.ts` | Page navigation | `GET /products?page=&limit=` |
| `navigation.spec.ts` | Hash-router nav | None (client-only) |
| `registration.spec.ts` | Registration form | `POST /auth/register` |
| `validation.spec.ts` | Form validation | Client-side + `POST /auth/register` |
| `accessibility.spec.ts` | A11y | None (client-only) |

---

## 9. Security Requirements

| ID | Requirement | Test Reference |
|---|---|---|
| SEC-001 | All form inputs (search, discount, address, login) must be sanitized against SQL injection. | TC-S-001, TC-S-002, POM-S-002 |
| SEC-002 | All user-generated content rendered to DOM must be HTML-escaped. | TC-S-003, POM-S-001 |
| SEC-003 | Card numbers and CVVs are never written to the database or logs (PCI-DSS). | TC-S-004, TC-S-005, POM-S-004 |
| SEC-004 | All state-changing endpoints require a valid CSRF token; missing/invalid token returns 403. | TC-S-007 |
| SEC-005 | HTTPS enforced in production; HTTP requests redirect to HTTPS (301). | TC-S-006 (deferred) |
| SEC-006 | One user cannot access another user's orders. Returns 403 or 404. | TC-S-008 (deferred) |
| SEC-007 | Rate limiting on login endpoint (429 + `Retry-After`). Brute-force protection on payment endpoint. | RATE-001–003, TC-S-009 (deferred) |
| SEC-008 | Server-side price calculation; client-submitted prices are ignored. | TC-S-010 |
| SEC-009 | JWT tokens must have a configurable TTL; logout invalidates tokens server-side. | AUTH-007 |
| SEC-010 | Error responses in production must not expose stack traces. | ERR-005 |

---

## 10. Out of Scope (MVP)

The following features are architecturally accounted for but deferred to post-MVP:

| Feature | Deferred Test Cases | Reason |
|---|---|---|
| Concurrent inventory management (race condition handling) | TC-E-005 | Requires distributed locking / inventory service |
| Session timeout & cart preservation | TC-E-006 | Requires session management infrastructure |
| Performance under large cart (50+ items) | TC-E-007 | Requires load-testing environment |
| International shipping & currency conversion | TC-E-009 | Requires currency/tax service integration |
| HTTPS enforcement in dev | TC-S-006 | Local dev uses HTTP; CI uses HTTPS |
| Cross-user order access restriction (full audit) | TC-S-008 | Needs audit logging layer |
| Payment endpoint brute-force throttling | TC-S-009 | Requires WAF / advanced rate-limiter |

---

## 11. Open Questions

| # | Question | Owner | Due |
|---|---|---|---|
| OQ-1 | Which payment gateway will be used in production — Stripe or PayPal (or both)? This affects how `paymentToken` is generated. | Product / Engineering | Sprint 1 |
| OQ-2 | Should guest cart items be merged with the user's cart upon login? | Product | Sprint 1 |
| OQ-3 | What is the JWT TTL? Should refresh tokens be supported? | Security / Engineering | Sprint 1 |
| OQ-4 | Will the Kanban and Social Feed features share the same user identity system as the e-commerce checkout? | Architecture | Sprint 2 |
| OQ-5 | Should the `POST /auth/register` endpoint auto-login the user (return a JWT), or redirect to a separate login step? | Product | Sprint 1 |
| OQ-6 | What database technology is preferred (PostgreSQL, MySQL, MongoDB)? This affects migration scripts. | Engineering | Sprint 1 |
| OQ-7 | What email service provider will handle transactional emails (SendGrid, SES, Mailgun)? | DevOps | Sprint 2 |
| OQ-8 | Are the Dashboard and Analytics pages backed by real-time data or pre-aggregated snapshots? | Product / Engineering | Sprint 2 |
