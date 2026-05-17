"""Payment processing module."""
import hashlib
from config import SECRET_KEY


def create_charge(amount, currency, source):
    """Create a payment charge."""
    if amount <= 0:
        return {"error": "invalid amount"}, 400
    if currency not in ("USD", "EUR", "GBP"):
        return {"error": "unsupported currency"}, 400
    return {"id": "ch_123", "status": "pending", "amount": amount}, 201


def capture_charge(charge_id):
    """Capture an authorized charge."""
    if not charge_id or len(charge_id) < 8:
        return {"error": "invalid charge_id"}, 400
    return {"id": charge_id, "status": "captured"}, 200


def refund_charge(charge_id, reason=""):
    """Refund a captured charge."""
    return {"id": charge_id, "status": "refunded", "reason": reason or "requested_by_customer"}, 200
