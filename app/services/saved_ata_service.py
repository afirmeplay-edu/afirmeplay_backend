from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import desc

from app import db
from app.models.saved_ata_sala import SavedAtaSala
from app.models.user import User
from app.permissions.utils import get_manager_school, get_teacher_schools


class SavedAtaValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


VALID_MODOS = {"turma", "avaliacao", "cartao_resposta"}


def _user_role(user: Dict[str, Any]) -> str:
    role = user.get("role")
    return (role.value if hasattr(role, "value") else str(role or "")).lower()


def _allowed_school_ids(user: Dict[str, Any]) -> Optional[Set[str]]:
    """
    None = sem filtro de escola (admin/tecadm no tenant).
    Set vazio = nenhuma escola permitida.
    """
    role = _user_role(user)
    if role in ("admin", "tecadm"):
        return None
    if role in ("diretor", "coordenador"):
        school_id = get_manager_school(user["id"])
        return {school_id} if school_id else set()
    if role == "professor":
        return set(get_teacher_schools(user["id"]) or [])
    return set()


def _apply_visibility(query, user: Dict[str, Any]):
    allowed = _allowed_school_ids(user)
    if allowed is None:
        return query
    if not allowed:
        return query.filter(False)
    return query.filter(SavedAtaSala.school_id.in_(list(allowed)))


def _resolve_author_name(user: Dict[str, Any]) -> str:
    db_user = User.query.get(user["id"])
    name = (db_user.name if db_user else None) or user.get("name") or user.get("email") or "Usuário"
    return str(name).strip() or "Usuário"


def _validate_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], str, str, str, str]:
    if not isinstance(payload, dict):
        raise SavedAtaValidationError("Corpo da requisição inválido.")

    title = str(payload.get("title") or "").strip()
    filters = payload.get("filters")
    content = payload.get("content")

    if not isinstance(filters, dict):
        raise SavedAtaValidationError("Campo 'filters' é obrigatório.")
    if not isinstance(content, dict):
        raise SavedAtaValidationError("Campo 'content' é obrigatório.")

    city_id = str(filters.get("municipio_id") or "").strip()
    school_id = str(filters.get("escola_id") or "").strip()
    if not city_id or city_id == "all":
        raise SavedAtaValidationError("Selecione o município antes de salvar.")
    if not school_id or school_id == "all":
        raise SavedAtaValidationError("Selecione a escola antes de salvar.")

    modo_lista = str(filters.get("modo_lista") or "").strip()
    if modo_lista not in VALID_MODOS:
        raise SavedAtaValidationError("Modo de lista inválido.")

    if not title:
        escola = str(content.get("escola") or "").strip()
        serie_turma = str(content.get("serieTurma") or "").strip()
        disciplina = str(content.get("disciplina") or "").strip()
        parts = [p for p in [escola, serie_turma, disciplina] if p]
        title = " — ".join(parts) if parts else "Ata de sala"

    return filters, content, title, city_id, school_id, modo_lista


def _serialize_summary(record: SavedAtaSala, user: Dict[str, Any]) -> Dict[str, Any]:
    content = record.content if isinstance(record.content, dict) else {}
    return {
        "id": str(record.id),
        "title": record.title,
        "created_by_name": record.created_by_name,
        "created_by_user_id": str(record.user_id),
        "escola": content.get("escola") or "",
        "serie_turma": content.get("serieTurma") or "",
        "disciplina": content.get("disciplina") or "",
        "modo_lista": record.modo_lista,
        "school_id": str(record.school_id),
        "city_id": str(record.city_id),
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "is_owner": str(record.user_id) == str(user["id"]),
    }


def _serialize_detail(record: SavedAtaSala, user: Dict[str, Any]) -> Dict[str, Any]:
    data = _serialize_summary(record, user)
    data["filters"] = record.filters if isinstance(record.filters, dict) else {}
    data["content"] = record.content if isinstance(record.content, dict) else {}
    return data


def _get_visible_or_404(user: Dict[str, Any], ata_id: str) -> SavedAtaSala:
    record = _apply_visibility(SavedAtaSala.query, user).filter(SavedAtaSala.id == ata_id).first()
    if not record:
        raise SavedAtaValidationError("Ata não encontrada ou sem permissão de acesso.")
    return record


class SavedAtaService:
    @staticmethod
    def list_saved(user: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        page = max(1, int(args.get("page") or 1))
        per_page = min(100, max(1, int(args.get("per_page") or 20)))
        search = str(args.get("search") or "").strip().lower()

        query = _apply_visibility(SavedAtaSala.query, user).order_by(desc(SavedAtaSala.updated_at))

        if search:
            like = f"%{search}%"
            query = query.filter(
                db.or_(
                    SavedAtaSala.title.ilike(like),
                    SavedAtaSala.created_by_name.ilike(like),
                )
            )

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        items = [_serialize_summary(row, user) for row in pagination.items]

        return {
            "items": items,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        }

    @staticmethod
    def get_saved(user: Dict[str, Any], ata_id: str) -> Dict[str, Any]:
        record = _get_visible_or_404(user, ata_id)
        return _serialize_detail(record, user)

    @staticmethod
    def create_saved(user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        filters, content, title, city_id, school_id, modo_lista = _validate_payload(payload)

        allowed = _allowed_school_ids(user)
        if allowed is not None and school_id not in allowed:
            raise SavedAtaValidationError("Sem permissão para salvar ata nesta escola.")

        record = SavedAtaSala(
            user_id=str(user["id"]),
            created_by_name=_resolve_author_name(user),
            city_id=city_id,
            school_id=school_id,
            title=title,
            modo_lista=modo_lista,
            filters=filters,
            content=content,
        )
        db.session.add(record)
        db.session.commit()
        return _serialize_detail(record, user)

    @staticmethod
    def update_saved(user: Dict[str, Any], ata_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = _get_visible_or_404(user, ata_id)
        if str(record.user_id) != str(user["id"]):
            raise SavedAtaValidationError("Somente o autor pode editar esta ata.")

        filters, content, title, city_id, school_id, modo_lista = _validate_payload(payload)

        allowed = _allowed_school_ids(user)
        if allowed is not None and school_id not in allowed:
            raise SavedAtaValidationError("Sem permissão para salvar ata nesta escola.")

        record.title = title
        record.city_id = city_id
        record.school_id = school_id
        record.modo_lista = modo_lista
        record.filters = filters
        record.content = content
        record.created_by_name = _resolve_author_name(user)
        db.session.commit()
        return _serialize_detail(record, user)

    @staticmethod
    def delete_saved(user: Dict[str, Any], ata_id: str) -> Dict[str, Any]:
        record = _get_visible_or_404(user, ata_id)
        if str(record.user_id) != str(user["id"]):
            raise SavedAtaValidationError("Somente o autor pode excluir esta ata.")

        db.session.delete(record)
        db.session.commit()
        return {"message": "Ata excluída com sucesso.", "id": str(ata_id)}
