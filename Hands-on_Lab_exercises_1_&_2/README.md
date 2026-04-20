# Blog Platform API

A REST API for a blogging platform built with Flask, SQLAlchemy, Marshmallow, JWT authentication, and Swagger UI documentation.

## Stack

| Layer | Library |
|---|---|
| Framework | Flask 3 (Application Factory pattern) |
| ORM | Flask-SQLAlchemy (SQLite dev / PostgreSQL prod) |
| Serialization & Validation | Flask-Marshmallow + marshmallow-sqlalchemy |
| Authentication | Flask-JWT-Extended (JWT access tokens) |
| Password Hashing | Flask-Bcrypt |
| API Documentation | Flasgger (Swagger UI) |

## Project Structure

```
├── app/
│   ├── __init__.py         # Application factory
│   ├── models/
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── post.py
│   │   └── comment.py
│   ├── schemas/
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── post.py
│   │   └── comment.py
│   └── routes/
│       ├── auth.py
│       ├── posts.py
│       ├── comments.py
│       ├── categories.py
│       └── search.py
├── config.py
├── run.py
├── requirements.txt
└── .env.example
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then edit SECRET_KEY and JWT_SECRET_KEY
python run.py
```

The server starts at `http://localhost:5000`.  
Swagger UI is available at **`http://localhost:5000/api/docs`**.

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Register a new user |
| POST | `/api/auth/login` | No | Login, receive JWT |
| GET | `/api/posts` | No | List posts (paginated, 20/page) |
| POST | `/api/posts` | Yes | Create a post |
| GET | `/api/posts/<id>` | No | Get a single post |
| PUT/PATCH | `/api/posts/<id>` | Yes (author) | Update a post |
| DELETE | `/api/posts/<id>` | Yes (author) | Delete a post |
| GET | `/api/posts/<id>/comments` | No | List comments (10/page) |
| POST | `/api/posts/<id>/comments` | Yes | Add a comment |
| DELETE | `/api/comments/<id>` | Yes (author) | Delete a comment |
| GET | `/api/categories` | No | List all categories |
| GET | `/api/search?q=keyword` | No | Search posts by keyword |

## Authentication

Include the JWT token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

## Error Responses

All errors return structured JSON:

```json
{ "error": "<message>", "details": "<detail or field errors>" }
```

| Status | Meaning |
|---|---|
| 400 | Validation failure (field-level Marshmallow errors in `details`) |
| 401 | Missing or invalid JWT |
| 403 | Authenticated but not the resource owner |
| 404 | Resource not found |
| 409 | Duplicate username or email |
| 500 | Unexpected server error |
