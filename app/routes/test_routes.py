from flask import Blueprint, request, jsonify, abort
from app.models.test import Test
from app.models.question import Question
from app.models.classTest import ClassTest
from app.models.studentClass import Class
from app.models.school import School
from app.models.grades import Grade
from app.models.student import Student
from app.models.schoolTeacher import SchoolTeacher
from app.models.teacher import Teacher
from app import db
from app.utils.auth import get_current_tenant_id
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime, timedelta
import logging
from app.utils.response_formatters import format_test_response
from sqlalchemy.orm import joinedload, subqueryload

bp = Blueprint('tests', __name__, url_prefix="/test")



@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"error": "Database error occurred", "details": str(error)}), 500

@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error(f"Integrity error: {str(error)}")
    return jsonify({"error": "Data integrity error", "details": str(error)}), 400

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"error": "An unexpected error occurred", "details": str(error)}), 500

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def criar_avaliacao():
    try:
        data = request.get_json()
        logging.info(f"Recebendo requisição POST para criar avaliação: {data}")
        
        if not data:
            logging.error("Nenhum dado fornecido na requisição")
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['title', 'type', 'model', 'course', 'created_by']
        for field in required_fields:
            if field not in data:
                logging.error(f"Campo obrigatório ausente: {field}")
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Validação específica para cada tipo de avaliação
        if data['type'] == 'SIMULADO':
            if not data.get('subjects_info'):
                logging.error("Informações de disciplinas ausentes para tipo SIMULADO")
                return jsonify({"error": "Subjects information is required for SIMULADO type"}), 400
        elif data['type'] == 'AVALIACAO':
            # Para AVALIACAO, pode ter subject (disciplina única) ou subjects (múltiplas disciplinas)
            has_subject = data.get('subject')
            has_subjects = data.get('subjects') and isinstance(data.get('subjects'), list) and len(data.get('subjects')) > 0
            
            if not has_subject and not has_subjects:
                logging.error("Disciplina ou disciplinas ausentes para tipo AVALIACAO")
                return jsonify({"error": "Subject or subjects array is required for AVALIACAO type"}), 400

        # Validação de escola se fornecida
        if data.get('schools'):
            if isinstance(data['schools'], list):
                school_ids = data['schools']
            else:
                school_ids = [data['schools']]
            
            # Verificar se todas as escolas existem
            existing_schools = School.query.filter(School.id.in_(school_ids)).all()
            if len(existing_schools) != len(school_ids):
                return jsonify({"error": "Uma ou mais escolas não foram encontradas"}), 400

        logging.info("Criando nova avaliação com os dados fornecidos")
        print(data)
        nova_avaliacao = Test(
            title=data.get('title'),
            description=data.get('description'),
            type=data.get('type'),
            subject=data.get('subject') if data.get('subject') else None,
            grade_id=data.get('grade') or data.get('grade_id'),  # Aceita tanto 'grade' quanto 'grade_id'
            intructions=data.get('intructions'),
            max_score=data.get('max_score'),
            time_limit=datetime.fromisoformat(data.get('time_limit')) if data.get('time_limit') else None,
            end_time=datetime.fromisoformat(data.get('end_time')) if data.get('end_time') else None,
            evaluation_mode=data.get('evaluation_mode', 'virtual'),
            created_by=data.get('created_by'),
            municipalities=data.get('municipalities'),
            schools=data.get('schools'),
            course=data.get('course'),
            model=data.get('model'),
            subjects_info=data.get('subjects') or data.get('subjects_info'),  # Aceita tanto 'subjects' quanto 'subjects_info'
            status='pendente'  # Sempre inicia como pendente, passa para agendada quando for aplicada
        )

        # Adiciona questões se fornecidas
        if 'questions' in data and isinstance(data['questions'], list):
            for question_data in data['questions']:
                # Se um ID for fornecido, buscar questão existente
                if 'id' in question_data and question_data['id']:
                    existing_question = Question.query.get(question_data['id'])
                    if existing_question:
                        # Associar questão existente à avaliação
                        nova_avaliacao.questions.append(existing_question)
                        logging.info(f"Questão existente {existing_question.id} associada à avaliação")
                    else:
                        logging.warning(f"Questão com ID {question_data['id']} não encontrada")
                else:
                    # Criar nova questão apenas se não houver ID
                    # Extrai o ID do grade se for um objeto
                    grade_level = question_data.get('grade')
                    if isinstance(grade_level, dict) and 'id' in grade_level:
                        grade_level = grade_level['id']
                    
                    question = Question(
                        number=question_data.get('number'),
                        text=question_data.get('text'),
                        formatted_text=question_data.get('formattedText'),
                        subject_id=question_data.get('subjectId') or question_data.get('subject_id'),
                        title=question_data.get('title'),
                        description=question_data.get('description'),
                        command=question_data.get('command'),
                        subtitle=question_data.get('subtitle'),
                        alternatives=question_data.get('options'),
                        skill=question_data.get('skills'),
                        grade_level=grade_level,
                        difficulty_level=question_data.get('difficulty'),
                        correct_answer=question_data.get('solution'),
                        formatted_solution=question_data.get('formattedSolution'),
                        question_type=question_data.get('type'),
                        value=question_data.get('value'),
                        topics=question_data.get('topics'),
                        created_by=question_data.get('created_by') or data.get('created_by')
                    )
                    db.session.add(question)
                    nova_avaliacao.questions.append(question)
                    logging.info(f"Nova questão criada e associada à avaliação")

        db.session.add(nova_avaliacao)
        db.session.commit()

        return jsonify({
            "message": "Test created successfully",
            "id": nova_avaliacao.id
        }), 201

    except ValueError as e:
        return jsonify({"error": "Invalid date format", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating test: {str(e)}", exc_info=True)
        return jsonify({"error": "Error creating test", "details": str(e)}), 500

@bp.route('/', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_avaliacoes():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401

        query = Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade),
            subqueryload(Test.questions).options(
                joinedload(Question.subject),
                joinedload(Question.grade),
                joinedload(Question.education_stage),
                joinedload(Question.creator),
                joinedload(Question.last_modifier)
            )
        )

        # Se o usuário for professor, filtra para ver apenas os seus testes
        if user['role'] == 'professor':
            query = query.filter(Test.created_by == user['id'])

        # Filtro por status se fornecido
        status_filter = request.args.get('status')
        if status_filter:
            query = query.filter(Test.status == status_filter)

        avaliacoes = query.all()
        
        return jsonify([format_test_response(a) for a in avaliacoes]), 200

    except Exception as e:
        logging.error(f"Error listing tests: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing tests", "details": str(e)}), 500

@bp.route('/user/<string:user_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_avaliacoes_por_usuario(user_id):
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        if user_id == 'me':
            user_id = user['id']

        query = Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade),
            subqueryload(Test.questions).options(
                joinedload(Question.subject),
                joinedload(Question.grade),
                joinedload(Question.education_stage),
                joinedload(Question.creator),
                joinedload(Question.last_modifier)
            )
        ).filter(Test.created_by == user_id)
        
        avaliacoes = query.all()
        
        if not avaliacoes:
            return jsonify({"message": "Nenhuma avaliação encontrada para este usuário"}), 404

        return jsonify([format_test_response(a) for a in avaliacoes]), 200

    except Exception as e:
        logging.error(f"Erro ao listar avaliações do usuário: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar avaliações do usuário", "details": str(e)}), 500

@bp.route('/school/<string:school_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_avaliacoes_por_escola(school_id):
    """Lista todas as avaliações agendadas para uma escola específica."""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401

        # Verificar se a escola existe
        school = School.query.get(school_id)
        if not school:
            return jsonify({"error": "School not found"}), 404

        # Verificar permissões do usuário
        if user['role'] == 'professor':
            # Professor só pode ver avaliações de escolas onde está alocado
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Teacher not found"}), 404
            
            teacher_school = SchoolTeacher.query.filter_by(
                teacher_id=teacher.id,
                school_id=school_id
            ).first()
            if not teacher_school:
                return jsonify({"error": "You don't have permission to view tests for this school"}), 403

        # Buscar avaliações que incluem esta escola
        query = Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade),
            subqueryload(Test.questions).options(
                joinedload(Question.subject),
                joinedload(Question.grade),
                joinedload(Question.education_stage),
                joinedload(Question.creator),
                joinedload(Question.last_modifier)
            )
        ).filter(
            Test.status == 'agendada'
        )

        # Filtrar por escola (pode estar em schools como lista ou string)
        avaliacoes = []
        all_tests = query.all()
        
        for test in all_tests:
            if test.schools:
                if isinstance(test.schools, list):
                    if school_id in test.schools:
                        avaliacoes.append(test)
                elif isinstance(test.schools, str):
                    if test.schools == school_id:
                        avaliacoes.append(test)

        return jsonify([format_test_response(a) for a in avaliacoes]), 200

    except Exception as e:
        logging.error(f"Error listing tests by school: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing tests by school", "details": str(e)}), 500

# @bp.route('/student/<string:student_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
def listar_avaliacoes_por_aluno(student_id):
    """Lista todas as avaliações agendadas para um aluno específico."""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401

        # Se o usuário for aluno, só pode ver suas próprias avaliações
        if user['role'] == 'aluno':
            if user['id'] != student_id:
                return jsonify({"error": "You can only view your own tests"}), 403

        # Verificar se o aluno existe
        # Se o student_id for igual ao user_id atual, buscar por user_id
        if student_id == user['id']:
            student = Student.query.filter_by(user_id=user['id']).first()
        else:
            student = Student.query.get(student_id)
        
        if not student:
            return jsonify({"error": "Student not found"}), 404

        # Verificar permissões do usuário
        if user['role'] == 'professor':
            # Professor só pode ver alunos da escola onde está alocado
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Teacher not found"}), 404
            
            teacher_school = SchoolTeacher.query.filter_by(
                teacher_id=teacher.id,
                school_id=student.school_id
            ).first()
            if not teacher_school:
                return jsonify({"error": "You don't have permission to view tests for this student"}), 403

        # Buscar avaliações que incluem a escola do aluno
        query = Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade),
            subqueryload(Test.questions).options(
                joinedload(Question.subject),
                joinedload(Question.grade),
                joinedload(Question.education_stage),
                joinedload(Question.creator),
                joinedload(Question.last_modifier)
            )
        ).filter(
            Test.status == 'agendada'
        )

        # Filtrar por escola do aluno
        avaliacoes = []
        all_tests = query.all()
        
        for test in all_tests:
            if test.schools:
                if isinstance(test.schools, list):
                    if student.school_id in test.schools:
                        avaliacoes.append(test)
                elif isinstance(test.schools, str):
                    if test.schools == student.school_id:
                        avaliacoes.append(test)

        return jsonify([format_test_response(a) for a in avaliacoes]), 200

    except Exception as e:
        logging.error(f"Error listing tests by student: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing tests by student", "details": str(e)}), 500

@bp.route('/<string:test_id>/status', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def atualizar_status_avaliacao(test_id):
    """Atualiza o status de uma avaliação."""
    try:
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({"error": "Status field is required"}), 400

        # Validar status permitidos
        status_permitidos = ['agendada', 'em_andamento', 'concluida', 'cancelada']
        if data['status'] not in status_permitidos:
            return jsonify({"error": f"Invalid status. Allowed values: {', '.join(status_permitidos)}"}), 400

        # Verificar permissões do usuário
        user = get_current_user_from_token()
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "You can only update tests you created"}), 403

        test.status = data['status']
        db.session.commit()

        return jsonify({
            "message": "Test status updated successfully",
            "id": test.id,
            "status": test.status
        }), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating test status: {str(e)}", exc_info=True)
        return jsonify({"error": "Error updating test status", "details": str(e)}), 500

@bp.route('/<string:test_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
def obter_avaliacao(test_id):
    try:
        test = Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade),
            subqueryload(Test.questions).options(
                joinedload(Question.subject),
                joinedload(Question.grade),
                joinedload(Question.education_stage),
                joinedload(Question.creator),
                joinedload(Question.last_modifier)
            )
        ).get(test_id)
        
        if not test:
            return jsonify({"error": "Test not found"}), 404

        return jsonify(format_test_response(test)), 200

    except Exception as e:
        logging.error(f"Error getting test: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting test", "details": str(e)}), 500

@bp.route('/<string:test_id>/details', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
def get_test_details(test_id):
    """
    Alias para /test/<test_id> - Detalhes completos da avaliação
    """
    return obter_avaliacao(test_id)

@bp.route('/<string:test_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def atualizar_avaliacao(test_id):
    try:
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validação específica para cada tipo de avaliação se o tipo estiver sendo atualizado
        if 'type' in data:
            if data['type'] == 'SIMULADO':
                if not data.get('subjects_info'):
                    logging.error("Informações de disciplinas ausentes para tipo SIMULADO")
                    return jsonify({"error": "Subjects information is required for SIMULADO type"}), 400
            elif data['type'] == 'AVALIACAO':
                # Para AVALIACAO, pode ter subject (disciplina única) ou subjects (múltiplas disciplinas)
                has_subject = data.get('subject')
                has_subjects = data.get('subjects') and isinstance(data.get('subjects'), list) and len(data.get('subjects')) > 0
                
                if not has_subject and not has_subjects:
                    logging.error("Disciplina ou disciplinas ausentes para tipo AVALIACAO")
                    return jsonify({"error": "Subject or subjects array is required for AVALIACAO type"}), 400

        # Campos que podem ser atualizados
        campos = [
            'title', 'description', 'type', 'subject', 'grade_id',
            'max_score', 'time_limit', 'end_time', 'evaluation_mode', 'intructions', 'municipalities',
            'schools', 'course', 'model', 'subjects_info'
        ]

        for campo in campos:
            if campo in data:
                if campo in ['time_limit', 'end_time'] and data[campo]:
                    setattr(test, campo, datetime.fromisoformat(data[campo]))
                elif campo == 'grade_id':
                    # Aceita tanto 'grade' quanto 'grade_id'
                    setattr(test, campo, data.get('grade') or data.get('grade_id'))
                elif campo == 'subjects_info':
                    # Aceita tanto 'subjects' quanto 'subjects_info'
                    setattr(test, campo, data.get('subjects') or data.get('subjects_info'))
                else:
                    setattr(test, campo, data[campo])

        db.session.commit()
        return jsonify({'message': 'Test updated successfully'}), 200

    except ValueError as e:
        return jsonify({"error": "Invalid date format", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating test: {str(e)}", exc_info=True)
        return jsonify({"error": "Error updating test", "details": str(e)}), 500

@bp.route('', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def bulk_delete_tests():
    """ Rota para deletar múltiplos testes em massa. """
    try:
        data = request.get_json()
        if not data or 'ids' not in data or not isinstance(data['ids'], list):
            return jsonify({"error": "A list of 'ids' is required in the request body"}), 400

        test_ids = data['ids']
        if not test_ids:
            return jsonify({"message": "No test IDs provided to delete"}), 200

        tests_to_delete = Test.query.filter(Test.id.in_(test_ids)).all()

        if not tests_to_delete:
            return jsonify({"error": "None of the provided test IDs were found"}), 404

        for test in tests_to_delete:
            db.session.delete(test)
        
        db.session.commit()

        return jsonify({'message': f'{len(tests_to_delete)} tests deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error bulk deleting tests: {str(e)}", exc_info=True)
        return jsonify({"error": "Error bulk deleting tests", "details": str(e)}), 500

@bp.route('/<string:test_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def deletar_avaliacao(test_id):
    try:
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        db.session.delete(test)
        db.session.commit()
        return jsonify({'message': 'Test deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting test: {str(e)}", exc_info=True)
        return jsonify({"error": "Error deleting test", "details": str(e)}), 500

@bp.route('/<string:test_id>/apply', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def aplicar_avaliacao_classe(test_id):
    """Aplica uma avaliação a uma ou múltiplas classes."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Verificar se a avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        # Validar campos obrigatórios
        if 'classes' not in data or not isinstance(data['classes'], list):
            return jsonify({"error": "Classes list is required"}), 400

        if not data['classes']:
            return jsonify({"error": "At least one class must be provided"}), 400

        applied_classes = []
        errors = []

        for class_data in data['classes']:
            class_id = class_data.get('class_id')
            application = class_data.get('application')
            expiration = class_data.get('expiration')

            if not class_id:
                errors.append("class_id is required for each class")
                continue

            # Verificar se já existe uma aplicação para esta classe e avaliação
            existing_application = ClassTest.query.filter_by(
                class_id=class_id,
                test_id=test_id
            ).first()

            if existing_application:
                errors.append(f"Test is already applied to class {class_id}")
                continue

            # Criar nova aplicação
            try:
                class_test = ClassTest(
                    class_id=class_id,
                    test_id=test_id,
                    application=datetime.fromisoformat(application) if application else None,
                    expiration=datetime.fromisoformat(expiration) if expiration else None
                )
                db.session.add(class_test)
                applied_classes.append(class_id)
            except ValueError as e:
                errors.append(f"Invalid date format for class {class_id}: {str(e)}")

        if applied_classes:
            db.session.commit()
            
            response = {
                "message": f"Test applied to {len(applied_classes)} classes successfully",
                "applied_classes": applied_classes
            }
            
            if errors:
                response["warnings"] = errors
                
            return jsonify(response), 201
        else:
            return jsonify({"error": "No classes were applied", "details": errors}), 400

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error applying test to classes: {str(e)}", exc_info=True)
        return jsonify({"error": "Error applying test to classes", "details": str(e)}), 500

@bp.route('/<string:test_id>/classes', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_classes_avaliacao(test_id):
    """Lista todas as classes onde uma avaliação foi aplicada."""
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        # Buscar todas as aplicações da avaliação
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
        classes_info = []
        for ct in class_tests:
            # Buscar informações da classe
            class_obj = Class.query.get(ct.class_id)
            if class_obj:
                school_obj = School.query.get(class_obj.school_id)
                grade_obj = Grade.query.get(class_obj.grade_id)
                
                classes_info.append({
                    "class_test_id": ct.id,
                    "class": {
                        "id": class_obj.id,
                        "name": class_obj.name,
                        "school": {
                            "id": school_obj.id,
                            "name": school_obj.name
                        } if school_obj else None,
                        "grade": {
                            "id": grade_obj.id,
                            "name": grade_obj.name
                        } if grade_obj else None
                    },
                    "application": ct.application.isoformat() if ct.application else None,
                    "expiration": ct.expiration.isoformat() if ct.expiration else None
                })

        return jsonify(classes_info), 200

    except Exception as e:
        logging.error(f"Error listing classes for test: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing classes for test", "details": str(e)}), 500

@bp.route('/<string:test_id>/classes/<string:class_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def remover_aplicacao_avaliacao(test_id, class_id):
    """Remove a aplicação de uma avaliação de uma classe específica."""
    try:
        # Verificar se a aplicação existe
        class_test = ClassTest.query.filter_by(
            test_id=test_id,
            class_id=class_id
        ).first()

        if not class_test:
            return jsonify({"error": "Test application to class not found"}), 404

        db.session.delete(class_test)
        db.session.commit()

        return jsonify({"message": "Test application removed successfully"}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error removing test application: {str(e)}", exc_info=True)
        return jsonify({"error": "Error removing test application", "details": str(e)}), 500

@bp.route('/class/<string:class_id>/tests/complete', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
def obter_avaliacoes_completas_classe(class_id):
    """Obtém todas as avaliações aplicadas a uma determinada classe, incluindo todas as questões."""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401

        # Verificar se a classe existe
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404

        # Verificar permissões específicas
        if user['role'] == 'aluno':
            # Aluno só pode ver avaliações da sua própria classe
            student = Student.query.filter_by(user_id=user['id']).first()
            if not student or student.class_id != class_id:
                return jsonify({"error": "You can only access tests from your own class"}), 403
        elif user['role'] == 'professor':
            # Professor só pode ver avaliações de classes onde está alocado
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Teacher not found"}), 404
            
            teacher_school = SchoolTeacher.query.filter_by(
                teacher_id=teacher.id,
                school_id=class_obj.school_id
            ).first()
            if not teacher_school:
                return jsonify({"error": "You don't have permission to view tests for this class"}), 403

        # Buscar todas as avaliações aplicadas nesta classe na tabela class_test
        class_tests = ClassTest.query.filter_by(class_id=class_id).all()
        
        if not class_tests:
            return jsonify({
                "message": "No tests found for this class",
                "class": {
                    "id": class_obj.id,
                    "name": class_obj.name
                },
                "total_tests": 0,
                "tests": []
            }), 200

        # Buscar informações da escola e série
        school_obj = School.query.get(class_obj.school_id)
        grade_obj = Grade.query.get(class_obj.grade_id)

        # Buscar todas as avaliações com seus dados completos
        test_ids = [ct.test_id for ct in class_tests]
        tests = Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade),
            subqueryload(Test.questions).options(
                joinedload(Question.subject),
                joinedload(Question.grade),
                joinedload(Question.education_stage),
                joinedload(Question.creator),
                joinedload(Question.last_modifier)
            )
        ).filter(Test.id.in_(test_ids)).all()

        # Criar um dicionário para mapear test_id -> ClassTest
        class_test_map = {ct.test_id: ct for ct in class_tests}

        # Preparar lista de avaliações completas
        tests_complete = []
        current_time = datetime.utcnow()
        
        for test in tests:
            class_test = class_test_map.get(test.id)
            
            # Verificar se está dentro do período de aplicação
            is_available = False
            availability_status = "not_available"
            
            if test.status == 'agendada' or test.status == 'em_andamento':
                if class_test.application and current_time >= class_test.application:
                    if not class_test.expiration or current_time <= class_test.expiration:
                        is_available = True
                        availability_status = "available"
                    else:
                        availability_status = "expired"
                elif class_test.application and current_time < class_test.application:
                    availability_status = "not_yet_available"
                else:
                    is_available = True
                    availability_status = "available"

            # Preparar questões para envio (sem respostas corretas para alunos)
            questions_for_students = []
            for question in test.questions:
                question_data = {
                    "id": question.id,
                    "number": question.number,
                    "text": question.text,
                    "formatted_text": question.formatted_text,
                    "title": question.title,
                    "description": question.description,
                    "command": question.command,
                    "subtitle": question.subtitle,
                    "alternatives": question.alternatives,
                    "question_type": question.question_type,
                    "value": question.value,
                    "topics": question.topics,
                    "subject": {
                        "id": question.subject.id,
                        "name": question.subject.name
                    } if question.subject else None,
                    "grade": {
                        "id": question.grade.id,
                        "name": question.grade.name
                    } if question.grade else None,
                    "education_stage": {
                        "id": question.education_stage.id,
                        "name": question.education_stage.name
                    } if question.education_stage else None
                }
                questions_for_students.append(question_data)

            # Preparar avaliação completa
            test_complete = {
                "test": {
                    "id": test.id,
                    "title": test.title,
                    "description": test.description,
                    "type": test.type,
                    "subject": {
                        "id": test.subject_rel.id,
                        "name": test.subject_rel.name
                    } if test.subject_rel else None,
                    "grade": {
                        "id": test.grade.id,
                        "name": test.grade.name
                    } if test.grade else None,
                    "intructions": test.intructions,
                    "max_score": test.max_score,
                    "time_limit": test.time_limit.isoformat() if test.time_limit else None,
                    "course": test.course,
                    "model": test.model,
                    "subjects_info": test.subjects_info,
                    "status": test.status,
                    "created_by": test.created_by,
                    "creator": {
                        "id": test.creator.id,
                        "name": test.creator.name,
                        "email": test.creator.email
                    } if test.creator else None
                },
                "class_test_info": {
                    "class_test_id": class_test.id,
                    "application": class_test.application.isoformat() if class_test.application else None,
                    "expiration": class_test.expiration.isoformat() if class_test.expiration else None,
                    "status": class_test.status
                },
                "availability": {
                    "is_available": is_available,
                    "status": availability_status,
                    "current_time": current_time.isoformat()
                },
                "questions": questions_for_students,
                "total_questions": len(questions_for_students),
                "total_value": sum(q.get('value', 0) for q in questions_for_students if q.get('value'))
            }
            
            tests_complete.append(test_complete)

        # Ordenar por data de aplicação (mais recente primeiro)
        tests_complete.sort(key=lambda x: x['class_test_info']['application'] or '', reverse=True)

        # Preparar resposta completa
        response = {
            "class": {
                "id": class_obj.id,
                "name": class_obj.name,
                "school": {
                    "id": school_obj.id,
                    "name": school_obj.name
                } if school_obj else None,
                "grade": {
                    "id": grade_obj.id,
                    "name": grade_obj.name
                } if grade_obj else None
            },
            "total_tests": len(tests_complete),
            "tests": tests_complete
        }

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error getting complete tests for class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting complete tests for class", "details": str(e)}), 500

@bp.route('/class/<string:class_id>/tests', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_avaliacoes_por_classe(class_id):
    """Lista todas as avaliações aplicadas em uma determinada classe."""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401

        # Verificar se a classe existe
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404

        # Verificar permissões do usuário
        if user['role'] == 'professor':
            # Professor só pode ver avaliações de classes onde está alocado
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Teacher not found"}), 404
            
            teacher_school = SchoolTeacher.query.filter_by(
                teacher_id=teacher.id,
                school_id=class_obj.school_id
            ).first()
            if not teacher_school:
                return jsonify({"error": "You don't have permission to view tests for this class"}), 403

        # Buscar todas as aplicações de avaliações nesta classe
        class_tests = ClassTest.query.filter_by(class_id=class_id).all()
        
        if not class_tests:
            return jsonify({
                "message": "No tests found for this class",
                "class": {
                    "id": class_obj.id,
                    "name": class_obj.name
                },
                "total_tests": 0,
                "tests": []
            }), 200

        # Buscar informações da escola e série
        school_obj = School.query.get(class_obj.school_id)
        grade_obj = Grade.query.get(class_obj.grade_id)

        # Buscar todas as avaliações aplicadas
        test_ids = [ct.test_id for ct in class_tests]
        tests = Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade),
            subqueryload(Test.questions)
        ).filter(Test.id.in_(test_ids)).all()

        # Criar um dicionário para mapear test_id -> ClassTest
        class_test_map = {ct.test_id: ct for ct in class_tests}

        # Preparar lista de avaliações com informações detalhadas
        tests_info = []
        for test in tests:
            class_test = class_test_map.get(test.id)
            
            test_info = {
                "test_id": test.id,
                "title": test.title,
                "description": test.description,
                "type": test.type,
                "subject": {
                    "id": test.subject_rel.id,
                    "name": test.subject_rel.name
                } if test.subject_rel else None,
                "grade": {
                    "id": test.grade.id,
                    "name": test.grade.name
                } if test.grade else None,
                "intructions": test.intructions,
                "max_score": test.max_score,
                "time_limit": test.time_limit.isoformat() if test.time_limit else None,
                "course": test.course,
                "model": test.model,
                "subjects_info": test.subjects_info,
                "status": test.status,
                "created_by": test.created_by,
                "creator": {
                    "id": test.creator.id,
                    "name": test.creator.name,
                    "email": test.creator.email
                } if test.creator else None,
                "total_questions": len(test.questions),
                "application_info": {
                    "class_test_id": class_test.id,
                    "application": class_test.application.isoformat() if class_test.application else None,
                    "expiration": class_test.expiration.isoformat() if class_test.expiration else None
                }
            }
            tests_info.append(test_info)

        # Ordenar por data de aplicação (mais recente primeiro)
        tests_info.sort(key=lambda x: x['application_info']['application'] or '', reverse=True)

        # Preparar resposta
        response = {
            "class": {
                "id": class_obj.id,
                "name": class_obj.name,
                "school": {
                    "id": school_obj.id,
                    "name": school_obj.name
                } if school_obj else None,
                "grade": {
                    "id": grade_obj.id,
                    "name": grade_obj.name
                } if grade_obj else None
            },
            "total_tests": len(tests_info),
            "tests": tests_info
        }

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error listing tests by class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing tests by class", "details": str(e)}), 500

@bp.route('/my-class/tests', methods=['GET'])
@jwt_required()
@role_required("aluno")
def listar_avaliacoes_minha_classe():
    """Lista todas as avaliações aplicadas na classe do aluno autenticado."""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401

        # Buscar o aluno pelo user_id
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"error": "Student not found"}), 404

        # Verificar se o aluno está matriculado em uma classe
        if not student.class_id:
            return jsonify({
                "message": "Student is not enrolled in any class",
                "student": {
                    "id": student.id,
                    "name": student.name
                },
                "total_tests": 0,
                "tests": []
            }), 200

        # Buscar a classe do aluno
        class_obj = Class.query.get(student.class_id)
        if not class_obj:
            return jsonify({"error": "Student's class not found"}), 404

        # Buscar todas as aplicações de avaliações nesta classe
        class_tests = ClassTest.query.filter_by(class_id=student.class_id).all()
        
        if not class_tests:
            return jsonify({
                "message": "No tests found for your class",
                "student": {
                    "id": student.id,
                    "name": student.name
                },
                "class": {
                    "id": class_obj.id,
                    "name": class_obj.name
                },
                "total_tests": 0,
                "tests": []
            }), 200

        # Buscar informações da escola e série
        school_obj = School.query.get(class_obj.school_id)
        grade_obj = Grade.query.get(class_obj.grade_id)

        # Buscar todas as avaliações aplicadas
        test_ids = [ct.test_id for ct in class_tests]
        tests = Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade),
            subqueryload(Test.questions)
        ).filter(Test.id.in_(test_ids)).all()

        # Criar um dicionário para mapear test_id -> ClassTest
        class_test_map = {ct.test_id: ct for ct in class_tests}

        # Preparar lista de avaliações com informações para o aluno
        tests_info = []
        current_time = datetime.utcnow()
        
        for test in tests:
            class_test = class_test_map.get(test.id)
            
            # Verificar se a avaliação está disponível para o aluno
            is_available = False
            availability_status = "not_available"
            
            if test.status == 'agendada' or test.status == 'em_andamento':
                if class_test.application and current_time >= class_test.application:
                    if not class_test.expiration or current_time <= class_test.expiration:
                        is_available = True
                        availability_status = "available"
                    else:
                        availability_status = "expired"
                elif class_test.application and current_time < class_test.application:
                    availability_status = "not_yet_available"
                else:
                    is_available = True
                    availability_status = "available"
            
            test_info = {
                "test_id": test.id,
                "title": test.title,
                "description": test.description,
                "type": test.type,
                "subject": {
                    "id": test.subject_rel.id,
                    "name": test.subject_rel.name
                } if test.subject_rel else None,
                "grade": {
                    "id": test.grade.id,
                    "name": test.grade.name
                } if test.grade else None,
                "intructions": test.intructions,
                "max_score": test.max_score,
                "time_limit": test.time_limit.isoformat() if test.time_limit else None,
                "course": test.course,
                "model": test.model,
                "subjects_info": test.subjects_info,
                "status": test.status,
                "creator": {
                    "id": test.creator.id,
                    "name": test.creator.name
                } if test.creator else None,
                "total_questions": len(test.questions),
                "application_info": {
                    "class_test_id": class_test.id,
                    "application": class_test.application.isoformat() if class_test.application else None,
                    "expiration": class_test.expiration.isoformat() if class_test.expiration else None,
                    "current_time": current_time.isoformat()
                },
                "availability": {
                    "is_available": is_available,
                    "status": availability_status
                }
            }
            tests_info.append(test_info)

        # Ordenar por data de aplicação (mais recente primeiro)
        tests_info.sort(key=lambda x: x['application_info']['application'] or '', reverse=True)

        # Preparar resposta
        response = {
            "student": {
                "id": student.id,
                "name": student.name,
                "user_id": student.user_id
            },
            "class": {
                "id": class_obj.id,
                "name": class_obj.name,
                "school": {
                    "id": school_obj.id,
                    "name": school_obj.name
                } if school_obj else None,
                "grade": {
                    "id": grade_obj.id,
                    "name": grade_obj.name
                } if grade_obj else None
            },
            "total_tests": len(tests_info),
            "tests": tests_info
        }

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error listing tests for student's class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error listing tests for student's class", "details": str(e)}), 500

@bp.route('/<string:test_id>/start-session', methods=['POST'])
@jwt_required()
@role_required("aluno")
def start_test_session(test_id):
    """
    Inicia uma nova sessão de teste para um aluno
    """
    try:
        from app.models.testSession import TestSession
        from app.models.student import Student
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        # Buscar aluno pelo user_id
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"error": "Dados do aluno não encontrados"}), 404
        
        # Verificar se o teste existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Teste não encontrado"}), 404
        
        # Verificar se já existe sessão ativa para este aluno/teste
        existing_session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id,
            status='em_andamento'
        ).first()
        
        if existing_session:
            return jsonify({
                "message": "Sessão já iniciada",
                "session_id": existing_session.id,
                "started_at": existing_session.started_at.isoformat(),
                "remaining_time_minutes": existing_session.remaining_time_minutes,
                "time_limit_minutes": existing_session.time_limit_minutes
            }), 200
        
        # Determinar tempo limite baseado no teste
        time_limit_minutes = None
        if test.time_limit:
            # Assumindo que time_limit é um timedelta ou datetime
            if hasattr(test.time_limit, 'total_seconds'):
                time_limit_minutes = int(test.time_limit.total_seconds() / 60)
            elif hasattr(test.time_limit, 'minute'):
                time_limit_minutes = test.time_limit.minute
        
        # Criar nova sessão
        session = TestSession(
            student_id=student.id,
            test_id=test_id,
            time_limit_minutes=time_limit_minutes,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            "message": "Sessão iniciada com sucesso",
            "session_id": session.id,
            "started_at": session.started_at.isoformat(),
            "time_limit_minutes": session.time_limit_minutes,
            "remaining_time_minutes": session.time_limit_minutes  # Tempo restante inicial = tempo limite
        }), 201
        
    except Exception as e:
        logging.error(f"Erro ao iniciar sessão do teste: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao iniciar sessão", "details": str(e)}), 500

@bp.route('/<string:test_id>/submit', methods=['POST'])
@jwt_required()
@role_required("aluno")
def submit_test_answers(test_id):
    """
    Submete as respostas de um teste
    
    Body:
    {
        "session_id": "uuid",
        "answers": [
            {
                "question_id": "uuid",
                "answer": "resposta_do_aluno"
            }
        ]
    }
    """
    try:
        from app.models.testSession import TestSession
        from app.models.student import Student
        from app.models.studentAnswer import StudentAnswer
        from datetime import datetime
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        # Buscar aluno pelo user_id
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"error": "Dados do aluno não encontrados"}), 404
        
        data = request.get_json()
        session_id = data.get('session_id')
        answers = data.get('answers', [])
        
        if not session_id:
            return jsonify({"error": "session_id é obrigatório"}), 400
        
        if not answers:
            return jsonify({"error": "Lista de respostas é obrigatória"}), 400
        
        # Buscar sessão
        session = TestSession.query.filter_by(
            id=session_id,
            test_id=test_id,
            student_id=student.id
        ).first()
        
        if not session:
            return jsonify({"error": "Sessão não encontrada"}), 404
        
        # Validar se sessão ainda está ativa
        if session.status != 'em_andamento':
            return jsonify({
                "error": f"Sessão não está ativa. Status atual: {session.status}"
            }), 400
        
        # Validar tempo limite
        if session.is_expired:
            session.status = 'expirada'
            db.session.commit()
            return jsonify({
                "error": "Tempo limite excedido. Sessão expirada."
            }), 410  # 410 Gone
        
        # Buscar questões do teste para validação e correção
        test_questions = Question.query.filter(
            Question.test_id == test_id
        ).all()
        
        # Se não há questões vinculadas diretamente ao teste, buscar pela relação many-to-many
        if not test_questions:
            test = Test.query.get(test_id)
            if test and test.questions:
                test_questions = test.questions
        
        questions_dict = {q.id: q for q in test_questions}
        
        correct_count = 0
        saved_answers = []
        
        # Processar cada resposta
        for ans_data in answers:
            question_id = ans_data.get('question_id')
            answer = ans_data.get('answer')
            
            if not question_id or answer is None:
                continue
            
            # Verificar se a questão existe e pertence ao teste
            if question_id not in questions_dict:
                logging.warning(f"Questão {question_id} não encontrada no teste {test_id}")
                continue
            
            # Verificar se já existe resposta para esta questão nesta sessão
            existing_answer = StudentAnswer.query.filter_by(
                student_id=student.id,
                test_id=test_id,
                question_id=question_id
            ).first()
            
            if existing_answer:
                # Atualizar resposta existente
                existing_answer.answer = str(answer)
                existing_answer.answered_at = datetime.utcnow()
                student_answer = existing_answer
            else:
                # Criar nova resposta
                student_answer = StudentAnswer(
                    student_id=student.id,
                    test_id=test_id,
                    question_id=question_id,
                    answer=str(answer)
                )
                db.session.add(student_answer)
            
            saved_answers.append({
                'question_id': question_id,
                'answer': str(answer),
                'answered_at': student_answer.answered_at.isoformat()
            })
            
            # Verificar se a resposta está correta (correção automática)
            question = questions_dict[question_id]
            if question.correct_answer and str(answer).strip().lower() == str(question.correct_answer).strip().lower():
                correct_count += 1
        
        # Finalizar sessão e calcular nota
        total_questions = len(test_questions)
        session.finalize_session(
            correct_answers=correct_count,
            total_questions=total_questions
        )
        
        db.session.commit()
        
        return jsonify({
            "message": "Respostas submetidas com sucesso",
            "session_id": session.id,
            "submitted_at": session.submitted_at.isoformat(),
            "duration_minutes": session.duration_minutes,
            "results": {
                "total_questions": session.total_questions,
                "correct_answers": session.correct_answers,
                "score_percentage": session.score,
                "grade": session.grade,
                "answers_saved": len(saved_answers)
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao submeter respostas do teste: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao submeter respostas", "details": str(e)}), 500