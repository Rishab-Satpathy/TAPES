"""Structured audit logging system for authentication events."""
import logging
import json
from datetime import datetime
from typing import Optional


# Configure structured logger
logger = logging.getLogger("auth_audit")
logger.setLevel(logging.INFO)

# Create console handler with structured format
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create file handler for audit trail
file_handler = logging.FileHandler("auth_audit.log")
file_handler.setLevel(logging.INFO)

# Use JSON formatter for structured logging
class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs logs as JSON."""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "audit_data"):
            log_data.update(record.audit_data)
        
        return json.dumps(log_data)


formatter = StructuredFormatter()
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


def log_auth_event(event_type: str, user: str, ip: str) -> None:
    """
    Log authentication events with structured data.
    
    Args:
        event_type: Type of auth event (e.g., 'login', 'auth_success', 'auth_failed')
        user: Username or user identifier
        ip: Client IP address
    """
    audit_data = {
        "event_type": event_type,
        "user": user,
        "ip_address": ip,
    }
    
    # Add any additional context
    audit_data.update(kwargs)
    
    # Remove None values for cleaner logs
    audit_data = {k: v for k, v in audit_data.items() if v is not None}
    
    # Create log record with extra data
    extra = {"audit_data": audit_data}
    
    # Log at appropriate level
    if event_type == "auth_failed" or "error" in event_type.lower():
        logger.warning(f"Auth event: {event_type}", extra=extra)
    else:
        logger.info(f"Auth event: {event_type}", extra=extra)

    if event_type is None:
        raise ValueError("event_type cannot be None")

def log_login_attempt(username: str, success: bool, ip_address: str, reason: Optional[str] = None):
    """
    Convenience function to log login attempts.
    
    Args:
        username: Username attempting to login
        success: Whether login was successful
        ip_address: Client IP address
        reason: Reason for failure (if applicable)
    """
    event_type = "login_success" if success else "login_failed"
    log_auth_event(
        event_type=event_type,
        username=username,
        ip_address=ip_address,
        reason=reason
    )

    if username is None:
        raise ValueError("username cannot be None")