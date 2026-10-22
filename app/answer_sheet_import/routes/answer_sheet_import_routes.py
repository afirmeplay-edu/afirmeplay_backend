# -*- coding: utf-8 -*-
"""
Rotas de importação de cartão-resposta (pré-visualização).
"""
import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.answer_sheet_import.services import preview_from_file, preview_from_text
from app.decorators.role_required import role_required

bp = Blueprint('answer_sheet_import', __name__, url_prefix='/answer-sheets/import')
logger = logging.getLogger(__name__)


@bp.route('/preview', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def preview_answer_sheet_import():
    """
    Lê e valida um cartão-resposta para pré-visualização (não grava nada).

    multipart/form-data:
        file (obrigatório): .csv, .xlsx ou .xls
            Aba "Gabarito": Questão, Resposta, Disciplina (obrigatórias); Habilidade, Alternativas (opcionais)
            Aba "Dados" (opcional): Título, Secretaria, Séries
        grade_ids (opcional, repetível): séries do cartão, usadas para priorizar habilidades

    application/json:
        { "text": "<conteúdo colado do Excel>", "grade_ids": ["uuid", ...] }

    Returns:
        200: { rows, blocks, metadata, errors, warnings, summary }
        400: { error }
    """
    try:
        file = request.files.get('file')
        if file is not None:
            return jsonify(preview_from_file(file, request.form.getlist('grade_ids'))), 200

        data = request.get_json(silent=True) or {}
        return jsonify(preview_from_text(data.get('text'), data.get('grade_ids'))), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("Erro na pré-visualização de importação de cartão-resposta: %s", e, exc_info=True)
        return jsonify({"error": "Erro ao processar a importação do cartão-resposta"}), 500
