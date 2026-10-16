# -*- coding: utf-8 -*-
"""
Rotas do Relatório Comparativo (prova digital).

GET  /comparative-report/opcoes-filtros
POST /comparative-report/resumo
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.permissions import get_current_user_from_token, role_required
from app.services.comparative_report_service import (
    ComparativeReportError,
    build_comparative_report,
    build_filter_options,
)

bp = Blueprint("comparative_report", __name__, url_prefix="/comparative-report")

_ROLES = ("admin", "professor", "coordenador", "diretor", "tecadm")


def _parse_id_list(*values) -> list:
    out = []
    seen = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            parts = value
        else:
            parts = str(value).split(",")
        for part in parts:
            item = str(part or "").strip()
            if not item or item.lower() == "all" or item in seen:
                continue
            seen.add(item)
            out.append(item)
    return out


@bp.route("/opcoes-filtros", methods=["GET"])
@jwt_required()
@role_required(*_ROLES)
def opcoes_filtros():
    """
    Estado → Município → Avaliações → Escola → Série → Turma.

    evaluation_ids: CSV ou params repetidos (união de opções de escola/série/turma).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        evaluation_ids = _parse_id_list(
            request.args.get("evaluation_ids"),
            request.args.get("avaliacoes"),
            request.args.getlist("evaluation_ids"),
            request.args.getlist("avaliacoes"),
            request.args.get("avaliacao"),
        )
        data = build_filter_options(
            user,
            estado=request.args.get("estado"),
            municipio=request.args.get("municipio"),
            avaliacao=request.args.get("avaliacao"),
            evaluation_ids=evaluation_ids,
            escola=request.args.get("escola"),
            serie=request.args.get("serie"),
            nome=request.args.get("nome"),
        )
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logging.exception("Erro em /comparative-report/opcoes-filtros: %s", e)
        return jsonify({"error": "Erro ao obter opções de filtro", "details": str(e)}), 500


@bp.route("/resumo", methods=["POST"])
@jwt_required()
@role_required(*_ROLES)
def resumo_comparativo():
    """
    Body JSON:
      evaluation_ids: string[] (mín. 2)
      estado, municipio: obrigatórios
      escola, serie, turma: opcionais
      alunos: regular | regular_adap | adap | todos (padrão regular)
      indicadores: string[] (mín. 1)
      report_entity_type: evaluation (único suportado nesta versão)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        body = request.get_json(silent=True) or {}
        evaluation_ids = _parse_id_list(
            body.get("evaluation_ids"),
            body.get("avaliacoes"),
            body.get("avaliacao"),
        )
        indicadores = body.get("indicadores") or body.get("indicators") or []
        if isinstance(indicadores, str):
            indicadores = [indicadores]

        data = build_comparative_report(
            user,
            evaluation_ids=evaluation_ids,
            estado=str(body.get("estado") or "").strip(),
            municipio=str(body.get("municipio") or "").strip(),
            escola=body.get("escola"),
            serie=body.get("serie"),
            turma=body.get("turma"),
            alunos=body.get("alunos", "regular"),
            indicadores=list(indicadores),
            report_entity_type=str(body.get("report_entity_type") or "evaluation"),
        )
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ComparativeReportError as ce:
        return jsonify({"error": str(ce)}), 400
    except Exception as e:
        logging.exception("Erro em /comparative-report/resumo: %s", e)
        return jsonify({"error": "Erro ao gerar relatório comparativo", "details": str(e)}), 500
