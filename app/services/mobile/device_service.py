import re
import uuid
from datetime import datetime

from app import db
from app.models.mobile_models import MobileDevice


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


def register_or_touch_device(user_id: str, device_id: str) -> None:
    row = MobileDevice.query.filter_by(device_id=device_id).first()
    now = datetime.utcnow()
    if row:
        if row.user_id != user_id:
            raise PermissionError("device_id vinculado a outro usuário")
        row.last_seen_at = now
    else:
        row = MobileDevice(device_id=device_id, user_id=user_id, last_seen_at=now)
        db.session.add(row)
