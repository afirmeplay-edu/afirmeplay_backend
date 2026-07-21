# -*- coding: utf-8 -*-
"""
Rotas da avaliação subjetiva: CRUD da estrutura (SubjectiveTest/SubjectiveQuestion),
correção manual (rubrica SIM/PARCIAL/NAO/BRANCO) e dashboard de resultados.

Diferente da avaliação online, a prova em si é física/impressa e fica fora do sistema:
o sistema só guarda a estrutura (quantidade de questões e, por questão, uma habilidade
digitada livremente). Não há resposta online do aluno: o professor (ou role com
privilégio) aplica a prova e lança o resultado manualmente, célula por célula
(aluno x questão). O dashboard agrega essa rubrica (distribuição + SAEB simplificado).
"""
import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.decorators import requires_city_context
from app.decorators.role_required import role_required, get_current_user_from_token
from app.models.subjectiveTest import SubjectiveTest
from app.models.studentClass import Class
from app.models.school import School
from app.permissions.utils import get_teacher_classes
from app.services.subjective_evaluation_service import SubjectiveEvaluationService
from app.models.subjectiveResult import RUBRIC_VALUES
from app.utils.response_formatters import format_subjective_test_response
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list, uuid_list_to_str

bp = Blueprint('subjective_tests', __name__, url_prefix='/subjective-tests')


def _user_can_access_class(user, class_id) -> bool:
    """Professor só acessa turmas em que leciona; demais perfis liberados (escopo já filtrado por município)."""
    if user.get('role') != 'professor':
        return True
    teacher_class_ids = get_teacher_classes(user['id']) or []
    return class_id in ensure_uuid_list(teacher_class_ids)


def _user_can_edit(user, subjective_test: SubjectiveTest) -> bool:
    """Professor só edita/exclui avaliações que ele mesmo criou; demais perfis liberados."""
    if user.get('role') != 'professor':
        return True
    return subjective_test.created_by == user.get('id')


def _validate_scope_fields(data: dict):
    """
    Valida escolas/turmas informadas (mesmo padrão de POST/PUT /test) e, se turmas
    específicas forem informadas, deriva as escolas a partir delas.
    Retorna (data_normalizado, None) ou (None, (response, status)) se inválido.
    """
    if data.get('schools'):
        school_ids = data['schools'] if isinstance(data['schools'], list) else [data['schools']]
        existing_schools = School.query.filter(School.id.in_(school_ids)).all()
        if len(existing_schools) != len(school_ids):
            return None, (jsonify({"error": "Uma ou mais escolas não foram encontradas"}), 400)

    if data.get('classes'):
        raw_classes = data['classes'] if isinstance(data['classes'], list) else [data['classes']]
        class_ids = [c.get('id') if isinstance(c, dict) else c for c in raw_classes]
        class_ids_uuids = ensure_uuid_list(class_ids)
        existing_classes = Class.query.filter(Class.id.in_(class_ids_uuids)).all()
        if len(existing_classes) != len(class_ids_uuids):
            return None, (jsonify({"error": "Uma ou mais turmas não foram encontradas"}), 400)

        school_ids_from_classes = list({c.school_id for c in existing_classes})
        data['schools'] = uuid_list_to_str(school_ids_from_classes) if school_ids_from_classes else []
        data['classes'] = uuid_list_to_str(class_ids_uuids)

    return data, None


def _validate_questions(questions):
    if questions is None:
        return None
    if not isinstance(questions, list):
        return "questions deve ser uma lista"
    for q in questions:
        if not isinstance(q, dict) or not (q.get('skill_description') or q.get('skillDescription')):
            return "Cada questão deve ter 'skill_description' (habilidade)"
    return None


@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def create_subjective_test():
    """
    Cria uma avaliação subjetiva.
    Body: { title, subject_id, grade_id, description?, test_type?, application_date?,
             municipalities?, schools?, classes?, questions?: [{number, code, skill_description}] }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Corpo JSON obrigatório"}), 400

        required_fields = ['title']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Campo obrigatório ausente: {field}"}), 400

        if not (data.get('subject_id') or data.get('subject')):
            return jsonify({"error": "Campo obrigatório ausente: subject_id"}), 400
        if not (data.get('grade_id') or data.get('grade')):
            return jsonify({"error": "Campo obrigatório ausente: grade_id"}), 400

        questions_error = _validate_questions(data.get('questions'))
        if questions_error:
            return jsonify({"error": questions_error}), 400

        data, err = _validate_scope_fields(data)
        if err:
            return err

        subjective_test = SubjectiveEvaluationService.create_subjective_test(data, created_by=user.get('id'))
        return jsonify(format_subjective_test_response(subjective_test)), 201
    except Exception as e:
        db.session.rollback()
        logging.error("Erro ao criar avaliação subjetiva: %s", str(e), exc_info=True)
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def list_subjective_tests():
    """Lista avaliações subjetivas (escopo já filtrado por município via schema do tenant)."""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)

        query = SubjectiveTest.query.order_by(SubjectiveTest.created_at.desc())
        if user.get('role') == 'professor':
            query = query.filter(SubjectiveTest.created_by == user.get('id'))

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            "items": [format_subjective_test_response(t) for t in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages,
        }), 200
    except Exception as e:
        logging.error("Erro ao listar avaliações subjetivas: %s", str(e), exc_info=True)
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/opcoes-filtros', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_subjective_filter_options():
    """
    Opções hierárquicas de filtros da avaliação subjetiva.

    Hierarquia: Estado → Município → Escola → Série → Avaliação → Turma
    (diferente de /evaluation-results/opcoes-filtros, onde avaliação vem antes da escola).

    Só retorna avaliações que já têm correção lançada.
    Diretor/coordenador: inclui escola_pre_selecionada e estreita o recorte por ela.

    Query params (todos opcionais, cascata):
      - estado, municipio, escola, serie, avaliacao
      Valores 'all' / 'todas' / omitidos = todos daquele nível.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        result = SubjectiveEvaluationService.get_filter_options(
            user=user,
            estado=request.args.get('estado'),
            municipio=request.args.get('municipio'),
            escola=request.args.get('escola'),
            serie=request.args.get('serie'),
            avaliacao=request.args.get('avaliacao'),
        )
        if result.get("error"):
            status = result.pop("status", 400)
            # Mantém níveis já montados (estados/municipios) junto com o erro.
            return jsonify(result), status

        return jsonify(result), 200
    except Exception as e:
        logging.error("Erro ao obter opções de filtros subjetivos: %s", str(e), exc_info=True)
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:subjective_test_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def get_subjective_test(subjective_test_id):
    try:
        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        return jsonify(format_subjective_test_response(subjective_test)), 200
    except Exception as e:
        logging.error(
            "Erro ao buscar avaliação subjetiva %s: %s", subjective_test_id, str(e), exc_info=True
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:subjective_test_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def update_subjective_test(subjective_test_id):
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        if not _user_can_edit(user, subjective_test):
            return jsonify({"error": "Você só pode editar avaliações que criou"}), 403

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Corpo JSON obrigatório"}), 400

        questions_error = _validate_questions(data.get('questions'))
        if questions_error:
            return jsonify({"error": questions_error}), 400

        data, err = _validate_scope_fields(data)
        if err:
            return err

        subjective_test = SubjectiveEvaluationService.update_subjective_test(subjective_test, data)
        return jsonify(format_subjective_test_response(subjective_test)), 200
    except Exception as e:
        db.session.rollback()
        logging.error(
            "Erro ao atualizar avaliação subjetiva %s: %s", subjective_test_id, str(e), exc_info=True
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:subjective_test_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def delete_subjective_test(subjective_test_id):
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        if not _user_can_edit(user, subjective_test):
            return jsonify({"error": "Você só pode excluir avaliações que criou"}), 403

        SubjectiveEvaluationService.delete_subjective_test(subjective_test)
        return jsonify({"message": "Avaliação subjetiva excluída com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(
            "Erro ao excluir avaliação subjetiva %s: %s", subjective_test_id, str(e), exc_info=True
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


# ----------------------------------------------------------------------
# Dashboard de resultados
# ----------------------------------------------------------------------

@bp.route('/<string:subjective_test_id>/dashboard', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def get_subjective_dashboard(subjective_test_id):
    """
    Painel de resultados da avaliação subjetiva (distribuição da rubrica + SAEB simplificado).

    Query params:
      - class_id (opcional): filtra por uma turma; sem ele, agrega todas as turmas do escopo.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        class_id_param = request.args.get('class_id')
        class_uuid = None
        if class_id_param:
            class_uuid = ensure_uuid(class_id_param)
            if not class_uuid:
                return jsonify({"error": "ID de turma inválido"}), 400
            if not Class.query.get(class_uuid):
                return jsonify({"error": "Turma não encontrada"}), 404
            if not _user_can_access_class(user, class_uuid):
                return jsonify({"error": "Acesso negado a esta turma"}), 403

        allowed_class_ids = None
        if user.get('role') == 'professor':
            allowed_class_ids = ensure_uuid_list(get_teacher_classes(user['id']) or [])

        dashboard = SubjectiveEvaluationService.get_dashboard(
            subjective_test_id=subjective_test_id,
            class_id=class_uuid,
            allowed_class_ids=allowed_class_ids,
        )
        if dashboard is None:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        if dashboard.get("error") == "class_out_of_scope":
            return jsonify({"error": "Turma fora do escopo desta avaliação ou sem permissão"}), 403

        return jsonify(dashboard), 200
    except Exception as e:
        logging.error(
            "Erro ao buscar dashboard da avaliação subjetiva %s: %s",
            subjective_test_id, str(e), exc_info=True,
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


# ----------------------------------------------------------------------
# Correção manual
# ----------------------------------------------------------------------

@bp.route('/<string:subjective_test_id>/turmas/<string:class_id>/correcao', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def get_correction_matrix(subjective_test_id, class_id):
    """Matriz aluno x questão (valores lançados + presença) para correção de uma turma."""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        class_uuid = ensure_uuid(class_id)
        if not class_uuid:
            return jsonify({"error": "ID de turma inválido"}), 400

        class_obj = Class.query.get(class_uuid)
        if not class_obj:
            return jsonify({"error": "Turma não encontrada"}), 404

        if not _user_can_access_class(user, class_uuid):
            return jsonify({"error": "Acesso negado a esta turma"}), 403

        matrix = SubjectiveEvaluationService.get_correction_matrix(subjective_test_id, class_uuid)
        if matrix is None:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        matrix["class"] = {"id": class_obj.id, "name": class_obj.name}
        return jsonify(matrix), 200
    except Exception as e:
        logging.error(
            "Erro ao buscar matriz de correção avaliacao=%s turma=%s: %s",
            subjective_test_id, class_id, str(e), exc_info=True,
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:subjective_test_id>/alunos/<string:student_id>/resultado', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def preview_student_result(subjective_test_id, student_id):
    """
    Preview do resultado de um aluno a partir da rubrica já lançada.
    Mesma fórmula do finalize (EvaluationCalculator), mas NÃO grava EvaluationResult
    nem marca relatórios dirty — para atualizar a coluna da matriz a cada célula.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        from app.models.student import Student
        student = Student.query.get(student_id)
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404
        if student.class_id and not _user_can_access_class(user, student.class_id):
            return jsonify({"error": "Acesso negado a este aluno"}), 403

        result = SubjectiveEvaluationService.preview_student_result(subjective_test_id, student_id)
        if result is None:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        return jsonify(result), 200
    except Exception as e:
        logging.error(
            "Erro ao preview resultado aluno=%s avaliacao=%s: %s",
            student_id, subjective_test_id, str(e), exc_info=True,
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:subjective_test_id>/correcao', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def upsert_correction(subjective_test_id):
    """
    Lança/atualiza a rubrica de uma célula (aluno x questão).
    Body: { subjective_question_id, student_id, value: 'SIM'|'PARCIAL'|'NAO'|'BRANCO'|null }
    value=None ou repetir o valor já lançado remove o lançamento.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Corpo JSON obrigatório"}), 400

        subjective_question_id = data.get('subjective_question_id') or data.get('question_id')
        student_id = data.get('student_id')
        value = data.get('value')

        if not subjective_question_id or not student_id:
            return jsonify({"error": "subjective_question_id e student_id são obrigatórios"}), 400

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
            subjective_test_id=subjective_test_id,
            subjective_question_id=subjective_question_id,
            student_id=student_id,
            value=value,
            corrected_by=user.get('id'),
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(
            "Erro ao lançar correção avaliacao=%s: %s", subjective_test_id, str(e), exc_info=True
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:subjective_test_id>/presenca', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def upsert_presence(subjective_test_id):
    """
    Lança/atualiza a presença de um aluno na avaliação.
    Body: { student_id, present: bool }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

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
            subjective_test_id=subjective_test_id,
            student_id=student_id,
            present=bool(present),
            updated_by=user.get('id'),
        )
        return jsonify(result), 200
    except Exception as e:
        logging.error(
            "Erro ao lançar presença avaliacao=%s: %s", subjective_test_id, str(e), exc_info=True
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500


@bp.route('/<string:subjective_test_id>/turmas/<string:class_id>/finalizar', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def finalize_class_correction(subjective_test_id, class_id):
    """
    Calcula e grava (EvaluationResult) o resultado de todos os alunos da turma,
    a partir da rubrica já lançada. Pode ser chamado novamente para recalcular
    após novos lançamentos (idempotente por aluno).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401

        subjective_test = SubjectiveTest.query.get(subjective_test_id)
        if not subjective_test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        class_uuid = ensure_uuid(class_id)
        if not class_uuid:
            return jsonify({"error": "ID de turma inválido"}), 400

        class_obj = Class.query.get(class_uuid)
        if not class_obj:
            return jsonify({"error": "Turma não encontrada"}), 404

        if not _user_can_access_class(user, class_uuid):
            return jsonify({"error": "Acesso negado a esta turma"}), 403

        summary = SubjectiveEvaluationService.finalize_class(
            subjective_test_id=subjective_test_id, class_id=class_uuid, corrected_by=user.get('id')
        )
        return jsonify(summary), 200
    except Exception as e:
        logging.error(
            "Erro ao finalizar correção avaliacao=%s turma=%s: %s",
            subjective_test_id, class_id, str(e), exc_info=True,
        )
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500
