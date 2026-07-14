# -*- coding: utf-8 -*-
"""
Rotas de correção manual da avaliação subjetiva (Test.evaluation_mode == 'subjective').

Não há resposta online do aluno nesse fluxo: o professor aplica a prova
(impressa/presencial) e lança o resultado manualmente, célula por célula
(aluno x questão), usando a rubrica SIM / PARCIAL / NAO / BRANCO.
"""
import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.decorators import requires_city_context
from app.decorators.role_required import role_required, get_current_user_from_token
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.studentClass import Class
from app.permissions.utils import get_teacher_classes
from app.services.subjective_evaluation_service import SubjectiveEvaluationService
from app.models.subjectiveResult import RUBRIC_VALUES

bp = Blueprint('subjective_tests', __name__, url_prefix='/subjective-tests')


def _user_can_access_class(user, class_id) -> bool:
    """Professor só acessa turmas em que leciona; demais perfis liberados (escopo já filtrado por município)."""
    if user.get('role') != 'professor':
        return True
    teacher_class_ids = get_teacher_classes(user['id']) or []
    from app.utils.uuid_helpers import ensure_uuid_list
    return class_id in ensure_uuid_list(teacher_class_ids)


def _validate_subjective_test(test_id):
    """Retorna (test, None) ou (None, (response, status)) se inválido."""
    test = Test.query.get(test_id)
    if not test:
        return None, (jsonify({"error": "Avaliação não encontrada"}), 404)
    if test.evaluation_mode != 'subjective':
        return None, (jsonify({"error": "Esta avaliação não é do tipo subjetiva"}), 400)
    return test, None


@bp.route('/<string:test_id>/turmas/<string:class_id>/correcao', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def get_correction_matrix(test_id, class_id):
    """Matriz aluno x questão (valores lançados + presença) para correção de uma turma."""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        test, err = _validate_subjective_test(test_id)
        if err:
            return err

        from app.utils.uuid_helpers import ensure_uuid
        class_uuid = ensure_uuid(class_id)
        if not class_uuid:
            return jsonify({"error": "ID de turma inválido"}), 400

        class_obj = Class.query.get(class_uuid)
        if not class_obj:
            return jsonify({"error": "Turma não encontrada"}), 404

        if not _user_can_access_class(user, class_uuid):
            return jsonify({"error": "Acesso negado a esta turma"}), 403

        matrix = SubjectiveEvaluationService.get_correction_matrix(test_id, class_uuid)
        if matrix is None:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        matrix["class"] = {"id": class_obj.id, "name": class_obj.name}
        return jsonify(matrix), 200
    except Exception as e:
        logging.error("Erro ao buscar matriz de correção test=%s class=%s: %s", test_id, class_id, str(e), exc_info=True)
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:test_id>/correcao', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def upsert_correction(test_id):
    """
    Lança/atualiza a rubrica de uma célula (aluno x questão).
    Body: { question_id, student_id, value: 'SIM'|'PARCIAL'|'NAO'|'BRANCO'|null }
    value=None ou repetir o valor já lançado remove o lançamento.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        test, err = _validate_subjective_test(test_id)
        if err:
            return err

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Corpo JSON obrigatório"}), 400

        question_id = data.get('question_id')
        student_id = data.get('student_id')
        value = data.get('value')

        if not question_id or not student_id:
            return jsonify({"error": "question_id e student_id são obrigatórios"}), 400

        if value is not None and value not in RUBRIC_VALUES:
            return jsonify({
                "error": f"value inválido: {value}. Aceitos: {', '.join(RUBRIC_VALUES)} ou null"
            }), 400

        from app.models.student import Student
        student = Student.query.get(student_id)
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404
        if student.class_id and not _user_can_access_class(user, student.class_id):
            return jsonify({"error": "Acesso negado a este aluno"}), 403

        result = SubjectiveEvaluationService.upsert_rubric_value(
            test_id=test_id,
            question_id=question_id,
            student_id=student_id,
            value=value,
            corrected_by=user.get('id'),
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error("Erro ao lançar correção test=%s: %s", test_id, str(e), exc_info=True)
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:test_id>/presenca', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def upsert_presence(test_id):
    """
    Lança/atualiza a presença de um aluno na avaliação.
    Body: { student_id, present: bool }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        test, err = _validate_subjective_test(test_id)
        if err:
            return err

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Corpo JSON obrigatório"}), 400

        student_id = data.get('student_id')
        present = data.get('present')
        if not student_id or present is None:
            return jsonify({"error": "student_id e present são obrigatórios"}), 400

        from app.models.student import Student
        student = Student.query.get(student_id)
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404
        if student.class_id and not _user_can_access_class(user, student.class_id):
            return jsonify({"error": "Acesso negado a este aluno"}), 403

        result = SubjectiveEvaluationService.set_presence(
            test_id=test_id,
            student_id=student_id,
            present=bool(present),
            updated_by=user.get('id'),
        )
        return jsonify(result), 200
    except Exception as e:
        logging.error("Erro ao lançar presença test=%s: %s", test_id, str(e), exc_info=True)
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:test_id>/turmas/<string:class_id>/finalizar', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def finalize_class_correction(test_id, class_id):
    """
    Calcula e grava (EvaluationResult) o resultado de todos os alunos da turma,
    a partir da rubrica já lançada. Pode ser chamado novamente para recalcular
    após novos lançamentos (idempotente por aluno).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        test, err = _validate_subjective_test(test_id)
        if err:
            return err

        from app.utils.uuid_helpers import ensure_uuid
        class_uuid = ensure_uuid(class_id)
        if not class_uuid:
            return jsonify({"error": "ID de turma inválido"}), 400

        class_obj = Class.query.get(class_uuid)
        if not class_obj:
            return jsonify({"error": "Turma não encontrada"}), 404

        if not _user_can_access_class(user, class_uuid):
            return jsonify({"error": "Acesso negado a esta turma"}), 403

        # Garante que a turma está registrada como aplicada (ClassTest), sem sobrescrever datas existentes.
        class_test = ClassTest.query.filter_by(test_id=test_id, class_id=class_uuid).first()
        if not class_test:
            logging.warning(
                "Finalizando correção subjetiva sem ClassTest configurado: test=%s class=%s",
                test_id, class_id,
            )

        summary = SubjectiveEvaluationService.finalize_class(
            test_id=test_id, class_id=class_uuid, corrected_by=user.get('id')
        )
        return jsonify(summary), 200
    except Exception as e:
        logging.error(
            "Erro ao finalizar correção test=%s class=%s: %s", test_id, class_id, str(e), exc_info=True
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500
