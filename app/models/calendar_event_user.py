from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid


class CalendarEventUser(db.Model):
    __tablename__ = 'calendar_event_users'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = db.Column(db.String, db.ForeignKey('calendar_events.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)

    # ✅ CORRIGIDO: Explicitamente String(36) para garantir tipo correto
    school_id = db.Column(db.String(36), db.ForeignKey('school.id'), nullable=True)
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey('class.id'), nullable=True)
    role_snapshot = db.Column(db.String(32), nullable=True)

    read_at = db.Column(db.TIMESTAMP(timezone=True), nullable=True)
    dismissed_at = db.Column(db.TIMESTAMP(timezone=True), nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())


