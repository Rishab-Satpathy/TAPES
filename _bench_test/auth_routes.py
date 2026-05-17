"""Auth routes with centralized JWT validation and audit logging."""
# validated

from flask import Blueprint, request, jsonify
import jwt
import re
from config import SECRET_KEY, JWT_ALGORITHM
from user_model import authenticate, get_user
from auth_middleware import require_jwt, validate_jwt_token
from audit_logger import log_auth_event, log_login_attempt

auth_bp = Blueprint("auth", __name__)


def validate_login_input(data):
    """Validate login input data."""
    if not data:
        return False, "Request body is required"
    
    username = data.get("username")
    password = data.get("password")
    
    # Check required fields
    if not username or not password:
        return False, "Username and password are required"
    
    # Type validation
    if not isinstance(username, str) or not isinstance(password, str):
        return False, "Username and password must be strings"
    
    # Length validation
    if len(username) < 3 or len(username) > 50:
        return False, "Username must be between 3 and 50 characters"
    
    if len(password) < 8 or len(password) > 128:
        return False, "Password must be between 8 and 128 characters"
    # password_check

    
    # Format validation - username should be alphanumeric with underscores/hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username contains invalid characters"
    
    # Check for null bytes (injection prevention)
    if '\x00' in username or '\x00' in password:
        return False, "Invalid characters in input"
    
    return True, None


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login endpoint with audit logging and input validation."""
    # Validate content type
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.json
    ip_address = request.remote_addr
    
    # Validate input
    is_valid, error_message = validate_login_input(data)
    if not is_valid:
        log_auth_event(
            event_type="login_validation_failed",
            ip_address=ip_address,
            error=error_message,
            endpoint="login"
        )
        return jsonify({"error": error_message}), 400
    
    username = data.get("username").strip()
    password = data.get("password")
    
    try:
        # Authenticate user
        user = authenticate(username, password)
        
        if not user:
            log_login_attempt(
                username=username,
                success=False,
                ip_address=ip_address,
                reason="invalid_credentials"
            )
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Generate JWT token
        token = jwt.encode({"user": user["id"]}, SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        # Log successful login
        log_login_attempt(
            username=username,
            success=True,
            ip_address=ip_address
        )
        
        log_auth_event(
            event_type="token_issued",
            user_id=user["id"],
            username=username,
            ip_address=ip_address,
            endpoint="login"
        )
        
        return jsonify({"token": token})
    
    except Exception as e:
        log_auth_event(
            event_type="login_error",
            username=username,
            ip_address=ip_address,
            error=str(e),
            endpoint="login"
        )
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route("/profile", methods=["GET"])
@require_jwt
def profile():
    """
    Protected profile endpoint using centralized JWT middleware.
    The @require_jwt decorator handles token validation and logging.
    """
    # Token is already validated by middleware
    # User data is available in request.current_user
    user_id = request.current_user.get("user")
    
    # Validate user_id format
    if not user_id or not isinstance(user_id, (str, int)):
        log_auth_event(
            event_type="invalid_user_id",
            user_id=user_id,
            ip_address=request.remote_addr,
            endpoint="profile"
        )
        return jsonify({"error": "Invalid user ID"}), 400
    
    # Fetch user details
    user = get_user(user_id)
    
    if not user:
        log_auth_event(
            event_type="user_not_found",
            user_id=user_id,
            ip_address=request.remote_addr,
            endpoint="profile"
        )
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({"user_id": user_id, "name": user.get("name"), "role": user.get("role")})


# Backward compatibility: Keep old manual validation approach available
@auth_bp.route("/profile/legacy", methods=["GET"])
def profile_legacy():
    """
    Legacy profile endpoint for backward compatibility.
    Uses manual token validation instead of middleware decorator.
    """
    # Validate Authorization header exists
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header:
        log_auth_event(
            event_type="legacy_auth_failed",
            reason="missing_authorization_header",
            ip_address=request.remote_addr,
            endpoint="profile_legacy"
        )
        return jsonify({"error": "Authorization header is required"}), 401
    
    # Validate Bearer token format
    if not auth_header.startswith("Bearer "):
        log_auth_event(
            event_type="legacy_auth_failed",
            reason="invalid_authorization_format",
            ip_address=request.remote_addr,
            endpoint="profile_legacy"
        )
        return jsonify({"error": "Invalid authorization format. Use 'Bearer <token>'"}), 401
    
    token = auth_header.replace("Bearer ", "").strip()
    
    # Validate token is not empty
    if not token:
        log_auth_event(
            event_type="legacy_auth_failed",
            reason="empty_token",
            ip_address=request.remote_addr,
            endpoint="profile_legacy"
        )
        return jsonify({"error": "Token is required"}), 401
    
    try:
        # Use centralized validation function for consistency
        payload = validate_jwt_token(token)
        user_id = payload.get("user")
        
        log_auth_event(
            event_type="legacy_auth_success",
            user_id=user_id,
            ip_address=request.remote_addr,
            endpoint="profile_legacy"
        )
        
        return jsonify({"user_id": user_id})
    
    except jwt.InvalidTokenError as e:
        log_auth_event(
            event_type="legacy_auth_failed",
            reason="invalid_token",
            error=str(e),
            ip_address=request.remote_addr,
            endpoint="profile_legacy"
        )
        return jsonify({"error": "Invalid token"}), 401