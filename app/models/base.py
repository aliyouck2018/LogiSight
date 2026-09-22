"""Model utilities."""
import uuid


def generate_public_id(prefix: str) -> str:
    """Generate a public entity id like SHP-000123."""
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"
