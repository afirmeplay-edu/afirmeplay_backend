# -*- coding: utf-8 -*-
"""
Rotas do Relatório de Tempo de Prova.

GET /tempo-prova/opcoes-filtros
GET /tempo-prova/resumo
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.participation_report.filters import parse_id_list
from app.permissions import get_current_user_from_token, role_required
from app.tempo_prova.filters import build_filter_options
from app.tempo_prova.services import build_tempo_prova_report

bp = Blueprint("tempo_prova", __name__, url_prefix="/tempo-prova")


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
    Opções hierárquicas: Estado → Município → Avaliação → Escola → Série → Turma → Aluno.
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
        logging.exception("Erro em /tempo-prova/opcoes-filtros: %s", e)
        return jsonify({"error": "Erro ao obter opções de filtro"}), 500


@bp.route("/resumo", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def resumo_tempo_prova():
    """
    Relatório de tempo de prova no escopo filtrado.

    Online: tempo real da sessão / nº de questões.
    Mobile: tempo estimado da série (1º-2º = 90 min, 3º-9º = 150 min) / nº de questões.
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

        data = build_tempo_prova_report(
            user=user,
            estado=estado,
            municipio_id=municipio,
            avaliacao_ids=_parse_multi_from_request("avaliacoes", "avaliacao") or None,
            escola_ids=_parse_multi_from_request("escolas", "escola") or None,
            serie_ids=_parse_multi_from_request("series", "serie") or None,
            turma_ids=_parse_multi_from_request("turmas", "turma") or None,
            aluno_ids=_parse_multi_from_request("alunos", "aluno") or None,
        )
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logging.exception("Erro em /tempo-prova/resumo: %s", e)
        return jsonify({"error": "Erro ao calcular relatório de tempo de prova"}), 500
