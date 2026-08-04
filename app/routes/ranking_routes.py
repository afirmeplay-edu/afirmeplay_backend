# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Tuple

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.decorators import requires_city_context
from app.decorators.role_required import get_current_user_from_token, role_required
from app.services.class_peer_ranking_service import ClassPeerRankingService
from app.services.ranking_report_service import RankingReportService

bp = Blueprint("ranking_routes", __name__, url_prefix="/ranking")


def _clean_arg(value: str | None, *, allow_all: bool = False) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if not allow_all and cleaned.lower() == "all":
        return None
    return cleaned


def _parse_id_list(args, *, multi_key: str, single_keys: tuple[str, ...]) -> list[str]:
    """Aceita CSV em multi_key ou um único ID em qualquer single_key (compatibilidade)."""
    ids: list[str] = []
    raw_multi = args.get(multi_key)
    if raw_multi and str(raw_multi).strip():
        ids = [part.strip() for part in str(raw_multi).split(",") if part.strip()]
    if not ids:
        for key in single_keys:
            single = _clean_arg(args.get(key))
            if single:
                ids = [single]
                break
    seen: set[str] = set()
    unique: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def parse_ranking_request_args(args) -> Tuple[str, int, int, Dict[str, str]]:
    ranking_type = (args.get("ranking_type") or "general").strip().lower()
    page = int(args.get("page", 1))
    per_page = int(args.get("per_page", 20))
    avaliacao = _clean_arg(args.get("avaliacao"))
    gabarito_id = _clean_arg(args.get("gabarito_id"))

    evaluation_ids = _parse_id_list(
        args, multi_key="evaluation_ids", single_keys=("evaluation_id",)
    )
    answer_sheet_ids = _parse_id_list(
        args, multi_key="answer_sheet_ids", single_keys=("answer_sheet_id", "gabarito_id")
    )

    # Compat: campos singulares continuam preenchidos com o primeiro ID.
    evaluation_id = evaluation_ids[0] if evaluation_ids else None
    answer_sheet_id = answer_sheet_ids[0] if answer_sheet_ids else None

    if ranking_type == "specific_evaluation" and not evaluation_id:
        evaluation_id = avaliacao
        if evaluation_id:
            evaluation_ids = [evaluation_id]
    if ranking_type == "specific_answer_sheet" and not answer_sheet_id:
        answer_sheet_id = avaliacao or gabarito_id
        if answer_sheet_id:
            answer_sheet_ids = [answer_sheet_id]

    # Fallback legado: "avaliacao" genérico quando nenhum ID explícito veio.
    if not evaluation_ids and not answer_sheet_ids and avaliacao:
        if ranking_type == "specific_answer_sheet":
            answer_sheet_ids = [avaliacao]
            answer_sheet_id = avaliacao
        else:
            evaluation_ids = [avaliacao]
            evaluation_id = avaliacao

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
        # Listas CSV — consumidas por _build_teacher_ranking (1º/2º LP+MAT).
        "evaluation_ids": ",".join(evaluation_ids) if evaluation_ids else None,
        "answer_sheet_ids": ",".join(answer_sheet_ids) if answer_sheet_ids else None,
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

    has_evaluation = bool(filters.get("evaluation_id") or filters.get("evaluation_ids"))
    has_answer_sheet = bool(filters.get("answer_sheet_id") or filters.get("answer_sheet_ids"))

    if ranking_type == "specific_evaluation" and not has_evaluation:
        raise ValueError(
            "Selecione uma avaliação no filtro 'avaliacao' para ranking_type=specific_evaluation."
        )
    if ranking_type == "specific_answer_sheet" and not has_answer_sheet:
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
      - evaluation_id / evaluation_ids (CSV) — multi para unificar LP+MAT (ex.: 1º/2º ano)
      - answer_sheet_id / answer_sheet_ids (CSV) — idem para cartão-resposta
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


@bp.route("/classes-peer", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
@requires_city_context
def ranking_classes_peer():
    """
    Ranking de turmas iguais (mesmo nome + turno na mesma série) e alunos entre esses peers.

    Query params:
      - scope: municipio | escola
      - evaluation_id: avaliação (compatibilidade; use evaluation_ids para várias)
      - evaluation_ids: IDs separados por vírgula (consolida alunos das avaliações)
      - municipio: obrigatório se scope=municipio
      - escola: obrigatório se scope=escola
      - serie: opcional (sem filtro = uma seção por série)
      - turma_nome: opcional
      - turno: opcional
      - page, per_page: paginação do student_ranking em cada peer
    """
    try:
        req = ClassPeerRankingService.build_request(request.args)
        user = get_current_user_from_token()
        payload = ClassPeerRankingService.get_report(user, req)
        return jsonify(payload), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro de banco ao gerar ranking de turmas iguais.", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao gerar ranking de turmas iguais.", "details": str(e)}), 500


@bp.route("/geral", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
@requires_city_context
def ranking_geral():
    """
    Ranking Geral consolidado: uma única listagem de alunos (sem seções por série/turma).

    Query params (mesmos de /classes-peer):
      - scope: municipio | escola
      - evaluation_id / evaluation_ids
      - municipio, escola, serie, turma_nome, turno
      - page, per_page: paginação global da lista de alunos
    """
    try:
        req = ClassPeerRankingService.build_request(request.args)
        user = get_current_user_from_token()
        payload = ClassPeerRankingService.get_consolidated_report(user, req)
        return jsonify(payload), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Erro de banco ao gerar ranking geral.", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao gerar ranking geral.", "details": str(e)}), 500
