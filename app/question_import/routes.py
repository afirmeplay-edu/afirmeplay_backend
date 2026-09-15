# -*- coding: utf-8 -*-
"""
Rotas do módulo de importação de questões via DOCX.

Mantém os paths públicos já usados pelo frontend:
  GET  /questions/import/template
  POST /questions/import/docx
  POST /test/import-docx
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required

from app import db
from app.decorators import requires_city_context
from app.decorators.role_required import get_current_user_from_token, role_required
from app.question_import.docx_template import build_questions_import_template
from app.question_import.importer import (
    import_questions_from_docx,
    parse_indexes_from_request,
    validate_import_defaults,
)
from app.question_import.test_docx_import import (
    TestDocxImportError,
    create_test_with_docx,
    parse_indexes_arg,
    parse_test_fields_from_form,
)

bp = Blueprint("question_import", __name__)
logger = logging.getLogger(__name__)

_IMPORT_ROLES = ("admin", "professor", "coordenador", "diretor", "tecadm")


@bp.route("/questions/import/template", methods=["GET"])
@jwt_required()
@role_required(*_IMPORT_ROLES)
def download_questions_import_template():
    """
    Baixa o template DOCX pré-preenchido com série e lista de disciplinas.

    Query params:
      - grade (obrigatório): UUID da série
      - subjectIds (recomendado): id1,id2,... disciplinas do arquivo
      - subjectId (opcional): atalho para 1 disciplina (também entra na lista)
    """
    try:
        subject_ids_raw = request.args.get("subjectIds") or request.args.get("subjects")
        listed = request.args.getlist("subjectId") or request.args.getlist("subjectIds")
        if listed and not subject_ids_raw:
            subject_ids_raw = ",".join(listed)

        defaults = {
            "grade": (request.args.get("grade") or request.args.get("gradeId") or "").strip(),
            "subjectId": (request.args.get("subjectId") or "").strip() if len(listed) <= 1 else "",
            "subjectIds": subject_ids_raw or ",".join(listed),
        }
        if len(listed) > 1:
            defaults["subjectId"] = ""
            defaults["subjectIds"] = ",".join(listed)

        context = validate_import_defaults(defaults)
        buffer = build_questions_import_template(context)

        safe_grade = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in (context["gradeName"] or "serie")
        )[:40]
        n_subj = len(context.get("subjects") or [])
        download_name = f"template_questoes_{safe_grade}_{n_subj}disc.docx"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("Error generating questions import template: %s", e, exc_info=True)
        return jsonify({"error": "Erro ao gerar template", "details": str(e)}), 500


@bp.route("/questions/import/docx", methods=["POST"])
@jwt_required()
@role_required(*_IMPORT_ROLES)
def import_questions_docx():
    """
    Importa questões de múltipla escolha a partir de um DOCX.

    multipart/form-data:
      - file (obrigatório): .docx
      - grade (obrigatório): UUID da série
      - subjectIds (opcional): lista permitida id1,id2
      - subjectId (opcional): default se a questão não trouxer SubjectId no DOCX
      - commit (opcional): "true" | "false"
      - indexes (opcional no commit): "1,3,5"

    Disciplina e dificuldade vêm por questão no arquivo.
    """
    try:
        if "file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado. Use o campo 'file'."}), 400

        file = request.files["file"]
        if not file or not file.filename:
            return jsonify({"error": "Nenhum arquivo selecionado"}), 400

        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"error": "User not authenticated"}), 401

        commit_raw = request.form.get("commit") or request.args.get("commit") or "false"
        commit = str(commit_raw).strip().lower() in ("1", "true", "yes", "sim")

        defaults = {}
        for key in ("subjectId", "grade", "gradeId", "subjectIds"):
            value = request.form.get(key)
            if value not in (None, ""):
                defaults[key] = value.strip()

        listed = request.form.getlist("subjectIds") or request.form.getlist("subjectIds[]")
        if listed:
            defaults["subjectIds"] = ",".join(v.strip() for v in listed if v and v.strip())

        indexes = parse_indexes_from_request(request.form, request.args)
        if indexes is not None and not commit:
            indexes = None

        result = import_questions_from_docx(
            file,
            current_user=current_user,
            commit=commit,
            defaults=defaults,
            indexes=indexes,
        )

        status = 201 if commit and result.get("summary", {}).get("created", 0) > 0 else 200
        if (
            commit
            and result.get("summary", {}).get("created", 0) == 0
            and result.get("summary", {}).get("total", 0) > 0
        ):
            status = 400
        return jsonify(result), status

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error("Error importing questions from DOCX: %s", e, exc_info=True)
        return jsonify({"error": "Erro ao importar questões", "details": str(e)}), 500


@bp.route("/test/import-docx", methods=["POST"])
@jwt_required()
@role_required(*_IMPORT_ROLES)
@requires_city_context
def criar_avaliacao_com_docx():
    """
    Cria avaliação online (virtual) + questões do DOCX de forma atômica.

    multipart/form-data:
      - file (obrigatório): .docx
      - indexes (recomendado): "1,3,5"
      - grade (obrigatório para as questões)
      - subjectIds (recomendado no SIMULADO): id1,id2 — disciplinas permitidas
      - subjectId (opcional): default se a questão não trouxer SubjectId no DOCX
      - Campos da avaliação: title, type (AVALIACAO|SIMULADO), model, course, created_by, ...
      - evaluation_mode: apenas virtual

    Disciplina por questão no DOCX (SubjectId). Preview: POST /questions/import/docx.
    """
    try:
        if "file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado. Use o campo 'file'."}), 400

        file = request.files["file"]
        if not file or not file.filename:
            return jsonify({"error": "Nenhum arquivo selecionado"}), 400

        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"error": "User not authenticated"}), 401

        test_data = parse_test_fields_from_form(request.form)
        if not test_data.get("created_by"):
            test_data["created_by"] = current_user.get("user_id") or current_user.get("id")

        question_defaults = {}
        for key in ("subjectId", "grade", "gradeId", "subjectIds"):
            value = request.form.get(key)
            if value not in (None, ""):
                question_defaults[key] = value.strip()

        listed = request.form.getlist("subjectIds") or request.form.getlist("subjectIds[]")
        if listed:
            question_defaults["subjectIds"] = ",".join(
                v.strip() for v in listed if v and v.strip()
            )

        if not question_defaults.get("grade") and not question_defaults.get("gradeId"):
            g = test_data.get("grade") or test_data.get("grade_id")
            if g:
                question_defaults["grade"] = str(g).strip()

        if not question_defaults.get("subjectId") and test_data.get("subject"):
            question_defaults["subjectId"] = str(test_data["subject"]).strip()

        indexes = parse_indexes_arg(request.form, request.args)

        result = create_test_with_docx(
            file,
            current_user=current_user,
            test_data=test_data,
            question_defaults=question_defaults,
            indexes=indexes,
        )
        return jsonify(result), 201

    except TestDocxImportError as e:
        db.session.rollback()
        body = {"error": e.message, **(e.payload or {})}
        return jsonify(body), 400
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error("Error creating test from DOCX: %s", e, exc_info=True)
        return jsonify({"error": "Erro ao criar avaliação com DOCX", "details": str(e)}), 500
