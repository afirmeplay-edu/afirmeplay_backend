# -*- coding: utf-8 -*-
"""
Rotas para templates de competições recorrentes (Etapa 6).
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app import db
from app.competitions.models import CompetitionTemplate, Competition
from app.permissions import role_required, get_current_user_from_token
from app.competitions.constants import validate_scope_and_filter, is_valid_level
from app.competitions.services import validate_reward_config

bp = Blueprint(
    "competition_templates",
    __name__,
    url_prefix="/competition-templates",
)

ROLES_EDIT = ("admin", "coordenador", "diretor", "tecadm", "professor")


def _template_to_dict(t: CompetitionTemplate) -> dict:
    """Serializa CompetitionTemplate para JSON."""
    return {
        "id": t.id,
        "name": t.name,
        "subject_id": t.subject_id,
        "level": t.level,
        "scope": t.scope,
        "scope_filter": t.scope_filter,
        "recurrence": t.recurrence,
        "question_mode": t.question_mode,
        "question_rules": t.question_rules,
        "reward_config": t.reward_config or {},
        "ranking_criteria": t.ranking_criteria,
        "ranking_tiebreaker": t.ranking_tiebreaker,
        "ranking_visibility": t.ranking_visibility,
        "max_participants": t.max_participants,
        "active": t.active,
        "created_by": t.created_by,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _validate_template_payload(data: dict, is_update: bool = False) -> tuple[bool, str | None]:
    """Valida payload básico para criação/atualização de template."""
    required = ("name", "recurrence")
    if not is_update:
        for field in required:
            if field not in data:
                return False, f"Campo obrigatório ausente: {field}"

    level = data.get("level")
    if level is not None and not is_valid_level(level):
        return (
            False,
            "level deve ser 1 (Educação Infantil, Anos Iniciais, Educação Especial, EJA) "
            "ou 2 (Anos Finais e Ensino Médio)",
        )

    scope = data.get("scope", "individual")
    scope_filter = data.get("scope_filter")
    try:
        validate_scope_and_filter(scope, scope_filter)
    except ValueError as e:
        return False, str(e)

    reward_config = data.get("reward_config")
    if reward_config is not None:
        # Usa o validador existente de competitions
        try:
            validate_reward_config(reward_config)
        except Exception as e:  # ValidationError
            return False, str(e)

    return True, None


@bp.route("", methods=["POST"])
@jwt_required()
@role_required(*ROLES_EDIT)
def create_template():
    """Cria um novo template de competição recorrente."""
    user = get_current_user_from_token()
    if not user:
        return jsonify({"error": "Usuário não autenticado"}), 401
    data = request.get_json() or {}

    ok, err = _validate_template_payload(data, is_update=False)
    if not ok:
        return jsonify({"error": err}), 400

    t = CompetitionTemplate(
        name=data["name"],
        subject_id=data.get("subject_id"),
        level=data.get("level"),
        scope=data.get("scope", "individual"),
        scope_filter=data.get("scope_filter"),
        recurrence=data["recurrence"],
        question_mode=data.get("question_mode", "auto_random"),
        question_rules=data.get("question_rules"),
        reward_config=data.get("reward_config"),
        ranking_criteria=data.get("ranking_criteria", "nota"),
        ranking_tiebreaker=data.get("ranking_tiebreaker", "tempo_entrega"),
        ranking_visibility=data.get("ranking_visibility", "final"),
        max_participants=data.get("max_participants"),
        active=data.get("active", True),
        created_by=user["id"],
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(_template_to_dict(t)), 201


@bp.route("", methods=["GET"])
@jwt_required()
@role_required(*ROLES_EDIT)
def list_templates():
    """Lista templates de competição com filtros simples."""
    query = CompetitionTemplate.query
    if "active" in request.args:
        active_str = request.args.get("active", "").lower()
        if active_str in ("true", "1", "yes"):
            query = query.filter(CompetitionTemplate.active.is_(True))
        elif active_str in ("false", "0", "no"):
            query = query.filter(CompetitionTemplate.active.is_(False))
    if request.args.get("subject_id"):
        query = query.filter(
            CompetitionTemplate.subject_id == request.args.get("subject_id")
        )
    if request.args.get("recurrence"):
        query = query.filter(
            CompetitionTemplate.recurrence
            == request.args.get("recurrence")
        )
    items = query.order_by(CompetitionTemplate.created_at.desc()).all()
    return jsonify([_template_to_dict(t) for t in items]), 200


@bp.route("/<template_id>", methods=["GET"])
@jwt_required()
@role_required(*ROLES_EDIT)
def get_template_detail(template_id):
    """
    Detalhes de um template + lista enxuta de competições já criadas a partir dele.
    """
    t = CompetitionTemplate.query.get_or_404(template_id)
    # Competitions relacionadas
    competitions = (
        Competition.query.filter_by(template_id=template_id)
        .order_by(Competition.created_at.desc())
        .limit(100)
        .all()
    )
    comp_list = [
        {
            "id": c.id,
            "name": c.name,
            "subject_id": c.subject_id,
            "level": c.level,
            "recurrence": c.recurrence,
            "status": c.status,
            "enrollment_start": c.enrollment_start.isoformat()
            if c.enrollment_start
            else None,
            "enrollment_end": c.enrollment_end.isoformat()
            if c.enrollment_end
            else None,
            "application": c.application.isoformat() if c.application else None,
            "expiration": c.expiration.isoformat() if c.expiration else None,
            "edition_number": c.edition_number,
            "edition_series": c.edition_series,
        }
        for c in competitions
    ]
    return jsonify({"template": _template_to_dict(t), "competitions": comp_list}), 200


@bp.route("/<template_id>", methods=["PATCH"])
@jwt_required()
@role_required(*ROLES_EDIT)
def update_template(template_id):
    """
    Atualiza campos do template.
    Não afeta competições já criadas, apenas futuras.
    """
    t = CompetitionTemplate.query.get_or_404(template_id)
    data = request.get_json() or {}

    ok, err = _validate_template_payload(data, is_update=True)
    if not ok:
        return jsonify({"error": err}), 400

    editable = {
        "name",
        "subject_id",
        "level",
        "scope",
        "scope_filter",
        "recurrence",
        "question_mode",
        "question_rules",
        "reward_config",
        "ranking_criteria",
        "ranking_tiebreaker",
        "ranking_visibility",
        "max_participants",
        "active",
    }
    for key in editable:
        if key in data:
            setattr(t, key, data[key])

    db.session.commit()
    return jsonify(_template_to_dict(t)), 200


@bp.route("/<template_id>", methods=["DELETE"])
@jwt_required()
@role_required(*ROLES_EDIT)
def delete_template(template_id):
    """
    Deleta template ou, de forma mais segura, apenas desativa (active=False).
    Aqui optamos por desativar para não perder histórico.
    """
    t = CompetitionTemplate.query.get_or_404(template_id)
    t.active = False
    db.session.commit()
    return jsonify({"message": "Template desativado com sucesso"}), 200


@bp.route("/<template_id>/deactivate", methods=["POST"])
@jwt_required()
@role_required(*ROLES_EDIT)
def deactivate_template(template_id):
    """Desativa template (para de criar novas competições)."""
    t = CompetitionTemplate.query.get_or_404(template_id)
    t.active = False
    db.session.commit()
    return jsonify(_template_to_dict(t)), 200


@bp.route("/<template_id>/activate", methods=["POST"])
@jwt_required()
@role_required(*ROLES_EDIT)
def activate_template(template_id):
    """Ativa template (volta a criar novas competições)."""
    t = CompetitionTemplate.query.get_or_404(template_id)
    t.active = True
    db.session.commit()
    return jsonify(_template_to_dict(t)), 200

