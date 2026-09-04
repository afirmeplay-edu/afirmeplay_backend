from app import db
from enum import Enum
import uuid


class CalendarVisibilityScope(Enum):
    SCHOOL_ALL = "SCHOOL_ALL"
    MUNICIPALITY = "MUNICIPALITY"
    SCHOOL = "SCHOOL"
    GRADE = "GRADE"
    CLASS = "CLASS"
    USERS = "USERS"


class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(200), nullable=True)

    start_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    end_at = db.Column(db.TIMESTAMP(timezone=True), nullable=True)
    all_day = db.Column(db.Boolean, nullable=False, default=False)
    timezone = db.Column(db.String(64), nullable=True)

    recurrence_rule = db.Column(db.String(255), nullable=True)

    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now())

    created_by_user_id = db.Column(db.String, db.ForeignKey('public.users.id'), nullable=False)
    created_by_role = db.Column(db.String(32), nullable=False)

    visibility_scope = db.Column(db.Enum(CalendarVisibilityScope), nullable=False)

    municipality_id = db.Column(db.String, db.ForeignKey('public.city.id'), nullable=True)
    # ✅ CORRIGIDO: Explicitamente String(36) para garantir tipo correto
    school_id = db.Column(db.String(36), db.ForeignKey('tenant.school.id'), nullable=True)

    metadata_json = db.Column(db.JSON, nullable=True)

    targets = db.relationship("CalendarEventTarget", backref="event", cascade="all, delete-orphan")
    recipients = db.relationship("CalendarEventUser", backref="event", cascade="all, delete-orphan")


