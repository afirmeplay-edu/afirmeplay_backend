from datetime import datetime
import uuid

from app import db


class MonitoringActionHistory(db.Model):
    __tablename__ = "monitoring_action_history"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    monitoring_action_id = db.Column(
        db.String,
        db.ForeignKey("tenant.monitoring_action.id"),
        nullable=False,
    )
    changed_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    changed_at = db.Column(db.TIMESTAMP, default=datetime.utcnow, nullable=False)
    changed_fields = db.Column(db.JSON, nullable=True)
    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)
    note = db.Column(db.Text, nullable=True)

    monitoring_action = db.relationship("MonitoringAction", backref="history_entries")
    changed_by_user = db.relationship("User", foreign_keys=[changed_by])

    def to_dict(self):
        return {
            "id": self.id,
            "monitoring_action_id": self.monitoring_action_id,
            "changed_by": self.changed_by,
            "changed_by_name": getattr(self.changed_by_user, "name", None),
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "changed_fields": self.changed_fields or [],
            "old_values": self.old_values or {},
            "new_values": self.new_values or {},
            "note": self.note,
        }
