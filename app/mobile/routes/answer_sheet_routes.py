# -*- coding: utf-8 -*-
"""
Rotas mobile para entrada manual de cartões resposta.
Permite que professores marquem respostas no app sem usar imagem/câmera.
"""
from flask import request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models.user import User, RoleEnum
from app.mobile.routes.blueprint import mobile_bp
from app.mobile.services.device_service import is_valid_uuid_v4
from app.answer_sheets.services.cartao_resposta.manual_answer_sheet_service import (
    ManualAnswerSheetError,
    get_manual_entry_form,
    list_students_for_gabarito,
    submit_manual_correction,
)
from app.utils.tenant_middleware import get_current_tenant_context

import logging

logger = logging.getLogger(__name__)

_ALLOWED = frozenset(
    {
        RoleEnum.ADMIN,
        RoleEnum.COORDENADOR,
        RoleEnum.DIRETOR,
        RoleEnum.TECADM,
        RoleEnum.APLICADOR,
        RoleEnum.PROFESSOR,
    }
)


def _require_device_header():
    device_id = request.headers.get("X-Device-Id")
    if not device_id or not is_valid_uuid_v4(device_id):
        return None, (jsonify({"error": "X-Device-Id obrigatório (UUID v4)"}), 400)
    return device_id, None


def _require_allowed_user():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    if not user or user.role not in _ALLOWED:
        return None, (jsonify({"error": "Operação não autorizada"}), 403)
    
    # Converter para dict para compatibilidade com manual_answer_sheet_service
    user_dict = {
        "id": str(user.id),
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "name": user.name,
        "email": user.email,
    }
    return user_dict, None


@mobile_bp.route("/answer-sheets/gabaritos/<string:gabarito_id>/students", methods=["GET", "OPTIONS"])
@jwt_required(optional=True)
def mobile_list_gabarito_students(gabarito_id):
    """
    Lista alunos de um gabarito para entrada manual.
    
    Query params (opcionais):
        - class_id: filtrar por turma
        - grade_id: filtrar por série
        - school_id: filtrar por escola
        - flat: true para lista plana (sem agrupar por turma)
    """
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    ctx = get_current_tenant_context()
    if not ctx or not ctx.city_id:
        return jsonify({"error": "Contexto de município obrigatório"}), 400

    try:
        flat_raw = (request.args.get("flat") or "").strip().lower()
        flat = flat_raw in ("1", "true", "yes")

        payload = list_students_for_gabarito(
            gabarito_id=gabarito_id,
            user=user,
            city_id=str(ctx.city_id),
            class_id=request.args.get("class_id"),
            grade_id=request.args.get("grade_id"),
            school_id=request.args.get("school_id"),
            flat=flat,
        )
        return jsonify(payload), 200
    except ManualAnswerSheetError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Erro ao listar alunos do gabarito {gabarito_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao listar alunos"}), 500


@mobile_bp.route("/answer-sheets/manual-entry/form", methods=["GET", "OPTIONS"])
@jwt_required(optional=True)
def mobile_get_manual_entry_form():
    """
    Retorna formulário de entrada manual para um aluno.
    
    Query params:
        - gabarito_id (ou test_id): identificador do gabarito
        - student_id: ID do aluno
    
    Returns:
        Estrutura do gabarito com questões, alternativas e respostas já salvas
    """
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    student_id = (request.args.get("student_id") or "").strip()
    if not student_id:
        return jsonify({"error": "student_id é obrigatório"}), 400

    try:
        payload = get_manual_entry_form(
            gabarito_id=request.args.get("gabarito_id"),
            test_id=request.args.get("test_id"),
            student_id=student_id,
            user=user,
        )
        return jsonify(payload), 200
    except ManualAnswerSheetError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Erro ao carregar formulário manual: {e}", exc_info=True)
        return jsonify({"error": "Erro ao carregar formulário"}), 500


@mobile_bp.route("/answer-sheets/manual-entry/submit", methods=["POST", "OPTIONS"])
@jwt_required(optional=True)
def mobile_submit_manual_entry():
    """
    Registra respostas marcadas manualmente no app.
    
    Body:
        {
            "gabarito_id": "uuid" (ou "test_id"),
            "student_id": "uuid",
            "answers": {
                "1": "A",
                "2": "B",
                "3": null,  // em branco
                "4": "INVALID"
            },
            "device_id": "uuid",
            "offline_submission_id": "uuid"  // opcional, para controle offline
        }
    
    Returns:
        Resultado da correção com nota, proficiência, etc.
    """
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    
    student_id = (body.get("student_id") or "").strip()
    if not student_id:
        return jsonify({"error": "student_id é obrigatório"}), 400

    raw_answers = body.get("answers")
    if raw_answers is None:
        return jsonify({"error": "Campo 'answers' é obrigatório"}), 400

    # Validar device_id no corpo corresponde ao header
    body_device = body.get("device_id")
    if body_device and str(body_device) != str(device_id):
        return jsonify({"error": "device_id no corpo deve coincidir com X-Device-Id"}), 400

    ctx = getattr(g, "tenant_context", None)
    schema = getattr(ctx, "schema", None) if ctx else None
    
    logger.info(
        f"[mobile/answer-sheets/manual-entry] POST — user_id={user['id']} "
        f"device_id={device_id} student_id={student_id} "
        f"gabarito_id={body.get('gabarito_id')} schema={schema!r}"
    )

    try:
        result = submit_manual_correction(
            gabarito_id=body.get("gabarito_id"),
            test_id=body.get("test_id"),
            student_id=student_id,
            raw_answers=raw_answers,
            user=user,
        )
        
        # Adicionar metadados mobile
        result["device_id"] = device_id
        result["offline_submission_id"] = body.get("offline_submission_id")
        
        db.session.commit()
        
        logger.info(
            f"[mobile/answer-sheets/manual-entry] 200 — student_id={student_id} "
            f"gabarito_id={body.get('gabarito_id')} correct={result.get('correct')}/{result.get('total')}"
        )
        
        return jsonify(result), 200
    except ManualAnswerSheetError as e:
        db.session.rollback()
        logger.warning(f"[mobile/answer-sheets/manual-entry] {e.status_code} — {e.message}")
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        db.session.rollback()
        logger.error(f"[mobile/answer-sheets/manual-entry] 500 — {type(e).__name__}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao registrar respostas"}), 500


@mobile_bp.route("/answer-sheets/manual-entry/batch", methods=["POST", "OPTIONS"])
@jwt_required(optional=True)
def mobile_submit_manual_batch():
    """
    Registra múltiplas respostas de cartões em lote (sincronização offline).
    
    Body:
        {
            "submissions": [
                {
                    "offline_submission_id": "uuid-local",
                    "gabarito_id": "uuid",
                    "student_id": "uuid",
                    "answers": {...},
                    "device_id": "uuid"
                },
                ...
            ]
        }
    
    Returns:
        {
            "results": [
                {
                    "offline_submission_id": "...",
                    "status": "applied" | "error",
                    "message": "...",
                    "data": {...}  // resultado da correção se success
                }
            ]
        }
    """
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    submissions = body.get("submissions")
    if not isinstance(submissions, list):
        return jsonify({"error": "submissions deve ser uma lista"}), 400

    # Validar device_id
    for item in submissions:
        item.setdefault("device_id", device_id)
        if item.get("device_id") != device_id:
            return jsonify({"error": "device_id no corpo deve coincidir com X-Device-Id"}), 400

    ctx = getattr(g, "tenant_context", None)
    schema = getattr(ctx, "schema", None) if ctx else None
    
    logger.info(
        f"[mobile/answer-sheets/batch] POST — user_id={user['id']} "
        f"device_id={device_id} submissions={len(submissions)} schema={schema!r}"
    )

    results = []
    applied_count = 0
    error_count = 0

    for item in submissions:
        offline_id = item.get("offline_submission_id", "unknown")
        try:
            student_id = (item.get("student_id") or "").strip()
            if not student_id:
                raise ValueError("student_id é obrigatório")

            raw_answers = item.get("answers")
            if raw_answers is None:
                raise ValueError("Campo 'answers' é obrigatório")

            result = submit_manual_correction(
                gabarito_id=item.get("gabarito_id"),
                test_id=item.get("test_id"),
                student_id=student_id,
                raw_answers=raw_answers,
                user=user,
            )
            
            results.append({
                "offline_submission_id": offline_id,
                "status": "applied",
                "message": "Respostas registradas com sucesso",
                "data": result,
            })
            applied_count += 1
        except ManualAnswerSheetError as e:
            results.append({
                "offline_submission_id": offline_id,
                "status": "error",
                "code": f"manual_error_{e.status_code}",
                "message": e.message,
            })
            error_count += 1
        except Exception as e:
            results.append({
                "offline_submission_id": offline_id,
                "status": "error",
                "code": "internal_error",
                "message": str(e),
            })
            error_count += 1
            logger.error(f"Erro em submission {offline_id}: {e}", exc_info=True)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao commitar lote: {e}", exc_info=True)
        return jsonify({"error": "Erro ao salvar lote de respostas"}), 500

    logger.info(
        f"[mobile/answer-sheets/batch] 200 — applied={applied_count} errors={error_count} total={len(submissions)}"
    )

    return jsonify({"results": results}), 200
