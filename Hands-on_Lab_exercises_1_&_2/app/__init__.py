import logging
import traceback

from flask import Flask, jsonify
from flask_bcrypt import Bcrypt
from flask_caching import Cache
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger

from config import config_map

db = SQLAlchemy()
ma = Marshmallow()
bcrypt = Bcrypt()
jwt = JWTManager()
cache = Cache()

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "Blog Platform API",
        "description": "A REST API for a blogging platform with JWT authentication.",
        "version": "1.0.0",
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Authorization header. Example: 'Bearer {token}'",
        }
    },
    "basePath": "/",
}

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs",
}


def create_app(env: str = "default") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_map[env])

    db.init_app(app)
    ma.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    Swagger(app, template=SWAGGER_TEMPLATE, config=SWAGGER_CONFIG)

    _init_cache(app)

    from app.routes.auth import auth_bp
    from app.routes.posts import posts_bp
    from app.routes.comments import comments_bp, register_post_comments
    from app.routes.categories import categories_bp
    from app.routes.search import search_bp

    # Register post-scoped comment routes directly on the posts blueprint
    register_post_comments(posts_bp)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(posts_bp, url_prefix="/api/posts")
    app.register_blueprint(comments_bp, url_prefix="/api/comments")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    app.register_blueprint(search_bp, url_prefix="/api/search")

    _register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app


def _init_cache(app: Flask) -> None:
    """Initialise Flask-Caching; fall back to SimpleCache when Redis is unavailable."""
    try:
        cache.init_app(app)
        # Probe the connection only when a real Redis backend is configured.
        if app.config.get("CACHE_TYPE") == "RedisCache":
            with app.app_context():
                cache.get("__probe__")
    except Exception:
        logging.warning(
            "Redis unavailable — falling back to SimpleCache (no caching between requests).",
            exc_info=True,
        )
        app.config["CACHE_TYPE"] = "SimpleCache"
        cache.init_app(app)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "details": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized", "details": str(e)}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden", "details": str(e)}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found", "details": str(e)}), 404

    @app.errorhandler(409)
    def conflict(e):
        return jsonify({"error": "Conflict", "details": str(e)}), 409

    @app.errorhandler(500)
    def internal_error(e):
        logging.error("Unhandled exception:\n%s", traceback.format_exc())
        return jsonify({"error": "Internal server error", "details": "An unexpected error occurred."}), 500
