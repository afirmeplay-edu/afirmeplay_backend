from app import db
from enum import Enum
import uuid


class CalendarTargetType(Enum):
    ALL = "ALL"
    ROLE_GROUP = "ROLE_GROUP"
    MUNICIPALITY = "MUNICIPALITY"
    SCHOOL = "SCHOOL"
    GRADE = "GRADE"
    CLASS = "CLASS"
    USER = "USER"


class CalendarEventTarget(db.Model):
    __tablename__ = 'calendar_event_targets'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = db.Column(db.String, db.ForeignKey('tenant.calendar_events.id'), nullable=False)

    target_type = db.Column(db.Enum(CalendarTargetType), nullable=False)
    target_id = db.Column(db.String, nullable=True)
    target_filters = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())


