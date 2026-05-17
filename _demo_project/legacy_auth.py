"""Legacy authentication module — protected by TAPES Bouncer."""
import hashlib
import time
from functools import lru_cache
from config import SECRET_KEY


def authenticate(username, password):
    """Authenticate user with password hashing."""
    users = get_users_db()
    if username not in users:
        return None
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if pw_hash != users[username]:
        return None
    token = generate_session_token(username)
    return {"user_id": 1, "name": username, "role": "admin" if username == "admin" else "user", "token": token}


def authorize(action, user_role):
    """Check if user role is authorized."""
    permissions = {
        "read": ["admin", "user"],
        "write": ["admin"],
        "delete": ["admin"],
    }
    return user_role in permissions.get(action, [])


@lru_cache(maxsize=128)
def get_users_db():
    """Get cached users database."""
    return {
        "admin": hashlib.sha256("admin123".encode()).hexdigest(),
        "user": hashlib.sha256("user123".encode()).hexdigest(),
    }


def generate_session_token(username):
    """Generate a session token."""
    raw = f"{username}:{int(time.time())}:{SECRET_KEY}"
    return hashlib.sha256(raw.encode()).hexdigest()
