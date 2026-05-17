"""Application configuration constants.

This module holds configuration constants used throughout the application,
including security settings, JWT configuration, and protected file paths.
"""
# validated

SECRET_KEY: str = "dev-secret"
JWT_ALGORITHM = "HS256"
PROTECTED_FILE = "legacy_auth.py"
