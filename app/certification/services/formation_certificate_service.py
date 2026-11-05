# -*- coding: utf-8 -*-
"""Serviço de certificados de formação (participantes híbridos)."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app import db
from app.certification.models.formation_certificate import (
    FormationCertificateEvent,
    FormationCertificateParticipant,
)
from app.models.user import User
from app.utils.tenant_middleware import get_current_tenant_context

DEFAULT_CERTIFICATE_TEXT = (
    "participou das Formações Continuadas para {publico} da Secretaria Municipal de Educação "
    "(SEMED), ministradas por {formador}, realizadas no ano de {ano},"
)

DEFAULT_TOPICS = [
    {"text": "Gestão pedagógica e monitoramento da aprendizagem", "hours": 4},
    {"text": "Avaliação formativa e práticas de sala de aula", "hours": 4},
]


def _city_id() -> Optional[str]:
    context = get_current_tenant_context()
    city_id = getattr(context, "city_id", None) if context else None
    return str(city_id) if city_id else None


def _user_id(user: Dict[str, Any]) -> str:
    uid = user.get("id") or user.get("user_id")
    if not uid:
        raise ValueError("Usuário inválido.")
    return str(uid)


def _normalize_topics(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return list(DEFAULT_TOPICS)
    if not isinstance(raw, list):
        raise ValueError("topics deve ser uma lista de {text, hours}.")
    topics = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Cada temática deve ser um objeto {text, hours}.")
        text = str(item.get("text") or "").strip()
        if not text:
            raise ValueError("Cada temática precisa de texto.")
        try:
            hours = float(item.get("hours") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("hours deve ser um número.") from exc
        if hours < 0:
            raise ValueError("hours não pode ser negativo.")
        topics.append({"text": text, "hours": hours})
    return topics


def _apply_event_fields(event: FormationCertificateEvent, data: Dict[str, Any]) -> None:
    mapping = {
        "title": "title",
        "trainer": "trainer",
        "audience": "audience",
        "subtitle": "subtitle",
        "certificateText": "certificate_text",
        "year": "year",
        "issuedText": "issued_text",
        "signerRole": "signer_role",
        "signatureUrl": "signature_url",
        "verifyUrl": "verify_url",
    }
    for src, dst in mapping.items():
        if src in data:
            value = data.get(src)
            if value is None:
                setattr(event, dst, None)
            else:
                setattr(event, dst, str(value).strip() if isinstance(value, str) else value)
    if "topics" in data:
        event.topics = _normalize_topics(data.get("topics"))


class FormationCertificateService:
    @staticmethod
    def list_events(user: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = FormationCertificateEvent.query.order_by(
            FormationCertificateEvent.created_at.desc()
        )
        city_id = _city_id()
        if city_id and user.get("role") != "admin":
            query = query.filter(FormationCertificateEvent.municipality_id == city_id)
        return [event.to_dict() for event in query.all()]

    @staticmethod
    def get_event(event_id: str, include_participants: bool = True) -> FormationCertificateEvent:
        event = FormationCertificateEvent.query.filter_by(id=str(event_id)).first()
        if not event:
            raise LookupError("Evento de formação não encontrado.")
        return event

    @staticmethod
    def create_event(user: Dict[str, Any], data: Dict[str, Any]) -> FormationCertificateEvent:
        if not isinstance(data, dict):
            raise ValueError("Corpo da requisição inválido.")
        event = FormationCertificateEvent(
            title=str(data.get("title") or "Formação Continuada").strip(),
            trainer=str(data.get("trainer") or "").strip(),
            audience=str(data.get("audience") or "").strip(),
            subtitle=str(data.get("subtitle") or "").strip() or None,
            certificate_text=str(data.get("certificateText") or DEFAULT_CERTIFICATE_TEXT).strip(),
            year=str(data.get("year") or datetime.now().year).strip(),
            issued_text=str(data.get("issuedText") or "").strip() or None,
            signer_role=str(data.get("signerRole") or "Secretário Municipal de Educação").strip(),
            signature_url=str(data.get("signatureUrl") or "").strip() or None,
            verify_url=str(data.get("verifyUrl") or "").strip() or None,
            topics=_normalize_topics(data.get("topics")),
            municipality_id=_city_id(),
            status="draft",
            created_by=_user_id(user),
        )
        db.session.add(event)
        db.session.commit()
        return event

    @staticmethod
    def update_event(event_id: str, data: Dict[str, Any]) -> FormationCertificateEvent:
        event = FormationCertificateService.get_event(event_id)
        if not isinstance(data, dict) or not data:
            raise ValueError("Corpo da requisição inválido.")
        _apply_event_fields(event, data)
        db.session.commit()
        return event

    @staticmethod
    def delete_event(event_id: str) -> None:
        event = FormationCertificateService.get_event(event_id)
        if event.status == "issued" and any(p.issued_at for p in event.participants or []):
            raise ValueError("Não é possível excluir um evento com certificados já emitidos.")
        db.session.delete(event)
        db.session.commit()

    @staticmethod
    def add_participants(
        event_id: str,
        data: Dict[str, Any],
    ) -> List[FormationCertificateParticipant]:
        event = FormationCertificateService.get_event(event_id)
        created: List[FormationCertificateParticipant] = []

        rows = data.get("participants") if isinstance(data, dict) else None
        if rows is None and isinstance(data, dict) and data.get("name"):
            rows = [data]
        if not isinstance(rows, list) or not rows:
            raise ValueError("Informe participants: [{name, externalRef?}].")

        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Cada participante deve ser um objeto.")
            name = str(row.get("name") or "").strip()
            if not name:
                raise ValueError("Nome do participante é obrigatório.")
            participant = FormationCertificateParticipant(
                event_id=event.id,
                name=name,
                external_ref=str(row.get("externalRef") or row.get("matricula") or "").strip() or None,
                user_id=str(row.get("userId")).strip() if row.get("userId") else None,
                certificate_code=str(uuid.uuid4()),
            )
            db.session.add(participant)
            created.append(participant)
        db.session.commit()
        return created

    @staticmethod
    def add_participants_from_csv(event_id: str, file_storage) -> List[FormationCertificateParticipant]:
        raw = file_storage.read()
        if not raw:
            raise ValueError("Arquivo CSV vazio.")
        text = raw.decode("utf-8-sig", errors="replace")
        sample = text[:2048]
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        rows = []
        for row in reader:
            lowered = {str(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            name = lowered.get("nome") or lowered.get("name") or ""
            ref = lowered.get("matricula") or lowered.get("externalref") or lowered.get("ref") or ""
            if name:
                rows.append({"name": name, "externalRef": ref or None})
        if not rows:
            raise ValueError("Nenhum participante válido no CSV (colunas nome;matricula).")
        return FormationCertificateService.add_participants(event_id, {"participants": rows})

    @staticmethod
    def add_participants_from_users(
        event_id: str,
        data: Dict[str, Any],
    ) -> List[FormationCertificateParticipant]:
        user_ids = data.get("userIds") if isinstance(data, dict) else None
        if not isinstance(user_ids, list) or not user_ids:
            raise ValueError("Informe userIds: [id, ...].")
        users = User.query.filter(User.id.in_([str(uid) for uid in user_ids])).all()
        by_id = {u.id: u for u in users}
        rows = []
        for uid in user_ids:
            user = by_id.get(str(uid))
            if not user:
                raise ValueError(f"Usuário não encontrado: {uid}.")
            rows.append({
                "name": user.name or user.email or str(uid),
                "userId": user.id,
                "externalRef": getattr(user, "registration", None) or None,
            })
        return FormationCertificateService.add_participants(event_id, {"participants": rows})

    @staticmethod
    def remove_participant(event_id: str, participant_id: str) -> None:
        participant = FormationCertificateParticipant.query.filter_by(
            id=str(participant_id), event_id=str(event_id)
        ).first()
        if not participant:
            raise LookupError("Participante não encontrado.")
        if participant.issued_at:
            raise ValueError("Não é possível remover participante com certificado emitido.")
        db.session.delete(participant)
        db.session.commit()

    @staticmethod
    def issue(event_id: str, participant_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        event = FormationCertificateService.get_event(event_id)
        targets = list(event.participants or [])
        if participant_ids:
            wanted = set(str(pid) for pid in participant_ids)
            targets = [p for p in targets if p.id in wanted]
        if not targets:
            raise ValueError("Nenhum participante para emitir.")
        now = datetime.now(timezone.utc)
        issued = 0
        for participant in targets:
            if not participant.certificate_code:
                participant.certificate_code = str(uuid.uuid4())
            if participant.issued_at is None:
                participant.issued_at = now
                issued += 1
        event.status = "issued"
        db.session.commit()
        return {
            "eventId": event.id,
            "issued": issued,
            "total": len(targets),
            "participants": [p.to_dict() for p in targets],
        }

    @staticmethod
    def batch_payload(event_id: str) -> Dict[str, Any]:
        event = FormationCertificateService.get_event(event_id)
        return {
            "event": event.to_dict(include_participants=True),
            "participants": [p.to_dict() for p in (event.participants or [])],
        }

    @staticmethod
    def validate_code(code: str) -> Dict[str, Any]:
        participant = FormationCertificateParticipant.query.filter_by(
            certificate_code=str(code)
        ).first()
        if not participant or not participant.issued_at:
            raise LookupError("Certificado não encontrado ou ainda não emitido.")
        event = participant.event
        return {
            "valid": True,
            "certificateCode": participant.certificate_code,
            "participantName": participant.name,
            "externalRef": participant.external_ref,
            "issuedAt": participant.issued_at.isoformat() if participant.issued_at else None,
            "event": {
                "id": event.id,
                "title": event.title,
                "trainer": event.trainer,
                "audience": event.audience,
                "year": event.year,
                "issuedText": event.issued_text,
                "totalHours": sum(
                    float(t.get("hours") or 0) for t in (event.topics or []) if isinstance(t, dict)
                ),
            },
        }
