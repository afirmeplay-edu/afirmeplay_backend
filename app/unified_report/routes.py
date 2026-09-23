# -*- coding: utf-8 -*-
"""
Rotas do Relatório Unificado.

GET /unified-report/opcoes-filtros
GET /unified-report/dados

Contrato de resposta (GET /dados) — exemplo:

{
  "metadados": {
    "rotuloCombinado": "Avaliação 2º Bimestre 2026 · Leitura Formativa",
    "estado": "SP",
    "municipioId": "...",
    "municipioNome": "...",
    "avaliacao": {
      "id": "...",
      "titulo": "Avaliação 2º Bimestre 2026",
      "reportEntityType": "digital"
    },
    "leitura": {
      "id": "...",
      "titulo": "Fluência 2026 Formativa",
      "ano": 2026,
      "edicao": "formativa",
      "edicaoLabel": "Avaliação Formativa"
    },
    "escopo": { "escolas": ["..."], "series": [], "turmas": ["..."] }
  },
  "disciplinas": [{ "id": "...", "nome": "Língua Portuguesa" }],
  "resumo": {
    "totalAlunos": 50,
    "alunosComLeitura": 45,
    "alunosLf": 28,
    "icaPctLf": 62.22,
    "alunosSemLeitura": 5
  },
  "alunos": [
    {
      "id": "...",
      "nome": "Maria Silva",
      "turmaId": "...",
      "turmaNome": "5º Ano A",
      "escolaId": "...",
      "porDisciplina": {
        "<subject_id>": {
          "proficiencia": 250.5,
          "nota": 7.2,
          "classificacao": "Adequado"
        }
      },
      "geral": {
        "proficiencia": 240.0,
        "nota": 6.8,
        "classificacao": "Básico"
      },
      "nivelLeitura": "LF",
      "nivelLeituraLabel": "Leitor Fluente",
      "alfabetizado": true,
      "semProva": false,
      "semLeitura": false
    }
  ]
}

Campos null em proficiencia/nota/classificacao/nivelLeitura/alfabetizado
devem ser exibidos no frontend como "não avaliado".

icaPctLf = % de LF entre presentes com leitura (mesmo cálculo de
leitoresFluentesPct do Alfabetômetro). NÃO é o ica_score/Leiturômetro.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.decorators.tenant_required import requires_city_context
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.permissions.roles import Roles
from app.unified_report.unified_report_service import (
    build_unified_filter_options,
    build_unified_report,
)
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

bp = Blueprint("unified_report", __name__, url_prefix="/unified-report")
logger = logging.getLogger(__name__)

_REPORT_ROLES = tuple(Roles.REPORT_ROLES)


def _parse_multi(*keys: str):
    from app.participation_report.filters import parse_id_list

    values = []
    for key in keys:
        values.append(request.args.get(key))
        values.extend(request.args.getlist(key))
    return parse_id_list(*values)


@bp.route("/opcoes-filtros", methods=["GET"])
@jwt_required()
@role_required(*_REPORT_ROLES)
@require_feature("reports")
@require_feature("afirme_reading")
@requires_city_context
def opcoes_filtros():
    """
    Estado → Município → Avaliação/Gabarito → Escola → Série → Turma
    + bloco ``leitura`` (anos, edicoes, avaliacoes) do Alfabetômetro.

    Cartão-resposta: ?report_entity_type=answer_sheet
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        municipio = (request.args.get("municipio") or "").strip()
        if municipio:
            set_search_path(city_id_to_schema_name(municipio))

        data = build_unified_filter_options(user, request.args)
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except Exception as e:
        logger.exception("Erro em /unified-report/opcoes-filtros: %s", e)
        return jsonify({"error": "Erro ao obter opções de filtro"}), 500


@bp.route("/dados", methods=["GET"])
@jwt_required()
@role_required(*_REPORT_ROLES)
@require_feature("reports")
@require_feature("afirme_reading")
@requires_city_context
def dados_relatorio():
    """
    Relatório unificado no escopo.

    Obrigatórios:
      - estado, municipio
      - avaliacao (test_id ou gabarito_id)
      - avaliacao_leitura (ReadingEvaluation.id) — mesma seleção do Alfabetômetro
      - escola e/ou turma (uma escola / uma turma para paridade do ICA)

    Opcionais:
      - report_entity_type=answer_sheet (default: digital)
      - serie
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        estado = (request.args.get("estado") or "").strip()
        municipio = (request.args.get("municipio") or "").strip()
        if not estado or not municipio:
            return jsonify({"error": "Parâmetros obrigatórios: estado e municipio"}), 400

        set_search_path(city_id_to_schema_name(municipio))

        report_entity_type = (
            request.args.get("report_entity_type") or "digital"
        ).strip().lower()
        if report_entity_type not in ("digital", "answer_sheet"):
            return jsonify(
                {"error": "report_entity_type deve ser digital ou answer_sheet"}
            ), 400

        avaliacao_ids = _parse_multi("avaliacoes", "avaliacao", "gabaritos", "gabarito")
        if len(avaliacao_ids) != 1:
            return jsonify({"error": "Informe exatamente uma avaliação"}), 400

        leitura_ids = _parse_multi(
            "avaliacao_leitura",
            "avaliacaoLeitura",
            "avaliacao_leitura_id",
            "avaliacaoLeituraId",
        )
        if len(leitura_ids) != 1:
            return jsonify(
                {"error": "Informe exatamente uma avaliação de leitura (avaliacao_leitura)"}
            ), 400

        data = build_unified_report(
            user=user,
            estado=estado,
            municipio_id=municipio,
            report_entity_type=report_entity_type,
            avaliacao_id=avaliacao_ids[0],
            avaliacao_leitura_id=leitura_ids[0],
            escola_ids=_parse_multi("escolas", "escola") or None,
            serie_ids=_parse_multi("series", "serie") or None,
            turma_ids=_parse_multi("turmas", "turma") or None,
        )
        return jsonify(data), 200
    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except LookupError as le:
        return jsonify({"error": str(le)}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.exception("Erro em /unified-report/dados: %s", e)
        return jsonify({"error": "Erro ao gerar o relatório unificado"}), 500
