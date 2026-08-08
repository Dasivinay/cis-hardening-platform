"""Centralized application exceptions + error handler registration.

IMPORTANT — flask-restx interaction:
flask-restx's Api registers its own top-level exception router
(Api.error_router) that intercepts every exception raised inside a
flask-restx Resource *before* Flask's normal app.errorhandler_spec lookup
ever runs. It only consults handlers registered via the flask-restx-specific
`api.errorhandler(...)` decorator (populating Api.error_handlers) — plain
`@app.errorhandler(SomeException)` registrations (including the ones
flask_jwt_extended's JWTManager registers internally for things like
NoAuthorizationError/ExpiredSignatureError) are silently bypassed for any
route flask-restx owns, and fall through to a generic 500 response.

This was verified empirically: registering AppError and the JWT exception
families only via `@app.errorhandler` produced a real 500 for every 400/401/
403/404/409 case when hit over real HTTP, despite passing in pytest (Flask's
TESTING config takes a different, non-representative exception-propagation
path that masked this bug in the test suite).

The fix is to register error handling on the flask-restx `Api` instance
itself, via `register_api_error_handlers(api)`, called from app/api/__init__.py
after the Api is constructed. The plain-Flask handlers below are kept as a
fallback for true non-flask-restx routes (currently just /health).
"""
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import PyJWTError


class AppError(Exception):
    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(AppError):
    status_code = 400


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class ExternalServiceError(AppError):
    status_code = 502


def register_api_error_handlers(api):
    """Register handlers on the flask-restx Api — this is the one that
    actually fires for /api/v1/* routes. Must be called after the Api is
    constructed, before any request is served."""

    @api.errorhandler(AppError)
    def handle_app_error(err):
        return {"error": err.__class__.__name__, "message": err.message}, err.status_code

    @api.errorhandler(JWTExtendedException)
    def handle_jwt_extended_error(err):
        # Covers NoAuthorizationError, CSRFError, WrongTokenError,
        # RevokedTokenError, FreshTokenRequired, UserLookupError,
        # UserClaimsVerificationError, InvalidHeaderError, InvalidQueryParamError.
        return {"error": "Unauthorized", "message": str(err)}, 401

    @api.errorhandler(PyJWTError)
    def handle_pyjwt_error(err):
        # Covers ExpiredSignatureError, DecodeError, InvalidTokenError,
        # InvalidAudienceError, InvalidIssuerError, MissingRequiredClaimError —
        # these come from PyJWT itself, not flask_jwt_extended.exceptions.
        return {"error": "Unauthorized", "message": str(err)}, 401


def register_error_handlers(app):
    """Fallback handlers for the small number of plain-Flask routes outside
    the flask-restx Api (currently just /health). Kept separate from
    register_api_error_handlers because the two frameworks route exceptions
    through entirely different mechanisms."""
    from flask import jsonify

    @app.errorhandler(404)
    def handle_404(err):
        return jsonify({"error": "NotFound", "message": "The requested resource was not found."}), 404

    @app.errorhandler(500)
    def handle_500(err):
        app.logger.exception("Unhandled server error")
        return jsonify({"error": "InternalServerError", "message": "An unexpected error occurred."}), 500
