# Customer Support Ticket System

A full-featured REST API built with Flask for managing customer support tickets. Implements JWT authentication, role-based access control, SLA tracking, async email notifications, and Swagger documentation.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Running the API](#running-the-api)
- [Running Tests](#running-tests)
- [API Endpoints](#api-endpoints)
- [Role Permissions](#role-permissions)
- [SLA Configuration](#sla-configuration)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Flask 3.x (Application Factory + Blueprints) |
| Database | SQLAlchemy + SQLite (dev) / PostgreSQL (prod) |
| Migrations | Flask-Migrate (Alembic) |
| Auth | Flask-JWT-Extended (JWT Bearer tokens) |
| Serialization | Marshmallow + Flask-Marshmallow |
| Password Hashing | Flask-Bcrypt (cost factor 12) |
| Caching | Flask-Caching + Redis |
| Rate Limiting | Flask-Limiter |
| Background Tasks | Celery + Redis broker |
| API Docs | Flasgger (Swagger UI / OpenAPI 3.0) |
| Testing | pytest + pytest-flask + pytest-cov |

---

## Project Structure

```
customer_support_system/
├── app/
│   ├── __init__.py           # Application factory (create_app)
│   ├── extensions.py         # Flask extensions
│   ├── blueprints/
│   │   ├── auth.py           # POST /api/auth/*
│   │   ├── tickets.py        # /api/tickets/*
│   │   ├── users.py          # /api/users/* and /api/agents/*
│   │   └── admin.py          # /api/admin/*
│   ├── models/
│   │   ├── user.py           # User model (roles, availability)
│   │   ├── ticket.py         # Ticket model (status FSM, SLA)
│   │   ├── comment.py        # Comment model (public/internal)
│   │   ├── assignment.py     # Assignment history
│   │   └── attachment.py     # File attachments
│   ├── schemas/
│   │   ├── user.py           # UserSchema, UserRegisterSchema
│   │   ├── ticket.py         # TicketCreateSchema, filters
│   │   ├── comment.py        # CommentCreateSchema
│   │   └── assignment.py     # AssignmentCreateSchema
│   ├── tasks/
│   │   └── email_tasks.py    # Celery async tasks (FR-035)
│   └── utils/
│       ├── decorators.py     # RBAC decorators + response helpers
│       └── helpers.py        # Ticket number gen, auto-assign, sanitize
├── tests/
│   ├── conftest.py           # Fixtures (app, db, users, JWT headers)
│   ├── unit/
│   │   ├── test_models.py    # Model unit tests
│   │   └── test_schemas.py   # Schema validation tests
│   ├── integration/
│   │   └── test_tasks.py     # Celery task integration tests
│   └── api/
│       ├── test_auth.py      # Auth endpoint tests
│       ├── test_tickets.py   # Ticket CRUD & RBAC tests
│       └── test_admin.py     # Admin dashboard & reports tests
├── config.py                 # Dev / Test / Production configs
├── run.py                    # Flask entry point
├── celery_worker.py          # Celery worker entry point
├── pytest.ini
└── requirements.txt
```

---

## Quick Start

### 1. Clone and Set Up Virtual Environment

```bash
cd Hands-on_Lab_exercise_3/customer_support_system
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start Redis (required for caching and Celery)

```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or using Homebrew (macOS)
brew install redis && brew services start redis
```

### 3. Configure Environment

```bash
cp .env.example .env   # then edit .env with your values
```

Or export directly:

```bash
export FLASK_ENV=development
export SECRET_KEY=your-secret-key
export JWT_SECRET_KEY=your-jwt-secret
export REDIS_URL=redis://localhost:6379/0
```

### 4. Initialize the Database

```bash
flask db init
flask db migrate -m "Initial schema"
flask db upgrade
```

### 5. Start the API

```bash
python run.py
# API available at http://localhost:5000
# Swagger UI at  http://localhost:5000/apidocs
```

### 6. Start the Celery Worker (optional, for email tasks)

```bash
celery -A celery_worker.celery worker --loglevel=info
```

### 7. Start Celery Beat (SLA periodic checks)

```bash
celery -A celery_worker.celery beat --loglevel=info
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | `development` | `development`, `testing`, or `production` |
| `SECRET_KEY` | dev key | Flask secret key |
| `JWT_SECRET_KEY` | dev key | JWT signing key |
| `DATABASE_URL` | SQLite | PostgreSQL DSN for production |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CELERY_BROKER_URL` | same as `REDIS_URL` | Celery broker |
| `MAIL_SERVER` | `smtp.gmail.com` | SMTP server |
| `MAIL_USERNAME` | — | SMTP username |
| `MAIL_PASSWORD` | — | SMTP password |

---

## Running Tests

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/api/test_tickets.py -v

# Run a specific test class
pytest tests/unit/test_models.py::TestTicketModel -v
```

The test suite includes **30+ test cases** across:

| File | Coverage |
|---|---|
| `tests/unit/test_models.py` | Model methods, SLA logic, status transitions |
| `tests/unit/test_schemas.py` | All Marshmallow validators |
| `tests/api/test_auth.py` | Register, login, logout, /me |
| `tests/api/test_tickets.py` | Full CRUD, RBAC, status, priority, comments |
| `tests/api/test_admin.py` | Dashboard, reports, CSV export |
| `tests/integration/test_tasks.py` | Email notification tasks |

---

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login, returns JWT tokens |
| POST | `/api/auth/logout` | Revoke access token |
| GET | `/api/auth/me` | Get current user profile |
| POST | `/api/auth/refresh` | Refresh access token |

### Tickets

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/tickets` | List tickets (filtered, paginated) |
| POST | `/api/tickets` | Create ticket (FR-001, FR-002) |
| GET | `/api/tickets/:id` | Get ticket details |
| PUT | `/api/tickets/:id` | Update subject/description/category |
| DELETE | `/api/tickets/:id` | Delete ticket (admin only) |
| PUT | `/api/tickets/:id/status` | Update status with FSM validation |
| PUT | `/api/tickets/:id/priority` | Update priority (agents/admins, reason required) |
| POST | `/api/tickets/:id/assign` | Assign ticket (admin only) |
| GET | `/api/tickets/:id/history` | Assignment history |
| POST | `/api/tickets/:id/comments` | Add comment |
| GET | `/api/tickets/:id/comments` | List comments |

### Users & Agents

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/users` | List users (admin only) |
| GET | `/api/users/:id` | Get user profile |
| PUT | `/api/users/:id` | Update profile |
| GET | `/api/agents` | List active agents |
| GET | `/api/agents/:id/tickets` | Agent's assigned tickets |
| PUT | `/api/agents/:id/availability` | Update availability status |

### Admin & Reports

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/admin/dashboard` | Dashboard metrics |
| GET | `/api/admin/reports/tickets` | Ticket volume report |
| GET | `/api/admin/reports/agents` | Agent performance |
| GET | `/api/admin/reports/sla` | SLA compliance by priority |
| POST | `/api/admin/reports/export` | Export CSV report |

---

## Role Permissions

| Feature | Customer | Agent | Admin |
|---|---|---|---|
| Create Ticket | ✅ | ✅ | ✅ |
| View Own Tickets | ✅ | ✅ | ✅ |
| View All Tickets | ❌ | Assigned + Open | ✅ |
| Update Ticket Status | ❌ | ✅ | ✅ |
| Assign Tickets | ❌ | ❌ | ✅ |
| Change Priority | ❌ | ✅ | ✅ |
| Add Internal Comments | ❌ | ✅ | ✅ |
| Delete Tickets | ❌ | ❌ | ✅ |
| View Reports | ❌ | Own stats | ✅ |
| Manage Users | ❌ | ❌ | ✅ |

---

## SLA Configuration

| Priority | First Response | Resolution |
|---|---|---|
| Urgent | 2 hours | 24 hours |
| High | 4 hours | 48 hours |
| Medium | 8 hours | 5 days |
| Low | 24 hours | 10 days |

- SLA deadlines are calculated at ticket creation.
- A Celery Beat task runs every 15 minutes to detect approaching and missed SLAs.
- Automated escalation emails are sent to agents and admins for missed SLAs (FR-022).

---

## Swagger UI

Visit `http://localhost:5000/apidocs` after starting the server to explore and test all endpoints interactively.

All endpoints are documented with:
- Request body schemas
- Response schemas
- HTTP status codes
- Authentication requirements (Bearer JWT)
