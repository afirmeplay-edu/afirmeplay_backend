import re
import uuid


_UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def is_valid_uuid_v4(value: str) -> bool:
    if not value or len(value) > 64:
        return False
    try:
        u = uuid.UUID(value)
        return u.version == 4
    except (ValueError, AttributeError):
        return _UUID_V4_RE.match(str(value)) is not None
