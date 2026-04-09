from app import db
import uuid


class CalendarEventResource(db.Model):
    __tablename__ = 'calendar_event_resources'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = db.Column(db.String, db.ForeignKey('calendar_events.id'), nullable=False)
    resource_type = db.Column(db.String(20), nullable=False)  # link | file
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(2000), nullable=True)
    minio_bucket = db.Column(db.String(100), nullable=True)
    minio_object_name = db.Column(db.String(500), nullable=True)
    original_filename = db.Column(db.String(500), nullable=True)
    content_type = db.Column(db.String(200), nullable=True)
    size_bytes = db.Column(db.BigInteger, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

    event = db.relationship('CalendarEvent', backref=db.backref(
        'resources',
        cascade='all, delete-orphan',
        order_by='CalendarEventResource.sort_order'
    ))
