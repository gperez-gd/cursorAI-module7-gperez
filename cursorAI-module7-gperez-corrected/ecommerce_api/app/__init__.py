import os
import time

from dotenv import load_dotenv
from flasgger import Swagger
from flask import Flask, g, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt

from .config import config_map
from .extensions import celery, db, jwt, limiter, init_redis, get_redis

load_dotenv()

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
    "specs_route": "/apidocs/",
    "title": "E-Commerce API",
    "version": "1.0.0",
    "description": "Full-stack e-commerce REST API – FR 5.1–5.6",
    "securityDefinitions": {
        "BearerAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "JWT Bearer token. Format: **Bearer &lt;token&gt;**",
        }
    },
}


def create_app(env: str | None = None) -> Flask:
    app = Flask(__name__)

    env = env or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_map.get(env, config_map["default"]))

    # Extensions
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)
    Swagger(app, config=SWAGGER_CONFIG, merge=True)

    # Celery – use REDIS_URL as broker/backend when available, else in-memory
    broker = app.config.get("REDIS_URL", "memory://")
    celery.config_from_object(
        {
            "broker_url": broker,
            "result_backend": broker,
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
        }
    )
    celery.conf.update(app.config)

    # Redis (optional)
    init_redis(app)

    # ── Health check ──────────────────────────────────────────────────
    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "env": env}), 200

    # ── Request / response logging ────────────────────────────────────
    @app.before_request
    def _log_request():
        g.t0 = time.monotonic()
        app.logger.info("→ %s %s", request.method, request.path)

    @app.after_request
    def _log_response(response):
        t0 = getattr(g, 't0', None)
        if t0 is not None:
            ms = (time.monotonic() - t0) * 1000
            app.logger.info("← %s %s  [%.1f ms]", response.status_code, request.path, ms)
        return response

    # JWT token blacklist check
    @jwt.token_in_blocklist_loader
    def check_token_blacklist(jwt_header, jwt_payload):
        r = get_redis()
        if r is None:
            return False
        jti = jwt_payload.get("jti")
        return r.get(f"blacklist:{jti}") is not None

    @jwt.revoked_token_loader
    def revoked_token_response(jwt_header, jwt_payload):
        return jsonify({"error": "Token has been revoked."}), 401

    @jwt.expired_token_loader
    def expired_token_response(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired."}), 401

    @jwt.invalid_token_loader
    def invalid_token_response(reason):
        return jsonify({"error": "Invalid token."}), 401

    @jwt.unauthorized_loader
    def missing_token_response(reason):
        return jsonify({"error": "Authentication required."}), 401

    # Register blueprints under /api/v1
    from .blueprints.auth import auth_bp
    from .blueprints.users import users_bp
    from .blueprints.products import products_bp
    from .blueprints.cart import cart_bp
    from .blueprints.checkout import checkout_bp
    from .blueprints.orders import orders_bp

    PREFIX = "/api/v1"
    app.register_blueprint(auth_bp, url_prefix=f"{PREFIX}/auth")
    app.register_blueprint(users_bp, url_prefix=f"{PREFIX}/users")
    app.register_blueprint(products_bp, url_prefix=f"{PREFIX}/products")
    app.register_blueprint(cart_bp, url_prefix=f"{PREFIX}/cart")
    app.register_blueprint(checkout_bp, url_prefix=f"{PREFIX}/checkout")
    app.register_blueprint(orders_bp, url_prefix=f"{PREFIX}/orders")

    # Global error handlers
    from .utils.errors import register_error_handlers
    register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app
