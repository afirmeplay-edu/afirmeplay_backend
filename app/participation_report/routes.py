# -*- coding: utf-8 -*-
"""
Rotas do relatório de participação.

GET /participation-report/opcoes-filtros
GET /participation-report/resumo
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.participation_report.filters import build_filter_options, parse_id_list
from app.participation_report.services import build_participation_report
from app.permissions import get_current_user_from_token, role_required

bp = Blueprint("participation_report", __name__, url_prefix="/participation-report")


def _parse_multi_from_request(*keys: str):
    values = []
    for key in keys:
        values.append(request.args.get(key))
        values.extend(request.args.getlist(key))
    return parse_id_list(*values)


@bp.route("/opcoes-filtros", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def opcoes_filtros():
    """
    Opções hierárquicas de filtro.

    Estado → Município → Avaliação → Escola → Série → Turma

    Multi-select (CSV ou params repetidos): avaliacoes, escolas, series, turmas.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        data = build_filter_options(user, request.args)
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logging.exception("Erro em /participation-report/opcoes-filtros: %s", e)
        return jsonify({"error": "Erro ao obter opções de filtro"}), 500


@bp.route("/resumo", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def resumo_participacao():
    """
    Resumo de participação no escopo filtrado.

    Obrigatórios: estado, municipio.
    Opcionais multi: avaliacoes, escolas, series, turmas.
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

        avaliacoes = _parse_multi_from_request("avaliacoes", "avaliacao")
        escolas = _parse_multi_from_request("escolas", "escola")
        series = _parse_multi_from_request("series", "serie")
        turmas = _parse_multi_from_request("turmas", "turma")

        data = build_participation_report(
            user=user,
            estado=estado,
            municipio_id=municipio,
            avaliacao_ids=avaliacoes or None,
            escola_ids=escolas or None,
            serie_ids=series or None,
            turma_ids=turmas or None,
        )
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logging.exception("Erro em /participation-report/resumo: %s", e)
        return jsonify({"error": "Erro ao calcular relatório de participação"}), 500
