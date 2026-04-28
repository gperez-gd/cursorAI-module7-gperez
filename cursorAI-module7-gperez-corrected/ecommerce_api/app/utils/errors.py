from flask import jsonify


def err(message: str, code: int = 400, error_code: str | None = None) -> tuple:
    body = {"error": message}
    if error_code:
        body["code"] = error_code
    return jsonify(body), code


def register_error_handlers(app) -> None:
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": str(e.description) if e.description else "Bad request."}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Authentication required."}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Access denied."}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(409)
    def conflict(e):
        return jsonify({"error": str(e.description) if e.description else "Conflict."}), 409

    @app.errorhandler(429)
    def too_many_requests(e):
        return (
            jsonify({"error": "Too many requests. Please slow down."}),
            429,
        )

    @app.errorhandler(500)
    def internal_error(e):
        # Never expose stack traces (SEC-010)
        return jsonify({"error": "An internal server error occurred."}), 500
