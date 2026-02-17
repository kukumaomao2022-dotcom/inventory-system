import hashlib
import secrets
import uuid
from datetime import datetime, timezone


def normalize_sku(sku: str | None) -> str:
    """Convert SKU to lowercase for internal storage."""
    if not sku:
        return ""
    return sku.lower().strip()


def generate_token() -> str:
    """Generate a unique token for idempotency."""
    return secrets.token_hex(32)


def generate_file_token(content: str) -> str:
    """Generate a token from file content for duplicate detection."""
    return hashlib.md5(content.encode()).hexdigest()


def utcnow() -> datetime:
    """Get current UTC time with timezone."""
    return datetime.now(timezone.utc)


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


def parse_rakuten_datetime(date_str: str | None) -> datetime | None:
    """Parse Rakuten datetime format to Python datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def format_datetime(dt: datetime | None) -> str | None:
    """Format datetime to ISO string."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
