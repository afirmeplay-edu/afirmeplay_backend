# -*- coding: utf-8 -*-
"""
Histórico de gerações de cartões resposta (ZIP MinIO) por gabarito, no schema do tenant (city_xxx).

Cada linha representa uma geração concluída (escopo + job + URL), sem sobrescrever gerações anteriores.
"""
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from sqlalchemy.dialects.postgresql import JSONB, UUID


class AnswerSheetGabaritoGeneration(db.Model):
    """
    Registro imutável de uma geração de PDFs/ZIP para um gabarito.
    Resolvido via search_path do tenant (mesmo padrão de AnswerSheetGabarito).
    """
    __tablename__ = 'answer_sheet_generations'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    gabarito_id = db.Column(
        db.String(36),
        db.ForeignKey('answer_sheet_gabaritos.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    # Mesmo UUID do job em public.answer_sheet_generation_jobs e path MinIO gabaritos/batch/{job_id}/
    job_id = db.Column(db.String(36), nullable=False, index=True)

    scope_type = db.Column(db.String(50), nullable=True)  # class | grade | school | city

    # Payload do escopo no momento da geração (ex.: class_ids, city_id, filtros)
    scope_snapshot = db.Column(JSONB, nullable=True)

    minio_url = db.Column(db.String(500), nullable=True)
    minio_object_name = db.Column(db.String(500), nullable=True)
    minio_bucket = db.Column(db.String(100), nullable=True)
    zip_generated_at = db.Column(db.DateTime, nullable=True)

    total_classes = db.Column(db.Integer, nullable=True)
    total_students = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(30), nullable=False, default='completed')

    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    gabarito = db.relationship(
        'AnswerSheetGabarito',
        foreign_keys=[gabarito_id],
        backref=db.backref('generation_records', lazy='dynamic'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'gabarito_id': str(self.gabarito_id),
            'job_id': self.job_id,
            'scope_type': self.scope_type,
            'scope_snapshot': self.scope_snapshot,
            'minio_url': self.minio_url,
            'minio_object_name': self.minio_object_name,
            'minio_bucket': self.minio_bucket,
            'zip_generated_at': self.zip_generated_at.isoformat() if self.zip_generated_at else None,
            'total_classes': self.total_classes,
            'total_students': self.total_students,
            'status': self.status,
            'created_by': str(self.created_by) if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


logger = logging.getLogger(__name__)


def build_class_scope_entries(class_ids: List[str]) -> List[Dict[str, str]]:
    """
    Monta entradas para scope_snapshot: série + turma legíveis (ex.: "8º Ano - A").
    Requer sessão no schema da cidade (Class com grade).
    """
    if not class_ids:
        return []
    from app.models.studentClass import Class

    entries: List[Dict[str, str]] = []
    for cid in class_ids:
        if not cid:
            continue
        co = Class.query.get(cid)
        if not co:
            entries.append(
                {
                    "class_id": str(cid),
                    "class_name": "",
                    "grade_name": "",
                    "label": str(cid),
                }
            )
            continue
        gname = (co.grade.name or "").strip() if co.grade else ""
        cname = (co.name or "").strip()
        if gname and cname:
            label = f"{gname} - {cname}"
        else:
            label = gname or cname or str(co.id)
        entries.append(
            {
                "class_id": str(co.id),
                "class_name": cname,
                "grade_name": gname,
                "label": label,
            }
        )
    return entries


def enrich_scope_snapshot(scope_snapshot: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Garante class_ids como lista de objetos com label (série + turma).
    Registros antigos com lista de UUIDs em string são resolvidos via Class.
    """
    if not scope_snapshot or not isinstance(scope_snapshot, dict):
        return scope_snapshot
    out = dict(scope_snapshot)
    raw = out.get("class_ids")
    if raw is None:
        return out
    if isinstance(raw, list) and raw and isinstance(raw[0], str):
        out["class_ids"] = build_class_scope_entries([str(x) for x in raw if x])
    elif isinstance(raw, list) and raw and isinstance(raw[0], dict):
        fixed = []
        for entry in raw:
            e = dict(entry)
            if e.get("label"):
                fixed.append(e)
                continue
            gname = (e.get("grade_name") or "").strip()
            cname = (e.get("class_name") or "").strip()
            if gname and cname:
                e["label"] = f"{gname} - {cname}"
            else:
                e["label"] = gname or cname or str(e.get("class_id", ""))
            fixed.append(e)
        out["class_ids"] = fixed
    return out


def record_answer_sheet_generations(
    gabarito_ids: List[str],
    batch_id: str,
    scope: str,
    scope_snapshot: Optional[Dict[str, Any]],
    minio_url: Optional[str],
    minio_object_name: Optional[str],
    minio_bucket: Optional[str],
    total_classes: int,
    total_students: int,
    created_by: Optional[str] = None,
) -> None:
    """
    Insere um registro por gabarito em answer_sheet_generations (mesmo ZIP / job).
    Falha silenciosa no log não interrompe a task Celery.
    """
    if not batch_id or not gabarito_ids or not minio_url:
        return
    now = datetime.utcnow()
    try:
        for gid in gabarito_ids:
            row = AnswerSheetGabaritoGeneration(
                gabarito_id=str(gid),
                job_id=str(batch_id),
                scope_type=scope,
                scope_snapshot=scope_snapshot,
                minio_url=minio_url,
                minio_object_name=minio_object_name,
                minio_bucket=minio_bucket,
                zip_generated_at=now,
                total_classes=total_classes,
                total_students=total_students,
                status='completed',
                created_by=created_by,
                created_at=now,
            )
            db.session.add(row)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.warning(
            'Não foi possível gravar answer_sheet_generations (tabela existe no schema?): %s',
            e,
            exc_info=True,
        )
