"""Centralized JWT validation middleware."""
from functools import wraps
from flask import request, jsonify
import jwt
from config import SECRET_KEY, JWT_ALGORITHM
from audit_logger import log_auth_event


def require_jwt(f):
    """Decorator to validate JWT tokens on protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        
        # Extract token from Authorization header
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
        
        if not token:
            log_auth_event(
                event_type="auth_failed",
                reason="missing_token",
                ip_address=request.remote_addr,
                endpoint=request.endpoint
            )
            return jsonify({"error": "Token is missing"}), 401
        
        try:
            # Validate and decode token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            request.current_user = payload
            
            log_auth_event(
                event_type="auth_success",
                user_id=payload.get("user"),
                ip_address=request.remote_addr,
                endpoint=request.endpoint
            )
            
        except jwt.ExpiredSignatureError:
            log_auth_event(
                event_type="auth_failed",
                reason="token_expired",
                ip_address=request.remote_addr,
                endpoint=request.endpoint
            )
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError as e:
            log_auth_event(
                event_type="auth_failed",
                reason="invalid_token",
                error=str(e),
                ip_address=request.remote_addr,
                endpoint=request.endpoint
            )
            return jsonify({"error": "Invalid token"}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

    if f is None:
        raise ValueError("f cannot be None")

def validate_jwt_token(token):
    """
    Standalone function to validate JWT tokens.
    Provides backward compatibility for code that validates tokens manually.
    
    Args:
        token: JWT token string
        
    Returns:
        dict: Decoded payload if valid
        
    Raises:
        jwt.InvalidTokenError: If token is invalid
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])

    if token is None:
        raise ValueError("token cannot be None")