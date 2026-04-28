# E-Commerce API

A production-quality **Flask REST API** implementing FR 5.1–5.6 of the
[E-Commerce Application PRD](../prd/PRD_ECommerce_Application.md).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Flask 3.0 |
| ORM | SQLAlchemy 2 + Flask-SQLAlchemy |
| Auth | Flask-JWT-Extended (JWT Bearer tokens) |
| Caching | Redis (via `redis-py`; graceful fallback) |
| Rate Limiting | Flask-Limiter (Redis backend) |
| Validation | Marshmallow 3 |
| Sanitisation | bleach |
| Docs | Flasgger (Swagger UI) |
| Tests | pytest + pytest-flask + fakeredis |

---

## Quick Start

### 1 – Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.11 |
| Redis | 7.x (optional – app degrades gracefully) |

### 2 – Install dependencies

```bash
cd ecommerce_api
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3 – Configure environment

```bash
cp .env.example .env
# Edit .env – at minimum set SECRET_KEY and JWT_SECRET_KEY
```

### 4 – Seed the database

```bash
python seed.py
```

This creates:
- `admin@example.com` / `Admin1234!` (role: admin)
- `user@example.com` / `User1234!` (role: user)
- 6 sample products across 4 categories
- 5 discount codes (SAVE10, FLAT5, NEWUSER, TWENTY_OFF, SUMMER21-expired)

### 5 – Run the server

```bash
python run.py
# Server starts on http://localhost:3000
```

### 6 – Browse Swagger UI

Open **<http://localhost:3000/apidocs/>** in your browser.

---

## Running Tests

```bash
# All tests with coverage report
pytest --cov=app --cov-report=term-missing -v

# Single module
pytest tests/test_checkout.py -v
```

Tests run against an **in-memory SQLite** database and a **fakeredis** instance,
so no external services are required.

---

## API Endpoints (FR 5.1–5.6)

All routes are prefixed with `/api/v1`.

### Authentication (`/auth`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | Public | Register; returns JWT + csrfToken |
| POST | `/auth/login` | Public | Login; returns JWT + csrfToken |
| POST | `/auth/logout` | User | Blacklist current JWT |
| POST | `/auth/refresh` | User | Issue a fresh token |

### Users (`/users`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/users` | Admin | Paginated user list |
| POST | `/users` | Admin | Create user |
| GET | `/users/me` | User | Own profile |
| PUT | `/users/me` | User | Update name / addresses |
| GET | `/users/me/settings` | User | Notification settings |
| PUT | `/users/me/settings` | User | Update settings |
| GET | `/users/:id` | Admin | Any user |
| PUT | `/users/:id` | Admin | Update any user |
| DELETE | `/users/:id` | Admin | Deactivate user |
| GET | `/users/:id/orders` | Admin | All orders for user |

### Products (`/products`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/products` | Public | Search / filter / sort / paginate |
| GET | `/products/:id` | Public | Single product |
| POST | `/products` | Admin | Create product |
| PUT | `/products/:id` | Admin | Update product (partial) |
| DELETE | `/products/:id` | Admin | Soft-delete |

**Query parameters for `GET /products`:**

| Param | Type | Example |
|---|---|---|
| `page` | int | `1` |
| `limit` | int | `10` |
| `search` | string | `headphones` |
| `category` | string | `Electronics` |
| `minPrice` | float | `50` |
| `maxPrice` | float | `200` |
| `sortBy` | string | `price`, `name`, `rating`, `createdAt` |
| `sortOrder` | string | `asc` / `desc` |

### Cart (`/cart`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/cart` | User | Current cart with totals |
| POST | `/cart/items` | User | Add item |
| PUT | `/cart/items/:id` | User | Update quantity (0 = remove) |
| DELETE | `/cart/items/:id` | User | Remove item |
| POST | `/cart/discount` | User | Apply discount code |
| DELETE | `/cart/discount` | User | Remove discount |

### Checkout (`/checkout`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/checkout` | User + CSRF | Place order from cart |
| POST | `/checkout/submit` | User + CSRF | Alias (same handler) |

**Request body:**
```json
{
  "shippingAddress": {
    "firstName": "John", "lastName": "Doe",
    "email": "john@example.com",
    "street": "123 Main St", "city": "Austin",
    "state": "TX", "zip": "78701", "country": "US"
  },
  "paymentToken": "tok_visa",
  "discountCode": "SAVE10",
  "idempotencyKey": "unique-request-id-123"
}
```

**Payment tokens (simulation):**

| Token | Outcome |
|---|---|
| `tok_visa` | ✅ Success (Visa ···4242) |
| `tok_mastercard` | ✅ Success (Mastercard ···4444) |
| `tok_paypal` | ✅ Success (PayPal) |
| `tok_declined` | ❌ Card declined |
| `tok_insufficient_funds` | ❌ Insufficient funds |
| `tok_expired_card` | ❌ Expired card |
| `tok_wrong_cvv` | ❌ Wrong CVV |
| `tok_lost_card` | ❌ Lost/stolen card |

### Orders (`/orders`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/orders` | User | Own order history (paginated) |
| GET | `/orders/:id` | User | Single order (own only) |
| PUT | `/orders/:id` | Admin | Update status |
| DELETE | `/orders/:id` | Admin | Cancel order |

---

## Security Features

| Feature | Implementation |
|---|---|
| **JWT blacklist** | On logout, `jti` is stored in Redis with remaining TTL |
| **CSRF protection** | `X-CSRF-Token` header required on `POST /checkout` |
| **Rate limiting** | Login: 10 req/min per IP · General API: 100 req/min |
| **Input sanitisation** | All user strings run through `bleach.clean()` |
| **SQL injection** | SQLAlchemy ORM parameterised queries – no raw SQL |
| **Price integrity** | Server always recalculates totals; ignores client-submitted prices |
| **PCI-DSS** | Raw card numbers / CVV never stored; only payment gateway tokens + last4 |
| **Soft deletes** | Products are flagged `is_deleted`; order history line items snapshot prices |
| **Idempotency** | Checkout idempotency key stored 24 h in Redis to prevent duplicate charges |

---

## Redis Caching

| Key pattern | TTL | Content |
|---|---|---|
| `products:{md5-of-query}` | 5 min | Paginated product list |
| `product:{id}` | 5 min | Single product dict |
| `blacklist:{jti}` | Remaining token TTL | Revoked JWT marker |
| `csrf:{user_id}` | 24 h | CSRF token |
| `idempotency:{key}` | 24 h | Checkout response snapshot |

If Redis is unavailable the API continues to function (caching is skipped, CSRF
validation is bypassed in non-production environments).

---

## Test Suite

```
tests/
├── conftest.py        # App factory, fixtures, fakeredis patch, seeded data
├── test_auth.py       # 11 cases – registration, login, logout, token validation
├── test_products.py   # 11 cases – list, search, filter, sort, admin CRUD
├── test_cart.py       # 14 cases – add, update, remove, discounts, security
├── test_checkout.py   # 14 cases – success, payment failures, CSRF, idempotency, PCI
└── test_orders.py     # 11 cases – list, get, cross-user access, admin management
```

**Total: 61 test cases** (well above the 20+ requirement).

---

## Project Structure

```
ecommerce_api/
├── app/
│   ├── __init__.py          # App factory + blueprint registration
│   ├── config.py            # Dev / Testing / Production configs
│   ├── extensions.py        # SQLAlchemy, JWT, Limiter, Redis init
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── product.py
│   │   ├── cart.py
│   │   ├── order.py
│   │   └── discount.py
│   ├── blueprints/          # Route handlers
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── products.py
│   │   ├── cart.py
│   │   ├── checkout.py
│   │   └── orders.py
│   ├── services/
│   │   ├── payment.py       # Payment gateway simulation
│   │   └── cache.py         # Redis cache helpers
│   └── utils/
│       ├── errors.py        # Global error handlers
│       ├── validators.py    # Marshmallow schemas
│       └── security.py      # CSRF, sanitisation, admin decorator
├── tests/                   # pytest test suite
├── seed.py                  # Development data seeder
├── run.py                   # Application entry point
├── requirements.txt
└── .env.example
```
