# -*- coding: utf-8 -*-
"""
Rotas do boletim do aluno.

GET /boletim-aluno/opcoes-filtros
GET /boletim-aluno/resumo

Uma avaliação (ou gabarito) por vez. Aluno: um id ou todos (paginado).
Só entram alunos que realizaram a prova. Discursiva fica de fora.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.boletim_aluno.filters import build_boletim_filter_options
from app.boletim_aluno.helpers import parse_aluno_param, parse_pagination
from app.boletim_aluno.services import build_boletins_digital
from app.participation_report.filters import is_answer_sheet_report, parse_id_list
from app.permissions import get_current_user_from_token, role_required
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

bp = Blueprint("boletim_aluno", __name__, url_prefix="/boletim-aluno")
logger = logging.getLogger(__name__)


def _parse_multi_from_request(*keys: str):
    values = []
    for key in keys:
        values.append(request.args.get(key))
        values.extend(request.args.getlist(key))
    return parse_id_list(*values)


def _require_single_avaliacao(ids: list, label: str = "avaliação") -> str:
    if len(ids) != 1:
        raise ValueError(f"Informe exatamente uma {label}")
    return ids[0]


@bp.route("/opcoes-filtros", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def opcoes_filtros():
    """
    Estado → Município → Avaliação → Escola → Série → Turma → Aluno.

    ``alunos`` só lista quem fez a prova. Paginado (page, per_page) e filtrável por nome.
    Cartão-resposta: ?report_entity_type=answer_sheet
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        municipio = (request.args.get("municipio") or "").strip()
        if municipio:
            set_search_path(city_id_to_schema_name(municipio))

        data = build_boletim_filter_options(user, request.args)
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logger.exception("Erro em /boletim-aluno/opcoes-filtros: %s", e)
        return jsonify({"error": "Erro ao obter opções de filtro"}), 500


@bp.route("/resumo", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def resumo_boletim():
    """
    Boletins no recorte.

    Obrigatórios: estado, municipio, avaliacao (exatamente uma).
    Aluno: um id, ou omitido / all = todos (paginado).
    Opcionais: escola, serie, turma, nome, page, per_page.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        estado = (request.args.get("estado") or "").strip()
        municipio = (request.args.get("municipio") or "").strip()
        if not estado or not municipio:
            return jsonify(
                {"error": "Parâmetros obrigatórios: estado e municipio"}
            ), 400

        escolas = _parse_multi_from_request("escolas", "escola")
        series = _parse_multi_from_request("series", "serie")
        turmas = _parse_multi_from_request("turmas", "turma")
        aluno_id = parse_aluno_param(_parse_multi_from_request("alunos", "aluno"))
        nome = (request.args.get("nome") or request.args.get("q") or "").strip() or None
        page, per_page = parse_pagination(
            request.args.get("page"), request.args.get("per_page")
        )

        if is_answer_sheet_report(request.args):
            from app.boletim_aluno.answer_sheet import build_boletins_answer_sheet

            gabarito_id = _require_single_avaliacao(
                _parse_multi_from_request(
                    "avaliacoes", "avaliacao", "gabaritos", "gabarito"
                ),
                "avaliação (gabarito)",
            )
            data = build_boletins_answer_sheet(
                user=user,
                estado=estado,
                municipio_id=municipio,
                gabarito_id=gabarito_id,
                escola_ids=escolas or None,
                serie_ids=series or None,
                turma_ids=turmas or None,
                aluno_id=aluno_id,
                nome=nome,
                page=page,
                per_page=per_page,
            )
        else:
            avaliacao_id = _require_single_avaliacao(
                _parse_multi_from_request("avaliacoes", "avaliacao")
            )
            data = build_boletins_digital(
                user=user,
                estado=estado,
                municipio_id=municipio,
                avaliacao_id=avaliacao_id,
                escola_ids=escolas or None,
                serie_ids=series or None,
                turma_ids=turmas or None,
                aluno_id=aluno_id,
                nome=nome,
                page=page,
                per_page=per_page,
            )
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except LookupError as le:
        return jsonify({"error": str(le)}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Erro em /boletim-aluno/resumo: %s", e)
        return jsonify({"error": "Erro ao calcular o boletim do aluno"}), 500
