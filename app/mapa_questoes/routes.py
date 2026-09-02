# -*- coding: utf-8 -*-
"""
Rotas do mapa de questões.

GET /mapa-questoes/opcoes-filtros
GET /mapa-questoes/resumo

Uma avaliação (ou gabarito) por vez.
Dual-path: sem param = prova digital; report_entity_type=answer_sheet = cartão-resposta.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.mapa_questoes.services import build_mapa_questoes_digital
from app.participation_report.filters import (
    build_filter_options,
    is_answer_sheet_report,
    parse_id_list,
)
from app.permissions import get_current_user_from_token, role_required
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

bp = Blueprint("mapa_questoes", __name__, url_prefix="/mapa-questoes")
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
    Opções hierárquicas: Estado → Município → Avaliação → Escola → Série → Turma.

    Mesmo contrato do relatório de participação. Cartão-resposta:
    ?report_entity_type=answer_sheet (avaliacoes = ids de gabarito).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        municipio = (request.args.get("municipio") or "").strip()
        if municipio:
            set_search_path(city_id_to_schema_name(municipio))

        data = build_filter_options(user, request.args)
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logger.exception("Erro em /mapa-questoes/opcoes-filtros: %s", e)
        return jsonify({"error": "Erro ao obter opções de filtro"}), 500


@bp.route("/resumo", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def resumo_mapa_questoes():
    """
    Mapa de questões no recorte filtrado.

    Obrigatórios: estado, municipio, avaliacao (exatamente uma).
    Opcionais: escola/escolas, serie/series, turma/turmas (vazio = todas).
    Cartão-resposta: ?report_entity_type=answer_sheet
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

        if is_answer_sheet_report(request.args):
            from app.mapa_questoes.answer_sheet import build_mapa_questoes_answer_sheet

            gabaritos = _parse_multi_from_request(
                "avaliacoes", "avaliacao", "gabaritos", "gabarito"
            )
            gabarito_id = _require_single_avaliacao(gabaritos, "avaliação (gabarito)")
            data = build_mapa_questoes_answer_sheet(
                user=user,
                estado=estado,
                municipio_id=municipio,
                gabarito_id=gabarito_id,
                escola_ids=escolas or None,
                serie_ids=series or None,
                turma_ids=turmas or None,
            )
        else:
            avaliacoes = _parse_multi_from_request("avaliacoes", "avaliacao")
            avaliacao_id = _require_single_avaliacao(avaliacoes)
            data = build_mapa_questoes_digital(
                user=user,
                estado=estado,
                municipio_id=municipio,
                avaliacao_id=avaliacao_id,
                escola_ids=escolas or None,
                serie_ids=series or None,
                turma_ids=turmas or None,
            )
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except LookupError as le:
        return jsonify({"error": str(le)}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Erro em /mapa-questoes/resumo: %s", e)
        return jsonify({"error": "Erro ao calcular o mapa de questões"}), 500
