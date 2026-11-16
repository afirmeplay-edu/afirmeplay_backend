# -*- coding: utf-8 -*-
"""
Rotas do Relatório de habilidade e gabarito.

GET /habilidade-gabarito/opcoes-filtros
GET /habilidade-gabarito/resumo

Uma ou mais avaliações. Escopo: município, e opcionalmente escola, série e turma.
Prova digital por padrão. Cartão-resposta: ?report_entity_type=answer_sheet.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.habilidade_gabarito.services import build_habilidade_gabarito_digital
from app.participation_report.filters import (
    build_filter_options,
    is_answer_sheet_report,
    parse_id_list,
)
from app.permissions import get_current_user_from_token, role_required
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

bp = Blueprint("habilidade_gabarito", __name__, url_prefix="/habilidade-gabarito")
logger = logging.getLogger(__name__)

_ROLES = ("admin", "professor", "coordenador", "diretor", "tecadm")


def _parse_multi_from_request(*keys: str):
    values = []
    for key in keys:
        values.append(request.args.get(key))
        values.extend(request.args.getlist(key))
    return parse_id_list(*values)


@bp.route("/opcoes-filtros", methods=["GET"])
@jwt_required()
@role_required(*_ROLES)
def opcoes_filtros():
    """
    Estado → Município → Avaliação → Escola → Série → Turma.

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
        logger.exception("Erro em /habilidade-gabarito/opcoes-filtros: %s", e)
        return jsonify({"error": "Erro ao obter opções de filtro"}), 500


@bp.route("/resumo", methods=["GET"])
@jwt_required()
@role_required(*_ROLES)
def resumo_habilidade_gabarito():
    """
    Habilidade e gabarito das avaliações no recorte.

    Obrigatórios: estado, municipio e ao menos uma avaliação.
    Opcionais: escola/escolas, serie/series, turma/turmas (vazio = todas).
    Várias avaliações: CSV ou parâmetros repetidos.
    Cartão-resposta: ?report_entity_type=answer_sheet
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        estado = (request.args.get("estado") or "").strip()
        municipio = (request.args.get("municipio") or "").strip()
        if not estado or not municipio:
            return jsonify({"error": "Parâmetros obrigatórios: estado e municipio"}), 400

        escolas = _parse_multi_from_request("escolas", "escola")
        series = _parse_multi_from_request("series", "serie")
        turmas = _parse_multi_from_request("turmas", "turma")

        if is_answer_sheet_report(request.args):
            from app.habilidade_gabarito.answer_sheet import (
                build_habilidade_gabarito_answer_sheet,
            )

            gabaritos = _parse_multi_from_request(
                "avaliacoes", "avaliacao", "gabaritos", "gabarito"
            )
            if not gabaritos:
                return jsonify({"error": "Informe ao menos uma avaliação"}), 400
            data = build_habilidade_gabarito_answer_sheet(
                user=user,
                estado=estado,
                municipio_id=municipio,
                gabarito_ids=gabaritos,
                escola_ids=escolas or None,
                serie_ids=series or None,
                turma_ids=turmas or None,
            )
        else:
            avaliacoes = _parse_multi_from_request("avaliacoes", "avaliacao")
            if not avaliacoes:
                return jsonify({"error": "Informe ao menos uma avaliação"}), 400
            data = build_habilidade_gabarito_digital(
                user=user,
                estado=estado,
                municipio_id=municipio,
                avaliacao_ids=avaliacoes,
                escola_ids=escolas or None,
                serie_ids=series or None,
                turma_ids=turmas or None,
            )
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Erro em /habilidade-gabarito/resumo: %s", e)
        return jsonify({"error": "Erro ao montar o relatório de habilidade e gabarito"}), 500
