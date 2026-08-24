# -*- coding: utf-8 -*-
from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON, UUID


class ReadingWordList(db.Model):
    __tablename__ = "reading_word_list"
    __table_args__ = {"schema": "public"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="PALAVRAS_CONHECIDAS")
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey("public.grade.id"), nullable=True)
    items = db.Column(JSON, nullable=False, default=list)
    description = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    scope_type = db.Column(db.String(20), nullable=False, default="GLOBAL")
    owner_city_id = db.Column(db.String, db.ForeignKey("public.city.id"), nullable=True)
    owner_user_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    created_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    creator = db.relationship("User", foreign_keys=[created_by])
    grade = db.relationship("Grade", foreign_keys=[grade_id])

    def to_dict(self):
        items = self.items if isinstance(self.items, list) else []
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "gradeId": str(self.grade_id) if self.grade_id else None,
            "grade": (
                {"id": str(self.grade.id), "name": self.grade.name}
                if self.grade
                else None
            ),
            "items": items,
            "description": self.description,
            "isDefault": bool(self.is_default),
            "active": bool(self.active),
            "scopeType": self.scope_type,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
