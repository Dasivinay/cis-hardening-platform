from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from app.utils.errors import ForbiddenError


def roles_required(*allowed_roles):
    """RBAC decorator — apply after @jwt_required() on any endpoint.

    Raises ForbiddenError (handled centrally by register_error_handlers) rather
    than building a Flask Response directly, since flask-restx Resource methods
    must return plain data/tuples for its own JSON representation layer to
    serialize — returning a Response object here causes a double-serialization
    TypeError.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") not in allowed_roles:
                raise ForbiddenError(f"This action requires one of roles: {allowed_roles}")
            return fn(*args, **kwargs)
        return wrapper
    return decorator
