import redis
from flask import Flask, jsonify
from .extensions import db, migrate, jwt, bcrypt, cache, limiter, swagger, celery
from config import config


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    swagger.init_app(app)

    # Configure Celery
    _configure_celery(app)

    # JWT token blocklist check
    _configure_jwt(app)

    # Register blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.tickets import tickets_bp
    from .blueprints.users import users_bp
    from .blueprints.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tickets_bp, url_prefix="/api/tickets")
    app.register_blueprint(users_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    # Register error handlers
    _register_error_handlers(app)

    return app


def _configure_celery(app):
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        beat_schedule=app.config.get("CELERY_BEAT_SCHEDULE", {}),
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            from flask import has_app_context
            if has_app_context():
                # Reuse existing context (e.g. during tests or when called from a view)
                return self.run(*args, **kwargs)
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask


def _configure_jwt(app):
    blocklist_client = None

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        nonlocal blocklist_client
        if app.config.get("TESTING"):
            return False
        try:
            if blocklist_client is None:
                blocklist_client = redis.from_url(app.config["REDIS_URL"])
            jti = jwt_payload["jti"]
            return blocklist_client.get(f"blocklist:{jti}") is not None
        except Exception:
            return False

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "status": "error",
            "message": "Token has expired",
            "code": "UNAUTHORIZED",
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            "status": "error",
            "message": "Invalid token",
            "code": "UNAUTHORIZED",
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            "status": "error",
            "message": "Authentication required",
            "code": "UNAUTHORIZED",
        }), 401


def _register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"status": "error", "message": str(e), "code": "BAD_REQUEST"}), 400

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"status": "error", "message": "Forbidden", "code": "FORBIDDEN"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"status": "error", "message": "Resource not found", "code": "NOT_FOUND"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"status": "error", "message": "Method not allowed", "code": "METHOD_NOT_ALLOWED"}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({"status": "error", "message": "Rate limit exceeded", "code": "RATE_LIMIT_EXCEEDED"}), 429

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"status": "error", "message": "Internal server error", "code": "INTERNAL_ERROR"}), 500
