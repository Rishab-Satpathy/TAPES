"""Modern authentication module with bcrypt and JWT tokens."""
import bcrypt
import jwt
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional, Dict, Any
from config import SECRET_KEY, JWT_ALGORITHM, SESSION_TIMEOUT_SECONDS


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password as a string
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.
    
    Args:
        password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def generate_jwt_token(username: str, user_id: int, role: str) -> str:
    """Generate a JWT token for authenticated user.
    
    Args:
        username: Username of the authenticated user
        user_id: User ID
        role: User role (admin, user, etc.)
        
    Returns:
        JWT token as a string
    """
    payload = {
        'sub': username,
        'user_id': user_id,
        'role': role,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(seconds=SESSION_TIMEOUT_SECONDS)
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def validate_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate and decode a JWT token.
    
    Args:
        token: JWT token to validate
        
    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        # Token has expired
        return None
    except jwt.InvalidTokenError:
        # Token is invalid
        return None


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user with bcrypt password verification and JWT token generation.
    
    Args:
        username: Username to authenticate
        password: Plain text password
        
    Returns:
        Dictionary with user info and JWT token if successful, None otherwise
    """
    users = get_users_db()
    
    if username not in users:
        return None
    
    # Verify password using bcrypt
    if not verify_password(password, users[username]['password_hash']):
        return None
    
    # Determine user role
    role = "admin" if username == "admin" else "user"
    user_id = users[username]['user_id']
    
    # Generate JWT token
    token = generate_jwt_token(username, user_id, role)
    
    return {
        "user_id": user_id,
        "name": username,
        "role": role,
        "token": token
    }


def authorize(action: str, user_role: str) -> bool:
    """Check if user role is authorized for an action.
    
    Args:
        action: Action to authorize (read, write, delete)
        user_role: Role of the user
        
    Returns:
        True if authorized, False otherwise
    """
    permissions = {
        "read": ["admin", "user"],
        "write": ["admin"],
        "delete": ["admin"],
    }
    return user_role in permissions.get(action, [])


@lru_cache(maxsize=128)
def get_users_db() -> Dict[str, Dict[str, Any]]:
    """Get cached users database with bcrypt hashed passwords.
    
    Returns:
        Dictionary of users with their hashed passwords and metadata
    """
    # Pre-hashed passwords for demo purposes
    # In production, these would be stored in a database
    # admin123 hashed with bcrypt
    admin_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVr/qviu."
    # user123 hashed with bcrypt
    user_hash = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"
    
    return {
        "admin": {
            "user_id": 1,
            "password_hash": admin_hash,
        },
        "user": {
            "user_id": 2,
            "password_hash": user_hash,
        },
    }


def refresh_token(old_token: str) -> Optional[str]:
    """Refresh an existing JWT token.
    
    Args:
        old_token: Existing JWT token to refresh
        
    Returns:
        New JWT token if old token is valid, None otherwise
    """
    payload = validate_jwt_token(old_token)
    
    if payload is None:
        return None
    
    # Generate new token with same user info
    new_token = generate_jwt_token(
        payload['sub'],
        payload['user_id'],
        payload['role']
    )
    
    return new_token


def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Extract user information from a JWT token.
    
    Args:
        token: JWT token
        
    Returns:
        User information if token is valid, None otherwise
    """
    payload = validate_jwt_token(token)
    
    if payload is None:
        return None
    
    return {
        "user_id": payload['user_id'],
        "name": payload['sub'],
        "role": payload['role']
    }