"""Application configuration constants."""
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
JWT_ALGORITHM = "HS256"
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")
API_VERSION = "v2.1"
MAX_LOGIN_ATTEMPTS = 5
SESSION_TIMEOUT_SECONDS = 3600
