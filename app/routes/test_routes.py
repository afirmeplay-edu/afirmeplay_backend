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

def process_subjects_for_test(test):
    """
    Processa os subjects de um teste, retornando uma lista de subjects com nomes
    """
    from app.utils.response_formatters import _get_all_subjects_from_test
    return _get_all_subjects_from_test(test)



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

        # Validação do campo duration se fornecido
        if 'duration' in data and data['duration'] is not None:
            try:
                duration = int(data['duration'])
                if duration <= 0:
                    logging.error("Duração deve ser maior que zero")
                    return jsonify({"error": "Duration must be greater than zero"}), 400
            except (ValueError, TypeError):
                logging.error("Duração deve ser um número inteiro")
                return jsonify({"error": "Duration must be an integer"}), 400

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
        
        # Validação de turmas se fornecidas
        classes_to_apply = []
        if data.get('classes'):
            if isinstance(data['classes'], list):
                class_ids = [c.get('id') if isinstance(c, dict) else c for c in data['classes']]
            else:
                class_ids = [data['classes']]
            
            # Verificar se todas as turmas existem
            existing_classes = Class.query.filter(Class.id.in_(class_ids)).all()
            if len(existing_classes) != len(class_ids):
                return jsonify({"error": "Uma ou mais turmas não foram encontradas"}), 400
            
            classes_to_apply = class_ids
            
            # Se turmas foram especificadas, extrair as escolas das turmas
            school_ids_from_classes = list(set([c.school_id for c in existing_classes]))
            data['schools'] = school_ids_from_classes

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
            duration=data.get('duration'),  # Duração em minutos
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
        db.session.flush()  # Para obter o ID da avaliação antes do commit
        
        # Se turmas específicas foram fornecidas, criar registros em ClassTest
        if classes_to_apply:
            for class_id in classes_to_apply:
                class_test = ClassTest(
                    class_id=class_id,
                    test_id=nova_avaliacao.id,
                    status='pendente'  # Status inicial
                )
                db.session.add(class_test)
            logging.info(f"Criados registros ClassTest para {len(classes_to_apply)} turmas")

        db.session.commit()

        return jsonify({
            "message": "Test created successfully",
            "id": nova_avaliacao.id,
            "classes_applied": len(classes_to_apply) if classes_to_apply else 0
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

        # Parâmetros de paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        per_page = min(per_page, 100)  # Máximo 100 itens por página
        
        # Verificar se é uma requisição apenas para contagem
        only_count = request.args.get('only_count', 'false').lower() == 'true'
        
        # Otimizar consulta baseada no tipo de requisição
        if only_count:
            # Para contagem, não carregar relacionamentos
            query = Test.query
        else:
            # Para dados completos, carregar apenas relacionamentos essenciais
            query = Test.query.options(
                joinedload(Test.creator),
                joinedload(Test.subject_rel),
                joinedload(Test.grade)
                # Remover subqueryload de questions para melhor performance
            )

        # Se o usuário for professor, filtra para ver apenas os seus testes
        if user['role'] == 'professor':
            query = query.filter(Test.created_by == user['id'])

        # Filtros
        status_filter = request.args.get('status')
        if status_filter:
            query = query.filter(Test.status == status_filter)
            
        subject_filter = request.args.get('subject_id')
        if subject_filter:
            query = query.filter(Test.subject == subject_filter)
            
        type_filter = request.args.get('type')
        if type_filter:
            query = query.filter(Test.type == type_filter)
            
        model_filter = request.args.get('model')
        if model_filter:
            query = query.filter(Test.model == model_filter)
            
        grade_filter = request.args.get('grade_id')
        if grade_filter:
            query = query.filter(Test.grade_id == grade_filter)

        # Se é apenas contagem, retornar rapidamente
        if only_count:
            total = query.count()
            return jsonify({"total": total}), 200

        # Parâmetros de ordenação
        sort_by = request.args.get('sort', 'created_at')
        order = request.args.get('order', 'desc')
        
        # Aplicar ordenação
        if sort_by == 'created_at':
            if order.lower() == 'desc':
                query = query.order_by(Test.created_at.desc())
            else:
                query = query.order_by(Test.created_at.asc())
        elif sort_by == 'title':
            if order.lower() == 'desc':
                query = query.order_by(Test.title.desc())
            else:
                query = query.order_by(Test.title.asc())
        elif sort_by == 'status':
            if order.lower() == 'desc':
                query = query.order_by(Test.status.desc())
            else:
                query = query.order_by(Test.status.asc())
        else:
            # Padrão: ordenar por data de criação descendente
            query = query.order_by(Test.created_at.desc())

        # Aplicar paginação
        paginated_query = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        avaliacoes = paginated_query.items
        
        # Resposta com metadados de paginação
        response_data = {
            "data": [format_test_response(a) for a in avaliacoes],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": paginated_query.total,
                "pages": paginated_query.pages,
                "has_next": paginated_query.has_next,
                "has_prev": paginated_query.has_prev,
                "next_num": paginated_query.next_num,
                "prev_num": paginated_query.prev_num
            }
        }
        
        return jsonify(response_data), 200

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
            'max_score', 'time_limit', 'end_time', 'duration', 'evaluation_mode', 'intructions', 'municipalities',
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
        logging.info("🗑️ Tentativa de deletar avaliações em massa")
        
        # Verificar permissões do usuário
        user = get_current_user_from_token()
        if not user:
            logging.error("❌ Usuário não encontrado no token")
            return jsonify({"error": "User not found or token invalid"}), 401
        
        logging.info(f"👤 Usuário fazendo bulk delete: {user['email']} (role: {user['role']})")
        
        data = request.get_json()
        if not data or 'ids' not in data or not isinstance(data['ids'], list):
            logging.error("❌ Lista de IDs não fornecida ou inválida")
            return jsonify({"error": "A list of 'ids' is required in the request body"}), 400

        test_ids = data['ids']
        logging.info(f"📋 IDs recebidos para exclusão: {test_ids}")
        
        if not test_ids:
            logging.info("⚠️ Nenhum ID fornecido para exclusão")
            return jsonify({"message": "No test IDs provided to delete"}), 200

        tests_to_delete = Test.query.filter(Test.id.in_(test_ids)).all()
        logging.info(f"🔍 Avaliações encontradas no banco: {[t.id for t in tests_to_delete]}")

        if not tests_to_delete:
            logging.error("❌ Nenhuma das avaliações foi encontrada no banco")
            return jsonify({"error": "None of the provided test IDs were found"}), 404

        # Verificar permissões para cada avaliação
        permission_errors = []
        valid_tests = []
        
        for test in tests_to_delete:
            if user['role'] == 'professor' and test.created_by != user['id']:
                permission_errors.append(f"Test {test.id} (created by {test.created_by})")
            else:
                valid_tests.append(test)
        
        if permission_errors:
            logging.error(f"❌ Erros de permissão: {permission_errors}")
            return jsonify({
                "error": "You can only delete tests you created",
                "details": f"Permission denied for: {', '.join(permission_errors)}"
            }), 403

        logging.info(f"✅ Deletando {len(valid_tests)} avaliações...")
        
        # EXCLUIR REGISTROS RELACIONADOS PARA CADA TESTE
        from app.models.studentAnswer import StudentAnswer
        from app.models.testSession import TestSession
        from app.models.question import Question
        
        for test in valid_tests:
            logging.info(f"🗑️ Iniciando exclusão em cascata para teste: {test.id}")
            
            # 1. Excluir respostas dos alunos
            student_answers = StudentAnswer.query.filter_by(test_id=test.id).all()
            for answer in student_answers:
                db.session.delete(answer)
            logging.info(f"🗑️ Excluídas {len(student_answers)} respostas de alunos para teste {test.id}")
            
            # 2. Excluir sessões de teste
            test_sessions = TestSession.query.filter_by(test_id=test.id).all()
            for session in test_sessions:
                db.session.delete(session)
            logging.info(f"🗑️ Excluídas {len(test_sessions)} sessões de teste para teste {test.id}")
            
            # 3. Excluir aplicações de classe
            class_tests = ClassTest.query.filter_by(test_id=test.id).all()
            for class_test in class_tests:
                db.session.delete(class_test)
            logging.info(f"🗑️ Excluídas {len(class_tests)} aplicações de classe para teste {test.id}")
            
            # 4. Excluir questões associadas (se existirem)
            questions = Question.query.filter_by(test_id=test.id).all()
            for question in questions:
                # Se a questão foi criada especificamente para este teste, deletar
                # Se foi criada por outro usuário ou é reutilizada, apenas remover a associação
                if question.created_by == test.created_by:
                    db.session.delete(question)
                else:
                    # Apenas remover a associação com o teste
                    question.test_id = None
            logging.info(f"🗑️ Processadas {len(questions)} questões para teste {test.id}")
            
            # 5. Finalmente, excluir o teste
            db.session.delete(test)
            logging.info(f"🗑️ Teste {test.id} marcado para exclusão")
        
        db.session.commit()
        logging.info(f"🎉 {len(valid_tests)} avaliações deletadas com sucesso!")

        return jsonify({'message': f'{len(valid_tests)} tests deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"❌ Erro ao deletar avaliações em massa: {str(e)}", exc_info=True)
        return jsonify({"error": "Error bulk deleting tests", "details": str(e)}), 500

@bp.route('/<string:test_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def deletar_avaliacao(test_id):
    try:
        logging.info(f"🗑️ Tentativa de deletar avaliação: {test_id}")
        
        # Verificar permissões do usuário
        user = get_current_user_from_token()
        if not user:
            logging.error("❌ Usuário não encontrado no token")
            return jsonify({"error": "User not found or token invalid"}), 401
        
        logging.info(f"👤 Usuário fazendo delete: {user['email']} (role: {user['role']})")
        
        test = Test.query.get(test_id)
        if not test:
            logging.error(f"❌ Avaliação não encontrada: {test_id}")
            return jsonify({"error": "Test not found"}), 404

        logging.info(f"📋 Avaliação encontrada: {test.title} (criada por: {test.created_by})")
        
        # Verificar se o professor só pode deletar suas próprias avaliações
        if user['role'] == 'professor' and test.created_by != user['id']:
            logging.error(f"❌ Professor tentando deletar avaliação de outro usuário. User: {user['id']}, Creator: {test.created_by}")
            return jsonify({"error": "You can only delete tests you created"}), 403

        logging.info("✅ Permissões validadas, iniciando exclusão em cascata...")

        # EXCLUIR REGISTROS RELACIONADOS EM ORDEM CORRETA
        
        # 1. Excluir respostas dos alunos
        from app.models.studentAnswer import StudentAnswer
        student_answers = StudentAnswer.query.filter_by(test_id=test_id).all()
        for answer in student_answers:
            db.session.delete(answer)
        logging.info(f"🗑️ Excluídas {len(student_answers)} respostas de alunos")
        
        # 2. Excluir sessões de teste
        from app.models.testSession import TestSession
        test_sessions = TestSession.query.filter_by(test_id=test_id).all()
        for session in test_sessions:
            db.session.delete(session)
        logging.info(f"🗑️ Excluídas {len(test_sessions)} sessões de teste")
        
        # 3. Excluir aplicações de classe
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        for class_test in class_tests:
            db.session.delete(class_test)
        logging.info(f"🗑️ Excluídas {len(class_tests)} aplicações de classe")
        
        # 4. Tratar questões associadas
        from app.models.question import Question
        questions = Question.query.filter_by(test_id=test_id).all()
        for question in questions:
            # Se a questão foi criada especificamente para este teste, deletar
            # Se foi criada por outro usuário ou é reutilizada, apenas remover a associação
            if question.created_by == test.created_by:
                db.session.delete(question)
            else:
                # Apenas remover a associação com o teste
                question.test_id = None
        logging.info(f"🗑️ Processadas {len(questions)} questões")
        
        # 5. Finalmente, excluir o teste
        db.session.delete(test)
        logging.info("🗑️ Excluindo a avaliação principal...")
        
        # Commit de todas as operações
        db.session.commit()
        
        logging.info(f"🎉 Avaliação {test_id} e todos os registros relacionados deletados com sucesso!")
        return jsonify({'message': 'Test and all related records deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"❌ Erro ao deletar avaliação {test_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Error deleting test", "details": str(e)}), 500

@bp.route('/<string:test_id>/apply', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def aplicar_avaliacao_classe(test_id):
    """Aplica uma avaliação a uma ou múltiplas classes."""
    print(test_id)
    print(request.get_json())
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

            print(f"Existing application found: {existing_application is not None}")

            if existing_application:
                # Atualizar aplicação existente com novas datas
                try:
                    print(f"Updating existing application for class_id: {class_id}")
                    existing_application.application = datetime.fromisoformat(application) if application else None
                    existing_application.expiration = datetime.fromisoformat(expiration) if expiration else None
                    applied_classes.append(class_id)
                    print(f"Existing application updated successfully for class_id: {class_id}")
                except ValueError as e:
                    print(f"ValueError updating class {class_id}: {str(e)}")
                    errors.append(f"Invalid date format for class {class_id}: {str(e)}")
                except Exception as e:
                    print(f"Unexpected error updating class {class_id}: {str(e)}")
                    errors.append(f"Error updating application for class {class_id}: {str(e)}")
                continue

            # Criar nova aplicação
            try:
                print(f"Creating ClassTest with class_id: {class_id}, test_id: {test_id}")
                class_test = ClassTest(
                    class_id=class_id,
                    test_id=test_id,
                    application=datetime.fromisoformat(application) if application else None,
                    expiration=datetime.fromisoformat(expiration) if expiration else None
                )
                db.session.add(class_test)
                applied_classes.append(class_id)
                print(f"ClassTest created successfully for class_id: {class_id}")
            except ValueError as e:
                print(f"ValueError for class {class_id}: {str(e)}")
                errors.append(f"Invalid date format for class {class_id}: {str(e)}")
            except Exception as e:
                print(f"Unexpected error for class {class_id}: {str(e)}")
                errors.append(f"Error creating application for class {class_id}: {str(e)}")

        if applied_classes:
            # Atualizar o status da avaliação para "agendada" para permitir que alunos realizem
            test.status = 'agendada'
            
            db.session.commit()
            
            response = {
                "message": f"Test applied/updated to {len(applied_classes)} classes successfully",
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
    """Lista todas as classes onde uma avaliação foi aplicada ou está configurada para aplicação."""
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        # Buscar todas as aplicações da avaliação
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
        classes_info = []
        
        # Primeira prioridade: usar class_tests (quando a avaliação foi aplicada)
        if class_tests:
            for ct in class_tests:
                # Buscar informações da classe
                class_obj = Class.query.get(ct.class_id)
                if class_obj:
                    school_obj = School.query.get(class_obj.school_id)
                    grade_obj = Grade.query.get(class_obj.grade_id)
                    
                    # Contar alunos na turma
                    students_count = len(class_obj.students) if class_obj.students else 0
                    
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
                        "students_count": students_count,
                        "application": ct.application.isoformat() if ct.application else None,
                        "expiration": ct.expiration.isoformat() if ct.expiration else None,
                        "status": "applied"  # Indica que foi aplicada
                    })
        
        # Segunda prioridade: usar schools (quando a avaliação foi criada mas não aplicada)
        elif test.schools:
            logging.info(f"Nenhuma aplicação encontrada, buscando turmas do campo schools: {test.schools}")
            
            # Converter schools para lista se for string
            if isinstance(test.schools, str):
                import json
                try:
                    school_ids = json.loads(test.schools)
                    if not isinstance(school_ids, list):
                        school_ids = [school_ids]
                except:
                    school_ids = [test.schools]
            elif isinstance(test.schools, list):
                school_ids = test.schools
            else:
                school_ids = []
            
            logging.info(f"School IDs para buscar: {school_ids}")
            
            # Buscar todas as turmas das escolas especificadas
            if school_ids:
                all_classes = Class.query.filter(Class.school_id.in_(school_ids)).all()
                logging.info(f"Encontradas {len(all_classes)} turmas nas escolas")
                
                for class_obj in all_classes:
                    school_obj = School.query.get(class_obj.school_id)
                    grade_obj = Grade.query.get(class_obj.grade_id)
                    
                    # Contar alunos na turma
                    students_count = len(class_obj.students) if class_obj.students else 0
                    
                    classes_info.append({
                        "class_test_id": None,  # Não há registro em ClassTest ainda
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
                        "students_count": students_count,
                        "application": None,  # Não foi aplicada ainda
                        "expiration": None,   # Não foi aplicada ainda
                        "status": "configured"  # Indica que foi configurada mas não aplicada
                    })
        
        logging.info(f"Retornando {len(classes_info)} turmas para avaliação {test_id}")
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


@bp.route('/<string:test_id>/classes/remove', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def remover_aplicacoes_avaliacao_multiplas(test_id):
    """Remove a aplicação de uma avaliação de múltiplas classes."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validar campos obrigatórios
        if 'class_ids' not in data or not isinstance(data['class_ids'], list):
            return jsonify({"error": "class_ids list is required"}), 400

        if not data['class_ids']:
            return jsonify({"error": "At least one class_id must be provided"}), 400

        # Verificar se a avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Test not found"}), 404

        removed_classes = []
        not_found_classes = []
        errors = []

        for class_id in data['class_ids']:
            if not class_id:
                errors.append("class_id cannot be empty")
                continue

            # Verificar se a aplicação existe
            class_test = ClassTest.query.filter_by(
                test_id=test_id,
                class_id=class_id
            ).first()

            if not class_test:
                not_found_classes.append(class_id)
                continue

            try:
                db.session.delete(class_test)
                removed_classes.append(class_id)
            except Exception as e:
                errors.append(f"Error removing class {class_id}: {str(e)}")

        if removed_classes:
            db.session.commit()
            
            response = {
                "message": f"Test applications removed from {len(removed_classes)} classes successfully",
                "removed_classes": removed_classes
            }
            
            if not_found_classes:
                response["not_found_classes"] = not_found_classes
                
            if errors:
                response["warnings"] = errors
                
            return jsonify(response), 200
        else:
            return jsonify({
                "error": "No classes were removed", 
                "not_found_classes": not_found_classes,
                "details": errors
            }), 400

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error removing test applications: {str(e)}", exc_info=True)
        return jsonify({"error": "Error removing test applications", "details": str(e)}), 500

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
                    "duration": test.duration,
                    "course": test.course,
                    "model": test.model,
                    "subjects_info": process_subjects_for_test(test),  # Retornar subjects com nomes
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
                "subjects_info": process_subjects_for_test(test),  # Retornar subjects com nomes
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
        
        # Usar fuso horário do Brasil
        from app.utils.timezone_utils import get_brazil_time
        current_time = get_brazil_time()
        
        # Buscar todas as sessões do aluno para estas avaliações
        from app.models.testSession import TestSession
        from app.models.studentAnswer import StudentAnswer
        
        test_ids = [ct.test_id for ct in class_tests]
        sessions = TestSession.query.filter_by(student_id=student.id).filter(
            TestSession.test_id.in_(test_ids)
        ).all()
        sessions_dict = {session.test_id: session for session in sessions}
        
        for test in tests:
            class_test = class_test_map.get(test.id)
            session = sessions_dict.get(test.id)
            
            # Verificar se a avaliação está disponível para o aluno
            is_available = False
            availability_status = "not_available"
            
            # Verificar se o aluno já completou esta avaliação
            has_completed = False
            student_status = "nao_iniciada"
            completed_at = None
            score = None
            grade = None
            can_start = True
            
            if session:
                has_completed = session.status in ['finalizada', 'expirada', 'corrigida', 'revisada']
                student_status = session.status
                completed_at = session.submitted_at.isoformat() if session.submitted_at else None
                score = session.score
                grade = session.grade
                
                # Verificar se há respostas salvas
                has_answers = StudentAnswer.query.filter_by(
                    student_id=student.id,
                    test_id=test.id
                ).first() is not None
                
                can_start = session.status == 'nao_iniciada' or (session.status == 'em_andamento' and not has_answers)
            
            # Determinar disponibilidade baseada no status global E individual
            if test.status == 'agendada' or test.status == 'em_andamento':
                # Se não há data de aplicação definida, considerar disponível
                if not class_test.application:
                    if not has_completed:
                        is_available = True
                        availability_status = "available"
                    else:
                        availability_status = "completed"
                else:
                    # Verificar se já passou da data de aplicação
                    # Converter application para fuso horário do Brasil
                    from app.utils.timezone_utils import convert_to_brazil_time
                    
                    application_time = convert_to_brazil_time(class_test.application)
                    expiration_time = convert_to_brazil_time(class_test.expiration)
                    
                    if current_time >= application_time:
                        # Verificar se não expirou
                        if not expiration_time or current_time <= expiration_time:
                            if not has_completed:
                                is_available = True
                                availability_status = "available"
                            else:
                                availability_status = "completed"
                        else:
                            availability_status = "expired"
                    else:
                        # Ainda não chegou a data de aplicação
                        availability_status = "not_yet_available"
            else:
                # Status global não permite disponibilidade
                availability_status = "not_available"
            
            # Preparar subjects usando a função auxiliar
            subjects = process_subjects_for_test(test)
            
            test_info = {
                "test_id": test.id,
                "title": test.title,
                "description": test.description,
                "type": test.type,
                "subject": subjects[0] if subjects else None,  # Subject principal para compatibilidade
                "subjects": subjects,  # Lista completa de subjects
                "grade": {
                    "id": test.grade.id,
                    "name": test.grade.name
                } if test.grade else None,
                "intructions": test.intructions,
                "max_score": test.max_score,
                "time_limit": test.time_limit.isoformat() if test.time_limit else None,
                "duration": test.duration,  # Duração em minutos
                "course": test.course,
                "model": test.model,
                "subjects_info": subjects,  # Retornar a lista de subjects com nomes
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
                },
                "student_status": {
                    "has_completed": has_completed,
                    "status": student_status,
                    "completed_at": completed_at,
                    "score": score,
                    "grade": grade,
                    "can_start": can_start
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
                "started_at": existing_session.started_at.isoformat() if existing_session.started_at else None,
                "time_limit_minutes": existing_session.time_limit_minutes
            }), 200
        
        # Verificar se há sessão ativa em qualquer teste para este aluno
        active_session_any_test = TestSession.query.filter_by(
            student_id=student.id,
            status='em_andamento'
        ).first()
        
        if active_session_any_test:
            return jsonify({
                "message": "Sessão já iniciada",
                "session_id": active_session_any_test.id,
                "test_id": active_session_any_test.test_id,
                "started_at": active_session_any_test.started_at.isoformat() if active_session_any_test.started_at else None,
                "time_limit_minutes": active_session_any_test.time_limit_minutes
            }), 200
        
        # Criar nova sessão (sem calcular time_limit automaticamente)
        session = TestSession(
            student_id=student.id,
            test_id=test_id,
            time_limit_minutes=None,  # Frontend gerencia o timer
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        # Iniciar a sessão (definir started_at)
        session.start_session()
        
        # Se for a primeira sessão iniciada para esta avaliação, mudar status para 'em_andamento' se estiver 'agendada'
        if test.status == 'agendada':
            active_sessions = TestSession.query.filter_by(
                test_id=test_id,
                status='em_andamento'
            ).count()
            if active_sessions == 0:
                test.status = 'em_andamento'

        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            "message": "Sessão iniciada com sucesso",
            "session_id": session.id,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "time_limit_minutes": session.time_limit_minutes
        }), 201
        
    except Exception as e:
        logging.error(f"Erro ao iniciar sessão do teste: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao iniciar sessão", "details": str(e)}), 500

@bp.route('/<string:test_id>/session-info', methods=['GET'])
@jwt_required()
@role_required("aluno")
def get_session_info(test_id):
    """
    Retorna informações da sessão para o frontend calcular o tempo
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
        
        # Buscar sessão ativa
        session = TestSession.query.filter_by(
            student_id=student.id,
            test_id=test_id,
            status='em_andamento'
        ).first()
        
        if not session:
            return jsonify({
                "message": "Nenhuma sessão ativa encontrada",
                "session_exists": False
            }), 404
        
        # Calcular tempo decorrido e restante
        elapsed_minutes = 0
        remaining_minutes = session.time_limit_minutes
        
        if session.started_at:
            from datetime import datetime
            elapsed_minutes = int((datetime.utcnow() - session.started_at).total_seconds() / 60)
            if session.time_limit_minutes:
                remaining_minutes = max(0, session.time_limit_minutes - elapsed_minutes)
        
        # Verificar se expirou (apenas se time_limit_minutes não for None)
        is_expired = False
        if session.time_limit_minutes is not None and remaining_minutes is not None:
            is_expired = remaining_minutes <= 0
        
        return jsonify({
            "session_id": session.id,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "time_limit_minutes": session.time_limit_minutes,
            "elapsed_minutes": elapsed_minutes,
            "remaining_minutes": remaining_minutes,
            "is_expired": is_expired,
            "session_exists": True
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter informações da sessão: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter informações da sessão", "details": str(e)}), 500

@bp.route('/debug/dates/<string:test_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
def debug_test_dates(test_id):
    """
    Endpoint de debug para verificar as datas de uma avaliação
    """
    try:
        from app.models.classTest import ClassTest
        from datetime import datetime, timezone
        
        # Buscar o teste
        test = Test.query.get(test_id)
        if not test:
            return jsonify({'error': 'Teste não encontrado'}), 404
        
        # Buscar aplicações do teste
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
        # Usar fuso horário do Brasil
        from app.utils.timezone_utils import get_brazil_time
        current_time = get_brazil_time()
        
        debug_info = {
            'test_id': test_id,
            'test_title': test.title,
            'test_status': test.status,
            'current_time': current_time.isoformat(),
            'current_time_utc': current_time.utctimetuple(),
            'class_tests': []
        }
        
        for class_test in class_tests:
            # Converter para fuso horário do Brasil
            from app.utils.timezone_utils import convert_to_brazil_time
            
            application_time = convert_to_brazil_time(class_test.application)
            expiration_time = convert_to_brazil_time(class_test.expiration)
            
            debug_class_test = {
                'class_test_id': class_test.id,
                'class_id': class_test.class_id,
                'application_original': class_test.application.isoformat() if class_test.application else None,
                'application_timezone_aware': application_time.isoformat() if application_time else None,
                'expiration_original': class_test.expiration.isoformat() if class_test.expiration else None,
                'expiration_timezone_aware': expiration_time.isoformat() if expiration_time else None,
                'current_time': current_time.isoformat(),
                'is_application_passed': current_time >= application_time if application_time else None,
                'is_expired': current_time > expiration_time if expiration_time else None,
                'time_until_application': None,
                'time_until_expiration': None
            }
            
            if application_time:
                time_diff = application_time - current_time
                debug_class_test['time_until_application'] = str(time_diff)
            
            if expiration_time:
                time_diff = expiration_time - current_time
                debug_class_test['time_until_expiration'] = str(time_diff)
            
            debug_info['class_tests'].append(debug_class_test)
        
        return jsonify(debug_info), 200
        
    except Exception as e:
        logging.error(f"Erro no debug de datas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro no debug", "details": str(e)}), 500

@bp.route('/debug/subjects/<string:test_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
def debug_test_subjects(test_id):
    """
    Endpoint de debug para verificar os subjects de uma avaliação
    """
    try:
        from app.models.subject import Subject
        
        # Buscar o teste
        test = Test.query.get(test_id)
        if not test:
            return jsonify({'error': 'Teste não encontrado'}), 404
        
        debug_info = {
            'test_id': test_id,
            'test_title': test.title,
            'subject_field': test.subject,  # Campo único
            'subject_rel': {
                'id': test.subject_rel.id,
                'name': test.subject_rel.name
            } if test.subject_rel else None,
            'subjects_info': test.subjects_info,  # Campo JSON
            'subjects_info_type': type(test.subjects_info).__name__,
            'parsed_subjects': []
        }
        
        # Tentar parsear subjects do subjects_info
        if test.subjects_info:
            if isinstance(test.subjects_info, list):
                for i, subject_info in enumerate(test.subjects_info):
                    if isinstance(subject_info, dict):
                        subject_id = subject_info.get('id')
                        subject_name = subject_info.get('name')
                        
                        # Buscar subject no banco se tiver ID
                        if subject_id:
                            subject = Subject.query.get(subject_id)
                            if subject:
                                debug_info['parsed_subjects'].append({
                                    'index': i,
                                    'from_db': True,
                                    'id': subject.id,
                                    'name': subject.name,
                                    'original_data': subject_info
                                })
                            else:
                                debug_info['parsed_subjects'].append({
                                    'index': i,
                                    'from_db': False,
                                    'id': subject_id,
                                    'name': subject_name,
                                    'original_data': subject_info,
                                    'error': 'Subject não encontrado no banco'
                                })
                        else:
                            debug_info['parsed_subjects'].append({
                                'index': i,
                                'from_db': False,
                                'original_data': subject_info,
                                'error': 'Sem ID no subject_info'
                            })
                    else:
                        debug_info['parsed_subjects'].append({
                            'index': i,
                            'from_db': False,
                            'original_data': subject_info,
                            'error': 'Não é um dicionário'
                        })
            else:
                debug_info['parsed_subjects'].append({
                    'error': f'subjects_info não é uma lista, é {type(test.subjects_info).__name__}'
                })
        
        return jsonify(debug_info), 200
        
    except Exception as e:
        logging.error(f"Erro no debug de subjects: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro no debug", "details": str(e)}), 500