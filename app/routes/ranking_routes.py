# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Tuple

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.decorators import requires_city_context
from app.decorators.role_required import get_current_user_from_token, role_required
from app.services.ranking_report_service import RankingReportService

bp = Blueprint("ranking_routes", __name__, url_prefix="/ranking")


def _clean_arg(value: str | None, *, allow_all: bool = False) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if not allow_all and cleaned.lower() == "all":
        return None
    return cleaned


def parse_ranking_request_args(args) -> Tuple[str, int, int, Dict[str, str]]:
    ranking_type = (args.get("ranking_type") or "general").strip().lower()
    page = int(args.get("page", 1))
    per_page = int(args.get("per_page", 20))
    avaliacao = _clean_arg(args.get("avaliacao"))
    gabarito_id = _clean_arg(args.get("gabarito_id"))
    evaluation_id = _clean_arg(args.get("evaluation_id"))
    answer_sheet_id = _clean_arg(args.get("answer_sheet_id"))

    if ranking_type == "specific_evaluation" and not evaluation_id:
        evaluation_id = avaliacao
    if ranking_type == "specific_answer_sheet" and not answer_sheet_id:
        answer_sheet_id = avaliacao or gabarito_id

    filters = {
        "scope": (_clean_arg(args.get("scope")) or "").lower() or None,
        "estado": _clean_arg(args.get("estado")),
        "municipio": _clean_arg(args.get("municipio")),
        "escola": _clean_arg(args.get("escola")),
        "serie": _clean_arg(args.get("serie")),
        "turma": _clean_arg(args.get("turma")),
        "periodo": _clean_arg(args.get("periodo")),
        "disciplina": _clean_arg(args.get("disciplina")),
        "avaliacao": avaliacao,
        "gabarito_id": gabarito_id,
        "evaluation_id": evaluation_id,
        "answer_sheet_id": answer_sheet_id,
    }
    return ranking_type, page, per_page, filters


def validate_ranking_filters(ranking_type: str, filters: Dict[str, str]) -> None:
    estado = filters.get("estado")
    municipio = filters.get("municipio")

    if not estado:
        raise ValueError("Estado é obrigatório e não pode ser 'all'.")
    if not municipio:
        raise ValueError("Município é obrigatório e não pode ser 'all'.")

    filtros_aplicados = sum(
        [
            bool(filters.get("estado")),
            bool(filters.get("municipio")),
            bool(filters.get("escola")),
            bool(filters.get("serie")),
            bool(filters.get("turma")),
            bool(filters.get("periodo")),
        ]
    )
    if filtros_aplicados < 2:
        raise ValueError("É necessário aplicar pelo menos 2 filtros válidos (excluindo 'all').")

    if ranking_type == "specific_evaluation" and not filters.get("evaluation_id"):
        raise ValueError(
            "Selecione uma avaliação no filtro 'avaliacao' para ranking_type=specific_evaluation."
        )
    if ranking_type == "specific_answer_sheet" and not filters.get("answer_sheet_id"):
        raise ValueError(
            "Selecione um cartão resposta no filtro 'avaliacao' para ranking_type=specific_answer_sheet."
        )


@bp.route("/report", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
@requires_city_context
def ranking_report():
    """
    Endpoint unificado para ranking geral, por avaliação/cartão e professores.

    Query params:
      - ranking_type: general | specific_evaluation | specific_answer_sheet | teachers
      - scope: turma | escola | municipio
      - estado, municipio, escola, serie, turma, periodo
      - avaliacao (id selecionado na lista de filtros)
      - evaluation_id e answer_sheet_id seguem aceitos por compatibilidade
      - page, per_page
    """
    try:
        ranking_type, page, per_page, filters = parse_ranking_request_args(request.args)
        validate_ranking_filters(ranking_type, filters)
        req = RankingReportService.build_request(
            ranking_type,
            page=page,
            per_page=per_page,
            filters=filters,
        )
        user = get_current_user_from_token()
        payload = RankingReportService.get_report(user, req)
        return jsonify(payload), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro de banco ao gerar ranking.", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao gerar relatório de ranking.", "details": str(e)}), 500
