# -*- coding: utf-8 -*-
"""Certificados de formação continuada (modelo Limoeiro / formadores)."""
from __future__ import annotations

import uuid
from datetime import datetime

from app import db


class FormationCertificateEvent(db.Model):
    __tablename__ = "formation_certificate_events"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False, default="Formação Continuada")
    trainer = db.Column(db.String(255), nullable=False, default="")
    audience = db.Column(db.String(255), nullable=False, default="")
    subtitle = db.Column(db.Text, nullable=True)
    certificate_text = db.Column(db.Text, nullable=False, default="")
    year = db.Column(db.String(20), nullable=False, default="")
    issued_text = db.Column(db.String(120), nullable=True)
    signer_role = db.Column(db.String(255), nullable=True)
    signature_url = db.Column(db.String(500), nullable=True)
    verify_url = db.Column(db.String(500), nullable=True)
    topics = db.Column(db.JSON, nullable=False, default=list)  # [{text, hours}]
    municipality_id = db.Column(db.String, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="draft")  # draft | issued
    created_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    creator = db.relationship("User", foreign_keys=[created_by])
    participants = db.relationship(
        "FormationCertificateParticipant",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="FormationCertificateParticipant.created_at",
    )

    def to_dict(self, include_participants: bool = False):
        data = {
            "id": self.id,
            "title": self.title,
            "trainer": self.trainer,
            "audience": self.audience,
            "subtitle": self.subtitle,
            "certificateText": self.certificate_text,
            "year": self.year,
            "issuedText": self.issued_text,
            "signerRole": self.signer_role,
            "signatureUrl": self.signature_url,
            "verifyUrl": self.verify_url,
            "topics": list(self.topics or []),
            "municipalityId": self.municipality_id,
            "status": self.status,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "participantsCount": len(self.participants or []),
            "totalHours": sum(float(t.get("hours") or 0) for t in (self.topics or []) if isinstance(t, dict)),
        }
        if include_participants:
            data["participants"] = [p.to_dict() for p in (self.participants or [])]
        return data


class FormationCertificateParticipant(db.Model):
    __tablename__ = "formation_certificate_participants"
    __table_args__ = (
        db.UniqueConstraint("event_id", "certificate_code", name="uq_formation_cert_code"),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = db.Column(
        db.String,
        db.ForeignKey("tenant.formation_certificate_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False)
    external_ref = db.Column(db.String(120), nullable=True)
    user_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    certificate_code = db.Column(db.String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    issued_at = db.Column(db.TIMESTAMP, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))

    event = db.relationship("FormationCertificateEvent", back_populates="participants")
    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "eventId": self.event_id,
            "name": self.name,
            "externalRef": self.external_ref,
            "userId": self.user_id,
            "certificateCode": self.certificate_code,
            "issuedAt": self.issued_at.isoformat() if self.issued_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
