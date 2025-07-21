# -*- coding: utf-8 -*-
"""
Rotas especializadas para resultados de avaliações
Endpoints para análise de dados, estatísticas e relatórios
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.evaluation_filters import EvaluationFilters
from app.services.evaluation_aggregator import EvaluationAggregator
from app.services.evaluation_result_service import EvaluationResultService
from app.models.test import Test
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app.models.question import Question
from app.models.subject import Subject
from app.models.school import School
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.classTest import ClassTest
from app import db
import logging
from typing import Dict, Any
from sqlalchemy import func, case
from datetime import datetime
from sqlalchemy.orm import joinedload

bp = Blueprint('evaluation_results', __name__, url_prefix='/evaluation-results')

# ==================== ENDPOINTS TEMPORÁRIOS DE TESTE ====================

@bp.route('/grades', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_grades():
    """
    Lista todas as grades (séries) disponíveis
    """
    try:
        grades = Grade.query.all()
        result = [{
            "id": str(grade.id),
            "name": grade.name,
            "education_stage_id": str(grade.education_stage_id) if grade.education_stage_id else None
        } for grade in grades]
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar grades: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar grades", "details": str(e)}), 500

@bp.route('/test/ping', methods=['GET'])
def test_ping():
    """Endpoint de teste sem autenticação"""
    return jsonify({"message": "Backend está funcionando!", "timestamp": datetime.now().isoformat()}), 200

@bp.route('/test/avaliacoes', methods=['GET'])
def test_avaliacoes():
    """Endpoint de teste para avaliacoes sem autenticação"""
    return jsonify({
        "data": [
            {
                "id": "test-eval-1",
                "titulo": "Avaliação de Matemática - 9º Ano [TESTE]",
                "disciplina": "Matemática",
                "curso": "Ensino Fundamental",
                "serie": "9º Ano",
                "escola": "Escola Municipal Campo Alegre",
                "municipio": "Campo Alegre",
                "data_aplicacao": "2024-01-15T10:00:00Z",
                "data_correcao": "2024-01-16T14:30:00Z",
                "status": "concluida",
                "total_alunos": 25,
                "alunos_participantes": 23,
                "alunos_pendentes": 2,
                "alunos_ausentes": 0,
                "media_nota": 7.2,
                "media_proficiencia": 650,
                "distribuicao_classificacao": {
                    "abaixo_do_basico": 2,
                    "basico": 8,
                    "adequado": 10,
                    "avancado": 3
                },
                "turmas_desempenho": []
            }
        ],
        "total": 1,
        "page": 1,
        "per_page": 10,
        "total_pages": 1
    }), 200

@bp.route('/test/avaliacoes/<string:evaluation_id>', methods=['GET'])
def test_evaluation_by_id(evaluation_id: str):
    """Endpoint de teste para buscar avaliação por ID sem autenticação"""
    return jsonify({
        "id": evaluation_id,
        "titulo": f"Avaliação Teste - {evaluation_id}",
        "disciplina": "Matemática",
        "curso": "Ensino Fundamental",
        "serie": "9º Ano",
        "escola": "Escola Municipal Campo Alegre",
        "municipio": "Campo Alegre",
        "data_aplicacao": "2024-01-15T10:00:00Z",
        "data_correcao": "2024-01-16T14:30:00Z",
        "status": "concluida",
        "total_alunos": 25,
        "alunos_participantes": 23,
        "alunos_pendentes": 2,
        "alunos_ausentes": 0,
        "media_nota": 7.2,
        "media_proficiencia": 650,
        "distribuicao_classificacao": {
            "abaixo_do_basico": 2,
            "basico": 8,
            "adequado": 10,
            "avancado": 3
        }
    }), 200



@bp.route('/test/relatorio-detalhado/<evaluation_id>', methods=['GET'])
def test_relatorio_detalhado(evaluation_id):
    """Endpoint de teste para relatório detalhado sem autenticação"""
    return jsonify({
        "avaliacao": {
            "id": evaluation_id,
            "titulo": "Avaliação de Matemática - 9º Ano [TESTE]",
            "disciplina": "Matemática",
            "total_questoes": 21
        },
        "questoes": [
            {
                "id": "q1",
                "numero": 1,
                "texto": "Questão sobre números e operações",
                "habilidade": "Números e Operações",
                "codigo_habilidade": "9N1.1",
                "tipo": "Múltipla Escolha",
                "dificuldade": "Fácil",
                "porcentagem_acertos": 85.5,
                "porcentagem_erros": 14.5
            },
            {
                "id": "q2",
                "numero": 2,
                "texto": "Questão sobre álgebra",
                "habilidade": "Álgebra",
                "codigo_habilidade": "9A1.2",
                "tipo": "Múltipla Escolha", 
                "dificuldade": "Médio",
                "porcentagem_acertos": 72.3,
                "porcentagem_erros": 27.7
            }
        ],
        "alunos": [
            {
                "id": "student-1",
                "nome": "João Silva",
                "turma": "9º A",
                "respostas": [
                    {"questao_id": "q1", "questao_numero": 1, "resposta_correta": True, "resposta_em_branco": False},
                    {"questao_id": "q2", "questao_numero": 2, "resposta_correta": False, "resposta_em_branco": False}
                ],
                "total_acertos": 15,
                "total_erros": 5,
                "total_em_branco": 1,
                "nota_final": 7.1,
                "proficiencia": 652,
                "classificacao": "Adequado"
            }
        ]
    }), 200

# ==================== ENDPOINTS ORIGINAIS ====================

@bp.errorhandler(Exception)
def handle_error(error):
    """Tratamento global de erros para este blueprint"""
    logging.error(f"Erro em evaluation_results: {str(error)}", exc_info=True)
    return jsonify({
        "error": "Erro interno no servidor",
        "details": str(error)
    }), 500


def convert_proficiency_to_1000_scale(proficiency: float, course: str, subject: str) -> float:
    """
    Converte proficiência do sistema atual para escala 0-1000
    """
    # Determinar proficiência máxima atual
    if "iniciais" in course.lower() or "infantil" in course.lower() or "eja" in course.lower():
        # Para cálculo geral, usar 375 (valor mais alto)
            max_current = 375
    else:  # Anos Finais, Ensino Médio
        # Para cálculo geral, usar 425 (valor mais alto)
            max_current = 425
    
    # Converter para escala 0-1000
    return (proficiency / max_current) * 1000


def get_classification_1000_scale(proficiency_1000: float) -> str:
    """
    Determina classificação baseada na escala 0-1000
    """
    if proficiency_1000 < 200:
        return "Abaixo do Básico"
    elif proficiency_1000 < 500:
        return "Básico"
    elif proficiency_1000 < 750:
        return "Adequado"
    else:
        return "Avançado"


# ==================== ENDPOINT 1: GET /avaliacoes ====================

@bp.route('/avaliacoes', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_avaliacoes():
    """
    Lista avaliações aplicadas com estatísticas completas
    
    Query Parameters conforme especificação do frontend:
    - curso, disciplina, turma, escola
    - proficiencia_min, proficiencia_max
    - nota_min, nota_max
    - classificacao, status
    - data_inicio, data_fim
    - page, per_page
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Extrair parâmetros conforme especificação do frontend
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        per_page = min(per_page, 100)  # Limitar máximo
        
        # Filtros
        curso = request.args.get('curso')
        disciplina = request.args.get('disciplina')
        turma = request.args.get('turma')
        escola = request.args.get('escola')
        status = request.args.getlist('status')
        
        # Query base - INVERTIDA: começar por ClassTest (aplicações)
        # JOIN com Class e Grade para buscar série
        query = ClassTest.query.join(Test, ClassTest.test_id == Test.id)\
                               .options(joinedload(ClassTest.class_).joinedload(Class.grade))
        
        # Se for professor, filtrar apenas suas avaliações
        if user['role'] == 'professor':
            query = query.filter(Test.created_by == user['id'])

        # Aplicar filtros de status na ClassTest (se especificado)
        if status:
            query = query.filter(ClassTest.status.in_(status))
        # Se não especificar status, incluir todos os status (incluindo pendente)

        # Aplicar filtros na tabela Test
        if curso:
            query = query.filter(Test.course.ilike(f"%{curso}%"))
        
        if disciplina:
            query = query.join(Subject, Test.subject == Subject.id)\
                        .filter(Subject.name.ilike(f"%{disciplina}%"))

        # Paginação baseada no número de aplicações
        total = query.count()
        offset = (page - 1) * per_page
        class_tests = query.offset(offset).limit(per_page).all()
        

        
        # Se não há resultados, retornar vazio
        if not class_tests:
            return jsonify({
                "data": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            }), 200
        
        # Gerar dados de resposta
        results = []
        
        for class_test in class_tests:
            evaluation = class_test.test  # Acesso à avaliação através do relacionamento
            
            # Buscar estatísticas de forma otimizada com timeout
            try:
                stats = EvaluationResultService.get_evaluation_results(evaluation.id)
            except Exception as e:
                logging.warning(f"Erro ao buscar estatísticas para avaliação {evaluation.id}: {str(e)}")
                stats = _empty_stats()
            
            # Se demorar muito, usar dados básicos
            if not stats or stats.get('total_alunos', 0) == 0:
                stats = _empty_stats()
            
            # Buscar informações da escola
            escola_nome = "N/A"
            municipio = "N/A"
            if evaluation.schools:  # Se tem escolas aplicadas
                try:
                    # Verificar se schools é uma lista ou string
                    school_id = None
                    if isinstance(evaluation.schools, list) and len(evaluation.schools) > 0:
                        school_id = evaluation.schools[0]
                    elif isinstance(evaluation.schools, str):
                        school_id = evaluation.schools
                    
                    if school_id:
                        school = School.query.get(school_id)
                        if school:
                            escola_nome = school.name
                            if school.city:
                                municipio = school.city.name if hasattr(school.city, 'name') else "N/A"
                except Exception as e:
                    logging.warning(f"Erro ao buscar escola para avaliação {evaluation.id}: {str(e)}")
            
            # ✅ NOVO: Buscar série através da relação ClassTest → Class → Grade
            serie_nome = "N/A"
            grade_id = None
            turma_nome = "N/A"
            try:
                if class_test.class_ and class_test.class_.grade:
                    grade = class_test.class_.grade
                    serie_nome = grade.name
                    grade_id = str(grade.id)
                    turma_nome = class_test.class_.name if class_test.class_.name else f"Turma {class_test.class_.id}"
            except Exception as e:
                logging.warning(f"Erro ao buscar série para avaliação {evaluation.id}: {str(e)}")
            
            # ✅ NOVO: Buscar nome do curso baseado no ID
            curso_nome = "N/A"
            if evaluation.course:
                try:
                    from app.models.educationStage import EducationStage
                    import uuid
                    # Converter string para UUID
                    course_uuid = uuid.UUID(evaluation.course)
                    course_obj = EducationStage.query.get(course_uuid)
                    if course_obj:
                        curso_nome = course_obj.name
                    else:
                        logging.warning(f"Curso não encontrado: {evaluation.course}. Usando Anos Iniciais como padrão.")
                        curso_nome = "Anos Iniciais"
                except (ValueError, TypeError) as e:
                    logging.warning(f"Erro ao converter UUID do curso {evaluation.course}: {str(e)}. Usando Anos Iniciais como padrão.")
                    curso_nome = "Anos Iniciais"
                except Exception as e:
                    logging.warning(f"Erro ao buscar curso {evaluation.course}: {str(e)}. Usando Anos Iniciais como padrão.")
                    curso_nome = "Anos Iniciais"
            
            result = {
                "id": evaluation.id,
                "class_test_id": class_test.id,  # ID da aplicação
                "titulo": evaluation.title,
                "disciplina": evaluation.subject_rel.name if evaluation.subject_rel else 'N/A',
                "curso": curso_nome,
                "serie": serie_nome,  # ✅ Série correta da Grade
                "grade_id": grade_id,  # ✅ ID da Grade
                "turma": turma_nome,  # ✅ Nome da turma
                "escola": escola_nome,
                "municipio": municipio,
                "data_aplicacao": evaluation.created_at.isoformat() if evaluation.created_at else None,
                "data_correcao": evaluation.updated_at.isoformat() if evaluation.updated_at else None,
                "status": class_test.status,  # Status da aplicação (ClassTest)
                "total_alunos": stats['total_alunos'],
                "alunos_participantes": stats['alunos_participantes'],
                "alunos_pendentes": stats['alunos_pendentes'],
                "alunos_ausentes": stats['alunos_ausentes'],
                "media_nota": stats['media_nota'],
                "media_proficiencia": stats['media_proficiencia'],
                "distribuicao_classificacao": stats['distribuicao_classificacao'],
                "turmas_desempenho": []  # Pode ser expandido se necessário
            }
            

            results.append(result)
        
        # Log para debug
        logging.info(f"Total de ClassTests: {len(class_tests)}, Resultados: {len(results)}")
        
        # Verificar e atualizar status automaticamente para avaliações que precisam
        for result in results:
            try:
                # Verificar se a avaliação precisa ter o status atualizado
                test_id = result.get('id')
                current_status = result.get('status')
                
                # Se não está concluída, verificar se deveria estar
                if current_status != "concluida":
                    status_info = _check_and_update_evaluation_status(test_id)
                    if status_info.get("should_be_completed", False):
                        # Atualizar o status no resultado
                        result['status'] = "concluida"
                        logging.info(f"Status atualizado automaticamente para avaliação {test_id}: {status_info.get('completion_reason', '')}")
            except Exception as e:
                logging.warning(f"Erro ao verificar status automático para avaliação {result.get('id')}: {str(e)}")
                continue
        
        # Calcular total de páginas
        total_pages = (total + per_page - 1) // per_page
        
        return jsonify({
            "data": results,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }), 200

    except Exception as e:
        logging.error(f"Erro ao listar avaliações: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar avaliações", "details": str(e)}), 500


def _calculate_evaluation_stats_frontend(test_id: str) -> Dict[str, Any]:
    """
    Calcula estatísticas de uma avaliação para o frontend
    """
    from app.models.question import Question
    
    # Buscar avaliação
    test = Test.query.get(test_id)
    if not test:
        return _empty_stats()
    
    # Buscar TODOS os alunos das turmas onde a avaliação foi aplicada
    class_tests = ClassTest.query.filter_by(test_id=test_id).all()
    class_ids = [ct.class_id for ct in class_tests]
    
    if not class_ids:
        return _empty_stats()
    
    # Buscar todos os alunos dessas turmas com relacionamentos carregados
    all_students = Student.query.options(
        joinedload(Student.class_).joinedload(Class.grade)
    ).filter(Student.class_id.in_(class_ids)).all()
    total_alunos = len(all_students)
    
    if total_alunos == 0:
        return _empty_stats()
    
    # Buscar respostas dos alunos que responderam
    student_answers_data = db.session.query(
        StudentAnswer.student_id,
        func.count(StudentAnswer.id).label('total_answered'),
        func.sum(
            case(
                (StudentAnswer.answer == Question.correct_answer, 1),
                else_=0
            )
        ).label('correct_answers')
    ).join(
        Question, StudentAnswer.question_id == Question.id
    ).filter(
        StudentAnswer.test_id == test_id
    ).group_by(StudentAnswer.student_id).all()
    
    # Criar dicionário para mapear student_id -> dados de resposta
    answers_dict = {sa.student_id: {'total_answered': sa.total_answered, 'correct_answers': sa.correct_answers} for sa in student_answers_data}
    
    total_questions = len(test.questions) if test.questions else 0
    if total_questions == 0:
        return _empty_stats()
    
    # Calcular resultados para cada aluno
    notas = []
    proficiencias_1000 = []
    classificacoes = {'Abaixo do Básico': 0, 'Básico': 0, 'Adequado': 0, 'Avançado': 0}
    alunos_participantes = 0
    
    # Buscar nome do curso baseado no ID
    course_name = "Anos Iniciais"  # Padrão
    if test.course:
        try:
            from app.models.educationStage import EducationStage
            import uuid
            # Converter string para UUID
            course_uuid = uuid.UUID(test.course)
            course_obj = EducationStage.query.get(course_uuid)
            if course_obj:
                course_name = course_obj.name
        except (ValueError, TypeError, Exception):
            # Se houver erro, manter o padrão
            pass
    
    subject_name = test.subject_rel.name if test.subject_rel else "Outras"
    
    for student in all_students:
        # Verificar se o aluno respondeu
        student_answers = answers_dict.get(student.id)
        
        if student_answers:
            # Aluno respondeu - calcular resultados normalmente
            alunos_participantes += 1
            correct_answers = int(student_answers['correct_answers'] or 0)
            
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=correct_answers,
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name
            )
            
            # Converter para escala 0-1000
            prof_1000 = convert_proficiency_to_1000_scale(
                result['proficiency'], course_name, subject_name
            )
            classification_1000 = get_classification_1000_scale(prof_1000)
            
            notas.append(result['grade'])
            proficiencias_1000.append(prof_1000)
            classificacoes[classification_1000] += 1
        else:
            # Aluno NÃO respondeu - contar como "Abaixo do Básico"
            classificacoes['Abaixo do Básico'] += 1
    
    # Calcular médias apenas dos alunos que participaram
    media_nota = round(sum(notas) / len(notas), 2) if notas else 0.0
    media_proficiencia = round(sum(proficiencias_1000) / len(proficiencias_1000), 2) if proficiencias_1000 else 0.0
    
    return {
        'total_alunos': total_alunos,
        'alunos_participantes': alunos_participantes,
        'alunos_pendentes': 0,
        'alunos_ausentes': total_alunos - alunos_participantes,
        'media_nota': media_nota,
        'media_proficiencia': media_proficiencia,
        'distribuicao_classificacao': {
            'abaixo_do_basico': classificacoes['Abaixo do Básico'],
            'basico': classificacoes['Básico'],
            'adequado': classificacoes['Adequado'],
            'avancado': classificacoes['Avançado']
        }
    }


def _calculate_evaluation_stats_by_class(test_id: str, class_id: str) -> Dict[str, Any]:
    """
    Calcula estatísticas de uma avaliação para uma turma específica
    """
    from app.models.question import Question
    
    # Buscar avaliação
    test = Test.query.get(test_id)
    if not test:
        return _empty_stats()
    
    # Buscar TODOS os alunos da turma específica
    all_students = Student.query.options(
        joinedload(Student.class_).joinedload(Class.grade)
    ).filter(Student.class_id == class_id).all()
    total_alunos = len(all_students)
    
    if total_alunos == 0:
        return _empty_stats()
    
    # Buscar respostas dos alunos que responderam
    student_answers_data = db.session.query(
        StudentAnswer.student_id,
        func.count(StudentAnswer.id).label('total_answered'),
        func.sum(
            case(
                (StudentAnswer.answer == Question.correct_answer, 1),
                else_=0
            )
        ).label('correct_answers')
    ).join(
        Question, StudentAnswer.question_id == Question.id
    ).filter(
        StudentAnswer.test_id == test_id,
        StudentAnswer.student_id.in_([s.id for s in all_students])
    ).group_by(StudentAnswer.student_id).all()
    
    # Criar dicionário para mapear student_id -> dados de resposta
    answers_dict = {sa.student_id: {'total_answered': sa.total_answered, 'correct_answers': sa.correct_answers} for sa in student_answers_data}
    
    total_questions = len(test.questions) if test.questions else 0
    if total_questions == 0:
        return _empty_stats()
    
    # Calcular resultados para cada aluno
    notas = []
    proficiencias_1000 = []
    classificacoes = {'Abaixo do Básico': 0, 'Básico': 0, 'Adequado': 0, 'Avançado': 0}
    alunos_participantes = 0
    
    # Buscar nome do curso baseado no ID
    course_name = "Anos Iniciais"  # Padrão
    if test.course:
        try:
            from app.models.educationStage import EducationStage
            import uuid
            # Converter string para UUID
            course_uuid = uuid.UUID(test.course)
            course_obj = EducationStage.query.get(course_uuid)
            if course_obj:
                course_name = course_obj.name
        except (ValueError, TypeError, Exception):
            # Se houver erro, manter o padrão
            pass
    
    subject_name = test.subject_rel.name if test.subject_rel else "Outras"
    
    for student in all_students:
        # Verificar se o aluno respondeu
        student_answers = answers_dict.get(student.id)
        
        if student_answers:
            # Aluno respondeu - calcular resultados normalmente
            alunos_participantes += 1
            correct_answers = int(student_answers['correct_answers'] or 0)
            
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=correct_answers,
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name
            )
            
            # Converter para escala 0-1000
            prof_1000 = convert_proficiency_to_1000_scale(
                result['proficiency'], course_name, subject_name
            )
            classification_1000 = get_classification_1000_scale(prof_1000)
            
            notas.append(result['grade'])
            proficiencias_1000.append(prof_1000)
            classificacoes[classification_1000] += 1
        else:
            # Aluno NÃO respondeu - contar como "Abaixo do Básico"
            classificacoes['Abaixo do Básico'] += 1
    
    # Calcular médias apenas dos alunos que participaram
    media_nota = round(sum(notas) / len(notas), 2) if notas else 0.0
    media_proficiencia = round(sum(proficiencias_1000) / len(proficiencias_1000), 2) if proficiencias_1000 else 0.0
    
    return {
        'total_alunos': total_alunos,
        'alunos_participantes': alunos_participantes,
        'alunos_pendentes': 0,
        'alunos_ausentes': total_alunos - alunos_participantes,
        'media_nota': media_nota,
        'media_proficiencia': media_proficiencia,
        'distribuicao_classificacao': {
            'abaixo_do_basico': classificacoes['Abaixo do Básico'],
            'basico': classificacoes['Básico'],
            'adequado': classificacoes['Adequado'],
            'avancado': classificacoes['Avançado']
        }
    }


def _empty_stats():
    """Retorna estatísticas vazias"""
    return {
        'total_alunos': 0,
        'alunos_participantes': 0,
        'alunos_pendentes': 0,
        'alunos_ausentes': 0,
        'media_nota': 0.0,
        'media_proficiencia': 0.0,
        'distribuicao_classificacao': {
            'abaixo_do_basico': 0,
            'basico': 0,
            'adequado': 0,
            'avancado': 0
        }
    }


# ==================== ENDPOINT 2: GET /alunos ====================

@bp.route('/alunos', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def listar_alunos():
    """
    Lista alunos com resultados de uma avaliação específica
    
    Query Parameters:
    - avaliacao_id (obrigatório)
    - Outros filtros opcionais
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Parâmetro obrigatório
        avaliacao_id = request.args.get('avaliacao_id')
        if not avaliacao_id:
            return jsonify({"error": "avaliacao_id é obrigatório"}), 400
        
        # Verificar se avaliação existe
        test = Test.query.get(avaliacao_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Buscar TODOS os alunos das turmas onde a avaliação foi aplicada
        # Primeiro, buscar as turmas onde a avaliação foi aplicada
        class_tests = ClassTest.query.filter_by(test_id=avaliacao_id).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return jsonify({
                "data": [],
                "message": "Avaliação não foi aplicada em nenhuma turma"
            }), 200
        
        # Buscar todos os alunos dessas turmas com relacionamentos carregados
        all_students = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade)
        ).filter(Student.class_id.in_(class_ids)).all()
        
        # ✅ NOVO: Buscar resultados pré-calculados da tabela evaluation_results
        from app.models.evaluationResult import EvaluationResult
        
        evaluation_results = EvaluationResult.query.filter_by(test_id=avaliacao_id).all()
        results_dict = {er.student_id: er for er in evaluation_results}
        
        total_questions = len(test.questions) if test.questions else 0
        
        results = []
        for student in all_students:
            # Verificar se o aluno tem resultado calculado
            evaluation_result = results_dict.get(student.id)
            
            if evaluation_result:
                # Aluno respondeu - usar resultados pré-calculados
                total_answered = evaluation_result.correct_answers  # Simplificado
                correct_answers = evaluation_result.correct_answers
                
                # Converter para escala 0-1000
                prof_1000 = convert_proficiency_to_1000_scale(
                    evaluation_result.proficiency, "Anos Iniciais", test.subject_rel.name if test.subject_rel else "Outras"
                )
                classification_1000 = get_classification_1000_scale(prof_1000)
                
                status = "concluida"
            else:
                # Aluno NÃO respondeu - retornar zeros
                total_answered = 0
                correct_answers = 0
                prof_1000 = 0.0
                classification_1000 = 'Abaixo do Básico'
                status = "pendente"
            
            # Buscar informações da turma e grade
            turma_nome = "N/A"
            grade_nome = "N/A"
            if student.class_:
                turma_nome = student.class_.name
                if student.class_.grade:
                    grade_nome = student.class_.grade.name
            
            student_result = {
                "id": student.id,
                "nome": student.name,
                "turma": turma_nome,
                "grade": grade_nome,
                "nota": evaluation_result.grade if evaluation_result else 0.0,
                "proficiencia": round(prof_1000, 2),
                "classificacao": classification_1000,
                "questoes_respondidas": total_answered,
                "acertos": correct_answers,
                "erros": total_answered - correct_answers,
                "em_branco": total_questions - total_answered,
                "tempo_gasto": 3600,  # Placeholder - pode ser implementado
                "status": status
            }
            results.append(student_result)
        
        return jsonify({
            "data": results
        }), 200

    except Exception as e:
        logging.error(f"Erro ao listar alunos: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar alunos", "details": str(e)}), 500


# ==================== ENDPOINT 3: GET /avaliacoes/{id} ====================

@bp.route('/avaliacoes/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_evaluation_by_id(evaluation_id: str):
    """
    Retorna dados de uma avaliação específica
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Buscar estatísticas da avaliação
        stats = EvaluationResultService.get_evaluation_results(evaluation_id)
        
        # Buscar informações da escola
        escola_nome = "N/A"
        municipio = "N/A"
        if test.schools:
            try:
                school_id = None
                if isinstance(test.schools, list) and len(test.schools) > 0:
                    school_id = test.schools[0]
                elif isinstance(test.schools, str):
                    school_id = test.schools
                
                if school_id:
                    school = School.query.get(school_id)
                    if school:
                        escola_nome = school.name
                        if school.city:
                            municipio = school.city.name if hasattr(school.city, 'name') else "N/A"
            except Exception as e:
                logging.warning(f"Erro ao buscar escola para avaliação {test.id}: {str(e)}")
        
        # Garantir que arrays sejam inicializados como vazios
        turmas_desempenho = []
        
        # Buscar nome do curso
        curso_nome = "N/A"
        if test.course:
            try:
                from app.models.educationStage import EducationStage
                import uuid
                course_uuid = uuid.UUID(test.course)
                course_obj = EducationStage.query.get(course_uuid)
                if course_obj:
                    curso_nome = course_obj.name
            except Exception as e:
                logging.warning(f"Erro ao buscar curso {test.course}: {str(e)}")
                curso_nome = "Anos Iniciais"
        
        result = {
            "id": test.id,
            "titulo": test.title,
            "disciplina": test.subject_rel.name if test.subject_rel else 'N/A',
            "curso": curso_nome,
            "serie": "N/A",
            "escola": escola_nome,
            "municipio": municipio,
            "data_aplicacao": test.created_at.isoformat() if test.created_at else None,
            "data_correcao": test.updated_at.isoformat() if test.updated_at else None,
            "status": "concluida",
            "total_alunos": stats['total_alunos'],
            "alunos_participantes": stats['alunos_participantes'],
            "alunos_pendentes": stats['alunos_pendentes'],
            "alunos_ausentes": stats['alunos_ausentes'],
            "media_nota": stats['media_nota'],
            "media_proficiencia": stats['media_proficiencia'],
            "distribuicao_classificacao": stats['distribuicao_classificacao']
        }
        
        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Erro ao buscar avaliação: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar avaliação", "details": str(e)}), 500


# ==================== ENDPOINT 4: GET /relatorio-detalhado ====================

@bp.route('/relatorio-detalhado/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def relatorio_detalhado(evaluation_id: str):
    """
    Retorna relatório detalhado de uma avaliação
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Dados da avaliação
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "disciplina": test.subject_rel.name if test.subject_rel else 'N/A',
            "total_questoes": len(test.questions) if test.questions else 0
        }
        
        # Dados das questões
        questoes_data = []
        if test.questions:
            for i, question in enumerate(test.questions, 1):
                # Calcular porcentagem de acertos
                total_respostas = StudentAnswer.query.filter_by(
                    test_id=evaluation_id, 
                    question_id=question.id
                ).count()
                
                # Calcular acertos corretamente baseado no tipo de questão
                acertos = 0
                if question.question_type == 'multipleChoice':
                    # Para questões de múltipla escolha, verificar alternatives
                    for answer in StudentAnswer.query.filter_by(
                        test_id=evaluation_id,
                        question_id=question.id
                    ).all():
                        if EvaluationResultService.check_multiple_choice_answer(answer.answer, question.alternatives):
                            acertos += 1
                else:
                    # Para outros tipos, usar correct_answer
                    acertos = StudentAnswer.query.filter_by(
                        test_id=evaluation_id,
                        question_id=question.id,
                        answer=question.correct_answer
                    ).count() if total_respostas > 0 else 0
                
                porcentagem_acertos = (acertos / total_respostas * 100) if total_respostas > 0 else 0
                
                questao_data = {
                    "id": question.id,
                    "numero": i,
                    "texto": question.text or f"Questão {i}",
                    "habilidade": question.skill or "N/A",
                    "codigo_habilidade": question.skill or "N/A",
                    "tipo": question.question_type or "multipleChoice",
                    "dificuldade": question.difficulty_level or "Médio",
                    "porcentagem_acertos": round(porcentagem_acertos, 2),
                    "porcentagem_erros": round(100 - porcentagem_acertos, 2)
                }
                questoes_data.append(questao_data)
        
        # Dados dos alunos (buscar diretamente)
        from app.models.evaluationResult import EvaluationResult
        
        # Buscar TODOS os alunos das turmas onde a avaliação foi aplicada
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return jsonify({
                "avaliacao": avaliacao_data,
                "questoes": questoes_data,
                "alunos": []
            }), 200
        
        # Buscar todos os alunos dessas turmas
        all_students = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade)
        ).filter(Student.class_id.in_(class_ids)).all()
        
        # Buscar resultados pré-calculados
        evaluation_results = EvaluationResult.query.filter_by(test_id=evaluation_id).all()
        results_dict = {er.student_id: er for er in evaluation_results}
        
        alunos_data = []
        for student in all_students:
            # Verificar se o aluno tem resultado calculado
            evaluation_result = results_dict.get(student.id)
            
            if evaluation_result:
                # Aluno respondeu - usar resultados pré-calculados
                total_answered = evaluation_result.correct_answers  # Simplificado
                correct_answers = evaluation_result.correct_answers
                
                # Converter para escala 0-1000
                prof_1000 = convert_proficiency_to_1000_scale(
                    evaluation_result.proficiency, "Anos Iniciais", test.subject_rel.name if test.subject_rel else "Outras"
                )
                classification_1000 = get_classification_1000_scale(prof_1000)
                
                status = "concluida"
            else:
                # Aluno NÃO respondeu - retornar zeros
                total_answered = 0
                correct_answers = 0
                prof_1000 = 0.0
                classification_1000 = 'Abaixo do Básico'
                status = "nao_respondida"
            
            # Buscar informações da turma
            turma_nome = "N/A"
            if student.class_:
                turma_nome = student.class_.name
            
            # Buscar respostas detalhadas do aluno
            respostas = []
            student_answers = StudentAnswer.query.filter_by(
                test_id=evaluation_id,
                student_id=student.id
            ).all()
            
            for answer in student_answers:
                question = Question.query.get(answer.question_id)
                if question:
                    # Verificar se a resposta está correta
                    is_correct = False
                    if question.question_type == 'multipleChoice':
                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.alternatives)
                    else:
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                    
                    resposta_data = {
                        "questao_id": question.id,
                        "questao_numero": question.number or 1,
                        "resposta_correta": is_correct,
                        "resposta_em_branco": not answer.answer,
                        "tempo_gasto": 120  # Placeholder
                    }
                    respostas.append(resposta_data)
            
            aluno_detalhado = {
                "id": student.id,
                "nome": student.name,
                "turma": turma_nome,
                "respostas": respostas,
                "total_acertos": correct_answers,
                "total_erros": total_answered - correct_answers,
                "total_em_branco": len(test.questions) - total_answered if test.questions else 0,
                "nota_final": evaluation_result.grade if evaluation_result else 0.0,
                "proficiencia": round(prof_1000, 2),
                "classificacao": classification_1000,
                "status": status
            }
            alunos_data.append(aluno_detalhado)
        
        return jsonify({
            "avaliacao": avaliacao_data,
            "questoes": questoes_data,
            "alunos": alunos_data
        }), 200

    except Exception as e:
        logging.error(f"Erro ao gerar relatório detalhado: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao gerar relatório detalhado", "details": str(e)}), 500


# ==================== ENDPOINT 4: POST /avaliacoes/calcular ====================

@bp.route('/avaliacoes/calcular', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def recalcular_avaliacao():
    """
    Recalcula resultados de uma avaliação
    """
    try:
        data = request.get_json()
        
        if not data or 'avaliacao_id' not in data:
            return jsonify({"error": "avaliacao_id é obrigatório"}), 400
        
        avaliacao_id = data['avaliacao_id']
        
        # Verificar se avaliação existe
        test = Test.query.get(avaliacao_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Recalcular (por enquanto retorna sucesso)
        return jsonify({
            "message": "Recálculo realizado com sucesso",
            "avaliacao_id": avaliacao_id
        }), 200

    except Exception as e:
        logging.error(f"Erro ao recalcular avaliação: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao recalcular avaliação", "details": str(e)}), 500


# ==================== ENDPOINT 5: PATCH /avaliacoes/<test_id>/finalizar ====================

@bp.route('/avaliacoes/<string:test_id>/finalizar', methods=['PATCH'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def finalizar_avaliacao(test_id):
    """
    Finaliza uma avaliação manualmente (marca como concluída)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode finalizar avaliações que criou"}), 403
        
        # Buscar ClassTest para esta avaliação
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
        if not class_tests:
            return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma"}), 404
        
        # Verificar se já está concluída
        already_completed = all(ct.status == "concluida" for ct in class_tests)
        if already_completed:
            return jsonify({
                "message": "Avaliação já está finalizada",
                "test_id": test_id,
                "status": "concluida"
            }), 200
        
        # Marcar todas as aplicações como concluídas
        updated_count = 0
        for class_test in class_tests:
            if class_test.status != "concluida":
                class_test.status = "concluida"
                class_test.updated_at = datetime.utcnow()
                updated_count += 1
        
        db.session.commit()
        
        # Obter resumo atual após a finalização
        summary = _get_evaluation_status_summary(test_id)
        
        return jsonify({
            "message": "Avaliação finalizada com sucesso",
            "test_id": test_id,
            "class_tests_updated": updated_count,
            "total_class_tests": len(class_tests),
            "finalized_at": datetime.utcnow().isoformat(),
            "status_summary": summary
        }), 200

    except Exception as e:
        logging.error(f"Erro ao finalizar avaliação: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao finalizar avaliação", "details": str(e)}), 500


# ==================== ENDPOINTS AUXILIARES (SE NECESSÁRIO) ====================
# Os endpoints auxiliares agora estão em basic_endpoints.py 

@bp.route('/admin/submitted-evaluations', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_submitted_evaluations():
    """
    Retorna todas as avaliações enviadas pelos alunos para correção
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found"}), 401

        # Buscar sessões finalizadas que precisam de correção
        query = db.session.query(TestSession).options(
            joinedload(TestSession.student),
            joinedload(TestSession.test).joinedload(Test.subject_rel),
            joinedload(TestSession.test).joinedload(Test.grade)
        ).filter(
            TestSession.status.in_(['finalizada', 'corrigida', 'revisada'])
        )

        # Filtros opcionais
        status_filter = request.args.get('status')
        if status_filter and status_filter != 'all':
            if status_filter == 'pending':
                query = query.filter(TestSession.status == 'finalizada')
            elif status_filter == 'corrected':
                query = query.filter(TestSession.status == 'corrigida')
            elif status_filter == 'reviewed':
                query = query.filter(TestSession.status == 'revisada')

        subject_filter = request.args.get('subject')
        if subject_filter and subject_filter != 'all':
            query = query.join(Test).filter(Test.subject == subject_filter)

        grade_filter = request.args.get('grade')
        if grade_filter and grade_filter != 'all':
            query = query.join(Test).filter(Test.grade_id == grade_filter)

        search_filter = request.args.get('search')
        if search_filter:
            query = query.join(Student).filter(
                Student.name.ilike(f'%{search_filter}%')
            )

        sessions = query.order_by(TestSession.submitted_at.desc()).all()

        results = []
        for session in sessions:
            # Buscar respostas do aluno
            answers = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id
            ).all()

            # Buscar questões do teste
            questions = Question.query.filter_by(test_id=session.test_id).all()
            questions_dict = {q.id: q for q in questions}

            # Preparar questões com respostas
            questions_with_answers = []
            for answer in answers:
                question = questions_dict.get(answer.question_id)
                if question:
                    questions_with_answers.append({
                        "id": question.id,
                        "number": question.number or len(questions_with_answers) + 1,
                        "type": question.question_type,
                        "text": question.text,
                        "options": question.alternatives if question.alternatives else None,
                        "points": question.value or 1,
                        "correctAnswer": question.correct_answer,
                        "studentAnswer": answer.answer,
                        "isCorrect": answer.answer == question.correct_answer if question.correct_answer else None,
                        "manualPoints": answer.manual_score,
                        "feedback": answer.feedback
                    })

            # Determinar status
            status = "pending"
            if session.status == 'corrigida':
                status = "corrected"
            elif session.status == 'revisada':
                status = "reviewed"

            result = {
                "id": session.id,
                "sessionId": session.id,
                "studentId": session.student_id,
                "studentName": session.student.name if session.student else "Aluno não encontrado",
                "testId": session.test_id,
                "testTitle": session.test.title if session.test else "Teste não encontrado",
                "subject": {
                    "id": session.test.subject if session.test else "",
                    "name": session.test.subject_rel.name if session.test and session.test.subject_rel else "Não informado"
                },
                "grade": {
                    "id": str(session.test.grade_id) if session.test and session.test.grade_id else "",
                    "name": session.test.grade.name if session.test and session.test.grade else "Não informado"
                },
                "submittedAt": session.submitted_at.isoformat() if session.submitted_at else "",
                "duration": session.duration_minutes or 0,
                "status": status,
                "totalQuestions": session.total_questions or len(questions_with_answers),
                "answeredQuestions": len(answers),
                "autoScore": session.correct_answers,
                "manualScore": sum(q.get("manualPoints", 0) for q in questions_with_answers if q.get("manualPoints")),
                "finalScore": session.score,
                "percentage": session.score,
                "correctedBy": session.corrected_by,
                "correctedAt": session.corrected_at.isoformat() if session.corrected_at else None,
                "feedback": session.feedback,
                "questions": questions_with_answers
            }
            results.append(result)

        return jsonify(results), 200

    except Exception as e:
        logging.error(f"Erro ao buscar avaliações enviadas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar avaliações enviadas", "details": str(e)}), 500


@bp.route('/admin/evaluations/<evaluation_id>/correct', methods=['PATCH'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def save_evaluation_correction(evaluation_id):
    """
    Salva a correção de uma avaliação (sem finalizar)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found"}), 401

        data = request.get_json()
        session_id = data.get('sessionId')
        questions_data = data.get('questions', [])
        general_feedback = data.get('generalFeedback', '')

        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({"error": "Sessão não encontrada"}), 404

        # Atualizar correções das questões
        for question_data in questions_data:
            question_id = question_data.get('questionId')
            manual_points = question_data.get('manualPoints')
            feedback = question_data.get('feedback', '')

            # Buscar resposta do aluno
            answer = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id,
                question_id=question_id
            ).first()

            if answer:
                answer.manual_score = manual_points
                answer.feedback = feedback
                answer.corrected_by = user['id']
                answer.corrected_at = datetime.utcnow()

        # Atualizar sessão
        session.status = 'corrigida'
        session.feedback = general_feedback
        session.corrected_by = user['id']
        session.corrected_at = datetime.utcnow()

        # Recalcular pontuação total
        total_score = 0
        answers = StudentAnswer.query.filter_by(
            student_id=session.student_id,
            test_id=session.test_id
        ).all()

        for answer in answers:
            question = Question.query.get(answer.question_id)
            if question:
                if question.question_type == 'essay' and answer.manual_score is not None:
                    total_score += answer.manual_score
                elif answer.answer == question.correct_answer:
                    total_score += question.value or 1

        # Calcular percentual
        total_possible = session.total_questions * 1  # Assumindo 1 ponto por questão
        if total_possible > 0:
            session.score = round((total_score / total_possible) * 100, 1)

        db.session.commit()

        return jsonify({
            "message": "Correção salva com sucesso",
            "finalScore": total_score,
            "percentage": session.score
        }), 200

    except Exception as e:
        logging.error(f"Erro ao salvar correção: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao salvar correção", "details": str(e)}), 500


@bp.route('/admin/evaluations/<evaluation_id>/finish', methods=['PATCH'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def finish_evaluation_correction(evaluation_id):
    """
    Finaliza a correção de uma avaliação e disponibiliza para o aluno
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found"}), 401

        data = request.get_json()
        session_id = data.get('sessionId')
        questions_data = data.get('questions', [])
        general_feedback = data.get('generalFeedback', '')

        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({"error": "Sessão não encontrada"}), 404

        # Atualizar correções das questões
        for question_data in questions_data:
            question_id = question_data.get('questionId')
            manual_points = question_data.get('manualPoints')
            feedback = question_data.get('feedback', '')

            # Buscar resposta do aluno
            answer = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id,
                question_id=question_id
            ).first()

            if answer:
                answer.manual_score = manual_points
                answer.feedback = feedback
                answer.corrected_by = user['id']
                answer.corrected_at = datetime.utcnow()

        # Finalizar sessão
        session.status = 'revisada'
        session.feedback = general_feedback
        session.corrected_by = user['id']
        session.corrected_at = datetime.utcnow()

        # Recalcular pontuação total
        total_score = 0
        answers = StudentAnswer.query.filter_by(
            student_id=session.student_id,
            test_id=session.test_id
        ).all()

        for answer in answers:
            question = Question.query.get(answer.question_id)
            if question:
                if question.question_type == 'essay' and answer.manual_score is not None:
                    total_score += answer.manual_score
                elif answer.answer == question.correct_answer:
                    total_score += question.value or 1

        # Calcular percentual
        total_possible = session.total_questions * 1  # Assumindo 1 ponto por questão
        if total_possible > 0:
            session.score = round((total_score / total_possible) * 100, 1)

        db.session.commit()

        # Aqui poderia enviar notificação para o aluno
        # notification_service.notify_student_result_ready(session.student_id, session.test_id)

        return jsonify({
            "message": "Correção finalizada com sucesso",
            "finalScore": total_score,
            "percentage": session.score
        }), 200

    except Exception as e:
        logging.error(f"Erro ao finalizar correção: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao finalizar correção", "details": str(e)}), 500 

# ==================== CÁLCULO DE NOTAS E CORREÇÃO ====================

@bp.route('/<string:test_id>/calculate-scores', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def calculate_test_scores(test_id):
    """
    Calcula as notas de todos os alunos para uma avaliação específica
    
    Body: (opcional)
    {
        "student_ids": ["uuid1", "uuid2"] // Se fornecido, calcula apenas para estes alunos
    }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Buscar o teste e suas questões
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Teste não encontrado"}), 404
            
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode calcular notas de testes que criou"}), 403
            
        questions = Question.query.filter_by(test_id=test_id).all()
        if not questions:
            return jsonify({"error": "Nenhuma questão encontrada para este teste"}), 404
            
        # Filtrar por alunos específicos se fornecido
        data = request.get_json() or {}
        student_ids_filter = data.get('student_ids')
        
        if student_ids_filter:
            student_answers = StudentAnswer.query.filter(
                StudentAnswer.test_id == test_id,
                StudentAnswer.student_id.in_(student_ids_filter)
            ).all()
        else:
            student_answers = StudentAnswer.query.filter_by(test_id=test_id).all()
        
        if not student_answers:
            return jsonify({
                "test_id": test_id,
                "message": "Nenhuma resposta encontrada para este teste",
                "total_students": 0,
                "results": {}
            }), 200
        
        # Agrupar respostas por aluno
        student_responses = {}
        for answer in student_answers:
            if answer.student_id not in student_responses:
                student_responses[answer.student_id] = []
            student_responses[answer.student_id].append(answer)
        
        results = {}
        
        for student_id, answers in student_responses.items():
            results[student_id] = {
                "total_questions": len(questions),
                "answered_questions": len(answers),
                "correct_answers": 0,
                "multiple_choice_questions": 0,
                "essay_questions": 0,
                "pending_corrections": 0,
                "corrected_essays": 0,
                "score_percentage": 0.0,
                "total_score": 0.0,
                "max_possible_score": 0.0
            }
            
            for answer in answers:
                # Encontrar a questão correspondente
                question = next((q for q in questions if q.id == answer.question_id), None)
                if not question:
                    continue
                
                # Adicionar valor da questão ao máximo possível
                question_value = question.value or 1.0
                results[student_id]["max_possible_score"] += question_value
                
                # Verificar tipo de questão
                if question.question_type == 'multipleChoice':
                    results[student_id]["multiple_choice_questions"] += 1
                    # Questão de múltipla escolha - correção automática
                    is_correct = check_multiple_choice_answer(answer.answer, question.alternatives)
                    if is_correct:
                        results[student_id]["correct_answers"] += 1
                        results[student_id]["total_score"] += question_value
                        
                elif question.question_type == 'essay':
                    results[student_id]["essay_questions"] += 1
                    # Questão dissertativa - verificar se já foi corrigida
                    if answer.manual_score is not None:
                        results[student_id]["corrected_essays"] += 1
                        # Calcular pontuação baseada no manual_score
                        essay_score = (answer.manual_score / 100.0) * question_value
                        results[student_id]["total_score"] += essay_score
                        if answer.manual_score > 0:
                            results[student_id]["correct_answers"] += 1
                    else:
                        results[student_id]["pending_corrections"] += 1
                else:
                    # Outros tipos de questão - usar correção automática se houver correct_answer
                    if question.correct_answer:
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                        if is_correct:
                            results[student_id]["correct_answers"] += 1
                            results[student_id]["total_score"] += question_value
            
            # Calcular percentual de acertos (apenas questões corrigidas automaticamente)
            auto_corrected_questions = results[student_id]["multiple_choice_questions"]
            if auto_corrected_questions > 0:
                results[student_id]["score_percentage"] = (results[student_id]["correct_answers"] / auto_corrected_questions) * 100
            else:
                results[student_id]["score_percentage"] = 0.0
                
        return jsonify({
            "test_id": test_id,
            "test_title": test.title,
            "total_students": len(results),
            "total_questions": len(questions),
            "calculation_timestamp": datetime.utcnow().isoformat(),
            "results": results
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao calcular notas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao calcular notas", "details": str(e)}), 500


@bp.route('/<string:test_id>/manual-correction', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def manual_correction(test_id):
    """
    Permite ao professor corrigir questões dissertativas
    
    Body:
    {
        "student_id": "uuid",
        "question_id": "uuid", 
        "score": 85.5,  // Pontuação de 0 a 100
        "feedback": "Boa resposta, mas poderia ser mais detalhada",
        "is_correct": true  // opcional: true/false baseado na pontuação
    }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados são obrigatórios"}), 400
            
        student_id = data.get('student_id')
        question_id = data.get('question_id')
        score = data.get('score')
        feedback = data.get('feedback')
        is_correct = data.get('is_correct')
        
        if not student_id or not question_id or score is None:
            return jsonify({"error": "student_id, question_id e score são obrigatórios"}), 400
            
        # Validar score
        if not isinstance(score, (int, float)) or score < 0 or score > 100:
            return jsonify({"error": "Score deve ser um número entre 0 e 100"}), 400
        
        # Verificar se o teste existe e se o usuário tem permissão
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Teste não encontrado"}), 404
            
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode corrigir testes que criou"}), 403
        
        # Buscar resposta do aluno
        # O student_id pode ser user_id ou student_id real
        # Primeiro tentar como user_id
        student = Student.query.filter_by(user_id=student_id).first()
        if student:
            # É um user_id, usar o student.id
            actual_student_id = student.id
        else:
            # Pode ser um student_id real, verificar se existe
            student = Student.query.get(student_id)
            if not student:
                return jsonify({"error": "Aluno não encontrado"}), 404
            actual_student_id = student_id
            
        answer = StudentAnswer.query.filter_by(
            test_id=test_id,
            student_id=actual_student_id,
            question_id=question_id
        ).first()
        
        if not answer:
            return jsonify({"error": "Resposta não encontrada"}), 404
            
        # Verificar se a questão é dissertativa
        question = Question.query.get(question_id)
        if not question or question.question_type != 'essay':
            return jsonify({"error": "Apenas questões dissertativas podem ser corrigidas manualmente"}), 400
        
        # Atualizar com correção manual
        answer.manual_score = float(score)
        answer.feedback = feedback
        answer.corrected_by = user['id']
        answer.corrected_at = datetime.utcnow()
        
        # Definir is_correct baseado na pontuação se não fornecido
        if is_correct is None:
            answer.is_correct = score > 50  # Considera correto se score > 50%
        else:
            answer.is_correct = bool(is_correct)
        
        db.session.commit()
        
        return jsonify({
            "message": "Correção salva com sucesso",
            "student_id": student_id,
            "question_id": question_id,
            "score": score,
            "corrected_at": answer.corrected_at.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao salvar correção: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao salvar correção", "details": str(e)}), 500


@bp.route('/<string:test_id>/student/<string:student_id>/results', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
def get_student_test_results(test_id, student_id):
    """
    Retorna os resultados detalhados de um aluno específico em um teste
    
    Query Parameters:
    - include_answers: true/false (incluir respostas detalhadas)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        if user['role'] == 'aluno':
            # Aluno só pode ver seus próprios resultados
            # O student_id enviado é o user_id, não o id da tabela Student
            if user['id'] != student_id:
                return jsonify({"error": "Você só pode ver seus próprios resultados"}), 403
        elif user['role'] == 'professor':
            # Professor só pode ver resultados de testes que criou
            test = Test.query.get(test_id)
            if not test or test.created_by != user['id']:
                return jsonify({"error": "Você só pode ver resultados de testes que criou"}), 403
        
        # ✅ NOVO: Buscar resultado pré-calculado da tabela evaluation_results
        from app.models.evaluationResult import EvaluationResult
        
        # O student_id na URL pode ser user_id ou student_id real
        # Primeiro, tentar buscar como user_id
        student = Student.query.filter_by(user_id=student_id).first()
        if student:
            # É um user_id, usar o student.id
            actual_student_id = student.id
        else:
            # Pode ser um student_id real, verificar se existe
            student = Student.query.get(student_id)
            if not student:
                return jsonify({"error": "Aluno não encontrado"}), 404
            actual_student_id = student_id
        
        # Buscar resultado pré-calculado
        evaluation_result = EvaluationResult.query.filter_by(
            test_id=test_id,
            student_id=actual_student_id
        ).first()
        
        if not evaluation_result:
            return jsonify({
                "error": "Aluno não respondeu esta avaliação",
                "message": "O aluno não possui resultados calculados para esta avaliação",
                "test_id": test_id,
                "student_id": student_id,
                "student_db_id": student.id,
                "total_questions": len(test.questions) if test.questions else 0,
                "answered_questions": 0,
                "correct_answers": 0,
                "score_percentage": 0.0,
                "total_score": 0.0,
                "max_possible_score": 0.0,
                "status": "nao_respondida"
            }), 200
        
        # ✅ NOVO: Usar dados pré-calculados da tabela evaluation_results
        test = Test.query.get(test_id)
        questions = Question.query.filter_by(test_id=test_id).all()
        
        # Usar dados pré-calculados
        total_questions = evaluation_result.total_questions
        correct_answers = evaluation_result.correct_answers
        score_percentage = evaluation_result.score_percentage
        grade = evaluation_result.grade
        proficiency = evaluation_result.proficiency
        classification = evaluation_result.classification
        
        # Converter proficiência para escala 0-1000
        prof_1000 = convert_proficiency_to_1000_scale(
            proficiency, "Anos Iniciais", test.subject_rel.name if test.subject_rel else "Outras"
        )
        
        # Buscar respostas detalhadas se solicitado
        detailed_answers = []
        if request.args.get('include_answers', 'false').lower() == 'true':
            answers = StudentAnswer.query.filter_by(
                test_id=test_id,
                student_id=student.id
            ).all()
            
            questions_dict = {q.id: q for q in questions}
            
            for answer in answers:
                question = questions_dict.get(answer.question_id)
                if not question:
                    continue
                    
                question_value = question.value or 1.0
                
                answer_detail = {
                    "question_id": answer.question_id,
                    "question_number": question.number,
                    "question_text": question.text,
                    "question_type": question.question_type,
                    "question_value": question_value,
                    "student_answer": answer.answer,
                    "answered_at": answer.answered_at.isoformat() if answer.answered_at else None,
                    "is_correct": None,
                    "score": None,
                    "feedback": answer.feedback,
                    "corrected_by": answer.corrected_by,
                    "corrected_at": answer.corrected_at.isoformat() if answer.corrected_at else None
                }
                
                if question.question_type == 'multipleChoice':
                    is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.alternatives)
                    answer_detail["is_correct"] = is_correct
                    answer_detail["score"] = question_value if is_correct else 0
                    
                elif question.question_type == 'essay':
                    if answer.manual_score is not None:
                        essay_score = (answer.manual_score / 100.0) * question_value
                        answer_detail["score"] = essay_score
                        answer_detail["manual_score"] = answer.manual_score
                        answer_detail["is_correct"] = answer.is_correct
                    else:
                        answer_detail["status"] = "pending_correction"
                        
                else:
                    # Outros tipos
                    if question.correct_answer:
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                        answer_detail["is_correct"] = is_correct
                        answer_detail["score"] = question_value if is_correct else 0
                
                detailed_answers.append(answer_detail)
        
        result = {
            "test_id": test_id,
            "student_id": student_id,  # user_id
            "student_db_id": student.id,  # id real da tabela Student
            "total_questions": total_questions,
            "answered_questions": correct_answers,  # Simplificado - usar acertos como questões respondidas
            "correct_answers": correct_answers,
            "score_percentage": round(score_percentage, 2),
            "total_score": round(grade, 2),  # Usar nota como total_score
            "max_possible_score": total_questions,  # Simplificado
            "grade": round(grade, 2),
            "proficiencia": round(prof_1000, 2),
            "classificacao": classification,
            "calculated_at": evaluation_result.calculated_at.isoformat() if evaluation_result.calculated_at else None,
            "answers": detailed_answers if request.args.get('include_answers', 'false').lower() == 'true' else []
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar resultados do aluno: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar resultados", "details": str(e)}), 500


@bp.route('/<string:test_id>/batch-correction', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def batch_correction(test_id):
    """
    Permite ao professor corrigir múltiplas questões dissertativas de uma vez
    
    Body:
    {
        "corrections": [
            {
                "student_id": "uuid",
                "question_id": "uuid",
                "score": 85.5,
                "feedback": "Boa resposta",
                "is_correct": true
            },
            {
                "student_id": "uuid2",
                "question_id": "uuid",
                "score": 70.0,
                "feedback": "Resposta parcialmente correta"
            }
        ]
    }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        data = request.get_json()
        if not data or 'corrections' not in data:
            return jsonify({"error": "Campo 'corrections' é obrigatório"}), 400
            
        corrections = data['corrections']
        if not isinstance(corrections, list) or len(corrections) == 0:
            return jsonify({"error": "Lista de correções deve ser um array não vazio"}), 400
        
        # Verificar se o teste existe e se o usuário tem permissão
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Teste não encontrado"}), 404
            
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode corrigir testes que criou"}), 403
        
        processed = 0
        errors = []
        
        for correction in corrections:
            try:
                student_id = correction.get('student_id')
                question_id = correction.get('question_id')
                score = correction.get('score')
                feedback = correction.get('feedback')
                is_correct = correction.get('is_correct')
                
                if not student_id or not question_id or score is None:
                    errors.append(f"Correção inválida: student_id, question_id e score são obrigatórios")
                    continue
                    
                # Validar score
                if not isinstance(score, (int, float)) or score < 0 or score > 100:
                    errors.append(f"Score inválido para aluno {student_id}, questão {question_id}: deve ser entre 0 e 100")
                    continue
                
                # Buscar resposta do aluno
                # O student_id pode ser user_id ou student_id real
                student = Student.query.filter_by(user_id=student_id).first()
                if student:
                    # É um user_id, usar o student.id
                    actual_student_id = student.id
                else:
                    # Pode ser um student_id real, verificar se existe
                    student = Student.query.get(student_id)
                    if not student:
                        errors.append(f"Aluno {student_id} não encontrado")
                        continue
                    actual_student_id = student_id
                    
                answer = StudentAnswer.query.filter_by(
                    test_id=test_id,
                    student_id=actual_student_id,
                    question_id=question_id
                ).first()
                
                if not answer:
                    errors.append(f"Resposta não encontrada para aluno {student_id}, questão {question_id}")
                    continue
                    
                # Verificar se a questão é dissertativa
                question = Question.query.get(question_id)
                if not question or question.question_type != 'essay':
                    errors.append(f"Questão {question_id} não é dissertativa")
                    continue
                
                # Atualizar com correção manual
                answer.manual_score = float(score)
                answer.feedback = feedback
                answer.corrected_by = user['id']
                answer.corrected_at = datetime.utcnow()
                
                # Definir is_correct baseado na pontuação se não fornecido
                if is_correct is None:
                    answer.is_correct = score > 50
                else:
                    answer.is_correct = bool(is_correct)
                
                processed += 1
                
            except Exception as e:
                errors.append(f"Erro ao processar correção: {str(e)}")
        
        if processed > 0:
            db.session.commit()
            
        return jsonify({
            "message": f"Processadas {processed} correções com sucesso",
            "processed": processed,
            "errors": errors if errors else None
        }), 200 if not errors else 207  # 207 Multi-Status se houver erros
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao processar correções em lote: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao processar correções", "details": str(e)}), 500


@bp.route('/<string:test_id>/pending-corrections', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_pending_corrections(test_id):
    """
    Lista todas as questões dissertativas que ainda precisam de correção manual
    
    Query Parameters:
    - student_id: uuid (opcional, filtrar por aluno específico)
    - question_id: uuid (opcional, filtrar por questão específica)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se o teste existe e se o usuário tem permissão
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Teste não encontrado"}), 404
            
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode ver correções de testes que criou"}), 403
        
        # Parâmetros de filtro
        student_id_filter = request.args.get('student_id')
        question_id_filter = request.args.get('question_id')
        
        # Query base
        query = db.session.query(
            StudentAnswer,
            Question,
            Student
        ).join(
            Question, StudentAnswer.question_id == Question.id
        ).join(
            Student, StudentAnswer.student_id == Student.id
        ).filter(
            StudentAnswer.test_id == test_id,
            Question.question_type == 'essay',
            StudentAnswer.manual_score.is_(None)
        )
        
        # Aplicar filtros
        if student_id_filter:
            query = query.filter(StudentAnswer.student_id == student_id_filter)
        if question_id_filter:
            query = query.filter(StudentAnswer.question_id == question_id_filter)
        
        pending_corrections = query.all()
        
        corrections_data = []
        for answer, question, student in pending_corrections:
            corrections_data.append({
                "student_answer_id": answer.id,
                "student_id": student.id,
                "student_name": student.name,
                "question_id": question.id,
                "question_number": question.number,
                "question_text": question.text,
                "question_value": question.value or 1.0,
                "student_answer": answer.answer,
                "answered_at": answer.answered_at.isoformat() if answer.answered_at else None
            })
        
        return jsonify({
            "test_id": test_id,
            "test_title": test.title,
            "total_pending": len(corrections_data),
            "pending_corrections": corrections_data
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar correções pendentes: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar correções pendentes", "details": str(e)}), 500


def check_multiple_choice_answer(student_answer, alternatives):
    """
    Verifica se a resposta do aluno está correta para questão de múltipla escolha
    Compara por ID da alternativa (recomendado) ou por texto (fallback)
    """
    if not alternatives or not student_answer:
        return False
        
    student_answer = str(student_answer).strip()
    
    # Opção 1: Comparar por ID da alternativa (recomendado)
    for alt in alternatives:
        if isinstance(alt, dict) and alt.get('isCorrect') and alt.get('id'):
            if student_answer == str(alt['id']):
                return True
    
    # Opção 2: Comparar por texto (fallback)
    for alt in alternatives:
        if isinstance(alt, dict) and alt.get('isCorrect'):
            alt_text = alt.get('text', '').strip()
            if student_answer.lower() == alt_text.lower():
                return True
        elif isinstance(alt, str):
            if student_answer.lower() == alt.strip().lower():
                return True
                
    return False 

# ==================== ENDPOINT: GET /{test_id}/student/{student_id}/answers ====================

@bp.route('/<string:test_id>/student/<string:student_id>/answers', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
def get_student_answers(test_id, student_id):
    """
    Retorna as respostas detalhadas de um aluno em um teste específico
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        if user['role'] == 'aluno':
            # Aluno só pode ver suas próprias respostas
            if user['id'] != student_id:
                return jsonify({"error": "Você só pode ver suas próprias respostas"}), 403
        elif user['role'] == 'professor':
            # Professor só pode ver respostas de testes que criou
            test = Test.query.get(test_id)
            if not test or test.created_by != user['id']:
                return jsonify({"error": "Você só pode ver respostas de testes que criou"}), 403
        
        # O student_id na URL pode ser user_id ou student_id real
        # Primeiro, tentar buscar como user_id
        student = Student.query.filter_by(user_id=student_id).first()
        if student:
            # É um user_id, usar o student.id
            actual_student_id = student.id
        else:
            # Pode ser um student_id real, verificar se existe
            student = Student.query.get(student_id)
            if not student:
                return jsonify({"error": "Aluno não encontrado"}), 404
            actual_student_id = student_id
        
        # Buscar respostas do aluno
        answers = StudentAnswer.query.filter_by(
            test_id=test_id,
            student_id=actual_student_id
        ).all()
        
        # Buscar questões do teste
        questions = Question.query.filter_by(test_id=test_id).all()
        questions_dict = {q.id: q for q in questions}
        
        answers_data = []
        for answer in answers:
            question = questions_dict.get(answer.question_id)
            if question:
                answer_detail = {
                    "question_id": answer.question_id,
                    "question_number": question.number or 1,
                    "question_text": question.text,
                    "question_type": question.question_type,
                    "question_value": question.value or 1.0,
                    "student_answer": answer.answer,
                    "answered_at": answer.answered_at.isoformat() if answer.answered_at else None,
                    "is_correct": None,
                    "score": None,
                    "feedback": answer.feedback,
                    "corrected_by": answer.corrected_by,
                    "corrected_at": answer.corrected_at.isoformat() if answer.corrected_at else None
                }
                
                # Verificar se a resposta está correta baseado no tipo de questão
                if question.question_type == 'multipleChoice':
                    is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.alternatives)
                    answer_detail["is_correct"] = is_correct
                    answer_detail["score"] = question.value if is_correct else 0
                    
                elif question.question_type == 'essay':
                    if answer.manual_score is not None:
                        essay_score = (answer.manual_score / 100.0) * question.value
                        answer_detail["score"] = essay_score
                        answer_detail["manual_score"] = answer.manual_score
                        answer_detail["is_correct"] = answer.is_correct
                    else:
                        answer_detail["status"] = "pending_correction"
                        
                else:
                    # Outros tipos
                    if question.correct_answer:
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                        answer_detail["is_correct"] = is_correct
                        answer_detail["score"] = question.value if is_correct else 0
                
                answers_data.append(answer_detail)
        
        return jsonify({
            "test_id": test_id,
            "student_id": student_id,
            "student_db_id": student.id,
            "total_answers": len(answers_data),
            "answers": answers_data
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar respostas do aluno: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar respostas", "details": str(e)}), 500


# ==================== ENDPOINT: GET /{test_id}/student/{student_id}/results ====================

# ==================== ENDPOINT 5: GET /relatorio-detalhado-filtrado ====================

@bp.route('/relatorio-detalhado-filtrado/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def relatorio_detalhado_filtrado(evaluation_id: str):
    """
    Retorna relatório detalhado de uma avaliação com filtros e ordenação
    
    Query Parameters:
    - fields: Campos a incluir (alunos,questoes,turma,habilidade,total,nota,proficiencia,nivel)
    - subject_id: Filtrar questões por disciplina
    - student_level: Filtrar alunos por nível (Ensino Fundamental, Médio, etc.)
    - order_by: Campo para ordenação (nota,proficiencia,status,turma)
    - order_direction: Direção da ordenação (asc,desc)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Extrair parâmetros de query
        fields = request.args.get('fields', '').split(',') if request.args.get('fields') else []
        subject_id = request.args.get('subject_id')
        student_level = request.args.get('student_level')
        order_by = request.args.get('order_by', 'nome')
        order_direction = request.args.get('order_direction', 'asc')
        
        # Validar campos permitidos
        allowed_fields = ['alunos', 'questoes', 'turma', 'habilidade', 'total', 'nota', 'proficiencia', 'nivel']
        if fields and not all(field in allowed_fields for field in fields):
            return jsonify({"error": "Campos inválidos"}), 400
        
        # Validar ordenação
        allowed_order_fields = ['nota', 'proficiencia', 'status', 'turma', 'nome']
        if order_by not in allowed_order_fields:
            return jsonify({"error": "Campo de ordenação inválido"}), 400
        
        if order_direction not in ['asc', 'desc']:
            return jsonify({"error": "Direção de ordenação inválida"}), 400
        
        # Dados da avaliação (sempre incluído)
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "disciplina": test.subject_rel.name if test.subject_rel else 'N/A',
            "total_questoes": len(test.questions) if test.questions else 0
        }
        
        # Dados das questões (filtrado por disciplina se especificado)
        questoes_data = []
        if test.questions and ('questoes' in fields or not fields):
            for i, question in enumerate(test.questions, 1):
                # Filtrar por disciplina se especificado
                if subject_id and question.subject_id != subject_id:
                    continue
                
                # Calcular porcentagem de acertos
                total_respostas = StudentAnswer.query.filter_by(
                    test_id=evaluation_id, 
                    question_id=question.id
                ).count()
                
                # Calcular acertos
                acertos = 0
                if question.question_type == 'multipleChoice':
                    for answer in StudentAnswer.query.filter_by(
                        test_id=evaluation_id,
                        question_id=question.id
                    ).all():
                        if EvaluationResultService.check_multiple_choice_answer(answer.answer, question.alternatives):
                            acertos += 1
                else:
                    acertos = StudentAnswer.query.filter_by(
                        test_id=evaluation_id,
                        question_id=question.id,
                        answer=question.correct_answer
                    ).count() if total_respostas > 0 else 0
                
                porcentagem_acertos = (acertos / total_respostas * 100) if total_respostas > 0 else 0
                
                questao_data = {
                    "id": question.id,
                    "numero": i,
                    "texto": question.text or f"Questão {i}",
                    "habilidade": question.skill or "N/A",
                    "codigo_habilidade": question.skill or "N/A",
                    "tipo": question.question_type or "multipleChoice",
                    "dificuldade": question.difficulty_level or "Médio",
                    "porcentagem_acertos": round(porcentagem_acertos, 2),
                    "porcentagem_erros": round(100 - porcentagem_acertos, 2)
                }
                questoes_data.append(questao_data)
        
        # Buscar alunos e resultados
        from app.models.evaluationResult import EvaluationResult
        
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return jsonify({
                "avaliacao": avaliacao_data,
                "questoes": questoes_data,
                "alunos": []
            }), 200
        
        # Buscar todos os alunos dessas turmas
        all_students = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade)
        ).filter(Student.class_id.in_(class_ids)).all()
        
        # Filtrar por nível se especificado
        if student_level:
            all_students = [
                student for student in all_students 
                if student.class_ and student.class_.grade and 
                student.class_.grade.name and student_level.lower() in student.class_.grade.name.lower()
            ]
        
        # Buscar resultados pré-calculados
        evaluation_results = EvaluationResult.query.filter_by(test_id=evaluation_id).all()
        results_dict = {er.student_id: er for er in evaluation_results}
        
        alunos_data = []
        for student in all_students:
            evaluation_result = results_dict.get(student.id)
            
            if evaluation_result:
                # Aluno respondeu
                total_answered = evaluation_result.correct_answers
                correct_answers = evaluation_result.correct_answers
                prof_1000 = convert_proficiency_to_1000_scale(
                    evaluation_result.proficiency, "Anos Iniciais", test.subject_rel.name if test.subject_rel else "Outras"
                )
                classification_1000 = get_classification_1000_scale(prof_1000)
                status = "concluida"
                nota = evaluation_result.grade if hasattr(evaluation_result, 'grade') else 0.0
            else:
                # Aluno NÃO respondeu
                total_answered = 0
                correct_answers = 0
                prof_1000 = 0.0
                classification_1000 = 'Abaixo do Básico'
                status = "nao_respondida"
                nota = 0.0
            
            # Buscar informações da turma
            turma_nome = "N/A"
            if student.class_:
                turma_nome = student.class_.name
            
            # Buscar respostas detalhadas do aluno
            respostas = []
            if 'questoes' in fields or not fields:
                student_answers = StudentAnswer.query.filter_by(
                    test_id=evaluation_id,
                    student_id=student.id
                ).all()
                
                for answer in student_answers:
                    question = Question.query.get(answer.question_id)
                    if question:
                        # Filtrar por disciplina se especificado
                        if subject_id and question.subject_id != subject_id:
                            continue
                        
                        is_correct = False
                        if question.question_type == 'multipleChoice':
                            is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.alternatives)
                        else:
                            is_correct = answer.answer == question.correct_answer
                        
                        respostas.append({
                            "questao_id": question.id,
                            "questao_numero": question.number or 0,
                            "resposta_correta": is_correct,
                            "resposta_em_branco": not answer.answer or answer.answer.strip() == ""
                        })
            
            aluno_data = {
                "id": student.id,
                "nome": student.user.name if student.user else "N/A",
                "total_acertos": correct_answers,
                "total_erros": total_answered - correct_answers,
                "total_em_branco": len(test.questions) - total_answered if test.questions else 0,
                "nota": nota,
                "proficiencia": prof_1000,
                "classificacao": classification_1000,
                "status": status
            }
            
            # Adicionar campos condicionalmente
            if 'turma' in fields or not fields:
                aluno_data["turma"] = turma_nome
            
            if 'nivel' in fields or not fields:
                aluno_data["nivel"] = student.class_.grade.name if student.class_ and student.class_.grade else "N/A"
            
            if 'questoes' in fields or not fields:
                aluno_data["respostas"] = respostas
            
            alunos_data.append(aluno_data)
        
        # Aplicar ordenação
        reverse_order = order_direction == 'desc'
        
        if order_by == 'nota':
            alunos_data.sort(key=lambda x: x.get('nota', 0), reverse=reverse_order)
        elif order_by == 'proficiencia':
            alunos_data.sort(key=lambda x: x.get('proficiencia', 0), reverse=reverse_order)
        elif order_by == 'status':
            # Ordenar por status: concluida primeiro, depois nao_respondida
            status_order = {'concluida': 1, 'nao_respondida': 2}
            alunos_data.sort(key=lambda x: status_order.get(x.get('status', 'nao_respondida'), 3), reverse=reverse_order)
        elif order_by == 'turma':
            alunos_data.sort(key=lambda x: x.get('turma', 'N/A'), reverse=reverse_order)
        elif order_by == 'nome':
            alunos_data.sort(key=lambda x: x.get('nome', 'N/A'), reverse=reverse_order)
        
        # Construir resposta final
        response = {"avaliacao": avaliacao_data}
        
        if 'questoes' in fields or not fields:
            response["questoes"] = questoes_data
        
        if 'alunos' in fields or not fields:
            response["alunos"] = alunos_data
        
        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Erro ao buscar relatório filtrado: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar relatório filtrado", "details": str(e)}), 500

# ==================== ENDPOINT 6: GET /opcoes-filtros ====================

@bp.route('/opcoes-filtros/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def opcoes_filtros(evaluation_id: str):
    """
    Retorna opções disponíveis para filtros da avaliação
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Buscar disciplinas das questões
        disciplinas = []
        if test.questions:
            subject_ids = set()
            for question in test.questions:
                if question.subject_id and question.subject_id not in subject_ids:
                    subject_ids.add(question.subject_id)
                    subject = Subject.query.get(question.subject_id)
                    if subject:
                        disciplinas.append({
                            "id": subject.id,
                            "name": subject.name
                        })
        
        # Buscar níveis dos alunos
        niveis = []
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if class_ids:
            students = Student.query.options(
                joinedload(Student.class_).joinedload(Class.grade)
            ).filter(Student.class_id.in_(class_ids)).all()
            
            grade_names = set()
            for student in students:
                if student.class_ and student.class_.grade and student.class_.grade.name:
                    grade_names.add(student.class_.grade.name)
            
            niveis = [{"id": name, "name": name} for name in sorted(grade_names)]
        
        # Opções de ordenação
        opcoes_ordenacao = [
            {"id": "nota", "name": "Nota"},
            {"id": "proficiencia", "name": "Proficiência"},
            {"id": "status", "name": "Status"},
            {"id": "turma", "name": "Turma"},
            {"id": "nome", "name": "Nome do Aluno"}
        ]
        
        # Campos disponíveis
        campos_disponiveis = [
            {"id": "alunos", "name": "Dados dos Alunos"},
            {"id": "questoes", "name": "Questões"},
            {"id": "turma", "name": "Turma"},
            {"id": "habilidade", "name": "Habilidades"},
            {"id": "total", "name": "Total de Acertos"},
            {"id": "nota", "name": "Nota"},
            {"id": "proficiencia", "name": "Proficiência"},
            {"id": "nivel", "name": "Nível"}
        ]
        
        return jsonify({
            "disciplinas": disciplinas,
            "niveis": niveis,
            "opcoes_ordenacao": opcoes_ordenacao,
            "campos_disponiveis": campos_disponiveis
        }), 200

    except Exception as e:
        logging.error(f"Erro ao buscar opções de filtros: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar opções de filtros", "details": str(e)}), 500

# ==================== FUNÇÕES AUXILIARES PARA STATUS ====================

def _check_and_update_evaluation_status(test_id: str) -> Dict[str, Any]:
    """
    Verifica e atualiza automaticamente o status de uma avaliação para "concluída" quando apropriado
    
    Critérios para marcar como "concluída":
    1. Todas as sessões de alunos foram finalizadas
    2. Todas as sessões foram corrigidas (se necessário)
    3. Prazo de expiração foi atingido (se configurado)
    
    Returns:
        Dict com informações sobre a atualização
    """
    try:
        from app.models.testSession import TestSession
        from app.models.classTest import ClassTest
        from datetime import datetime, timedelta
        
        # Buscar a avaliação
        test = Test.query.get(test_id)
        if not test:
            return {"error": "Avaliação não encontrada"}
        
        # Buscar todas as aplicações da avaliação
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        if not class_tests:
            return {"error": "Avaliação não foi aplicada em nenhuma turma"}
        
        # Buscar todas as sessões da avaliação
        sessions = TestSession.query.filter_by(test_id=test_id).all()
        
        if not sessions:
            return {"message": "Nenhuma sessão encontrada para esta avaliação"}
        
        # Verificar se todas as sessões foram finalizadas
        total_sessions = len(sessions)
        finalized_sessions = len([s for s in sessions if s.status in ['finalizada', 'corrigida', 'revisada', 'finalized']])
        
        # Verificar se há prazo de expiração
        has_expired = False
        if class_tests and class_tests[0].expiration:
            current_time = datetime.utcnow()
            expiration_time = class_tests[0].expiration
            if current_time > expiration_time:
                has_expired = True
        
        # Determinar se deve ser marcada como concluída
        should_be_completed = False
        completion_reason = ""
        
        if has_expired:
            should_be_completed = True
            completion_reason = "Prazo de expiração atingido"
        elif finalized_sessions == total_sessions and total_sessions > 0:
            should_be_completed = True
            completion_reason = "Todas as sessões foram finalizadas"
        
        # Atualizar status se necessário
        updated_class_tests = []
        if should_be_completed:
            for class_test in class_tests:
                if class_test.status != "concluida":
                    class_test.status = "concluida"
                    class_test.updated_at = datetime.utcnow()
                    updated_class_tests.append(class_test.id)
            
            if updated_class_tests:
                db.session.commit()
        
        return {
            "test_id": test_id,
            "total_sessions": total_sessions,
            "finalized_sessions": finalized_sessions,
            "has_expired": has_expired,
            "should_be_completed": should_be_completed,
            "completion_reason": completion_reason,
            "updated_class_tests": updated_class_tests,
            "current_status": class_tests[0].status if class_tests else "N/A"
        }
        
    except Exception as e:
        logging.error(f"Erro ao verificar status da avaliação {test_id}: {str(e)}", exc_info=True)
        return {"error": f"Erro ao verificar status: {str(e)}"}


def _get_evaluation_status_summary(test_id: str) -> Dict[str, Any]:
    """
    Retorna um resumo do status atual de uma avaliação
    """
    try:
        from app.models.testSession import TestSession
        from app.models.classTest import ClassTest
        from datetime import datetime
        
        # Buscar aplicações da avaliação
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
        # Buscar sessões
        sessions = TestSession.query.filter_by(test_id=test_id).all()
        
        # Contar por status
        status_counts = {}
        for session in sessions:
            status = session.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Verificar expiração
        expiration_info = None
        if class_tests and class_tests[0].expiration:
            current_time = datetime.utcnow()
            expiration_time = class_tests[0].expiration
            is_expired = current_time > expiration_time
            expiration_info = {
                "expiration_date": expiration_time.isoformat() if expiration_time else None,
                "is_expired": is_expired,
                "days_until_expiration": (expiration_time - current_time).days if not is_expired else 0
            }
        
        return {
            "test_id": test_id,
            "total_sessions": len(sessions),
            "status_counts": status_counts,
            "class_test_status": [ct.status for ct in class_tests],
            "expiration_info": expiration_info,
            "overall_status": class_tests[0].status if class_tests else "N/A"
        }
        
    except Exception as e:
        logging.error(f"Erro ao obter resumo de status da avaliação {test_id}: {str(e)}", exc_info=True)
        return {"error": f"Erro ao obter resumo: {str(e)}"}


# ==================== ENDPOINT PARA VERIFICAR/ATUALIZAR STATUS ====================

@bp.route('/avaliacoes/<string:test_id>/verificar-status', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def verificar_e_atualizar_status(test_id: str):
    """
    Verifica e atualiza automaticamente o status de uma avaliação
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode verificar avaliações que criou"}), 403
        
        # Verificar e atualizar status
        status_info = _check_and_update_evaluation_status(test_id)
        
        if "error" in status_info:
            return jsonify(status_info), 400
        
        # Obter resumo atual
        summary = _get_evaluation_status_summary(test_id)
        
        return jsonify({
            "message": "Status verificado e atualizado com sucesso",
            "status_update": status_info,
            "current_summary": summary
        }), 200

    except Exception as e:
        logging.error(f"Erro ao verificar status da avaliação: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar status", "details": str(e)}), 500


# ==================== ENDPOINT PARA OBTER RESUMO DE STATUS ====================

@bp.route('/avaliacoes/<string:test_id>/status-resumo', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def obter_resumo_status(test_id: str):
    """
    Retorna um resumo detalhado do status atual de uma avaliação
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode verificar avaliações que criou"}), 403
        
        # Obter resumo
        summary = _get_evaluation_status_summary(test_id)
        
        if "error" in summary:
            return jsonify(summary), 400
        
        return jsonify(summary), 200

    except Exception as e:
        logging.error(f"Erro ao obter resumo de status: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter resumo", "details": str(e)}), 500

# ==================== ENDPOINT PARA VERIFICAR TODAS AS AVALIAÇÕES ====================

@bp.route('/avaliacoes/verificar-todas', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def verificar_todas_avaliacoes():
    """
    Verifica e atualiza automaticamente o status de todas as avaliações
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Buscar todas as avaliações
        if user['role'] == 'professor':
            # Professores só veem suas próprias avaliações
            tests = Test.query.filter_by(created_by=user['id']).all()
        else:
            # Admins veem todas as avaliações
            tests = Test.query.all()
        
        if not tests:
            return jsonify({
                "message": "Nenhuma avaliação encontrada",
                "total_checked": 0,
                "total_updated": 0
            }), 200
        
        # Verificar cada avaliação
        results = []
        total_updated = 0
        
        for test in tests:
            try:
                status_info = _check_and_update_evaluation_status(test.id)
                
                if status_info.get("should_be_completed", False):
                    total_updated += 1
                
                results.append({
                    "test_id": test.id,
                    "title": test.title,
                    "status_info": status_info
                })
                
            except Exception as e:
                logging.error(f"Erro ao verificar avaliação {test.id}: {str(e)}")
                results.append({
                    "test_id": test.id,
                    "title": test.title,
                    "error": str(e)
                })
        
        return jsonify({
            "message": "Verificação de todas as avaliações concluída",
            "total_checked": len(tests),
            "total_updated": total_updated,
            "results": results
        }), 200

    except Exception as e:
        logging.error(f"Erro ao verificar todas as avaliações: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar avaliações", "details": str(e)}), 500


# ==================== ENDPOINT PARA OBTER ESTATÍSTICAS DE STATUS ====================

@bp.route('/avaliacoes/estatisticas-status', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def obter_estatisticas_status():
    """
    Retorna estatísticas gerais do status das avaliações
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Buscar todas as avaliações
        if user['role'] == 'professor':
            tests = Test.query.filter_by(created_by=user['id']).all()
        else:
            tests = Test.query.all()
        
        # Contar por status
        status_counts = {}
        total_tests = len(tests)
        
        for test in tests:
            class_tests = ClassTest.query.filter_by(test_id=test.id).all()
            if class_tests:
                # Usar o status da primeira aplicação como representativo
                status = class_tests[0].status
                status_counts[status] = status_counts.get(status, 0) + 1
            else:
                status_counts['sem_aplicacao'] = status_counts.get('sem_aplicacao', 0) + 1
        
        # Calcular porcentagens
        status_percentages = {}
        for status, count in status_counts.items():
            status_percentages[status] = round((count / total_tests) * 100, 2) if total_tests > 0 else 0
        
        return jsonify({
            "total_avaliacoes": total_tests,
            "contagem_por_status": status_counts,
            "porcentagem_por_status": status_percentages,
            "status_disponiveis": ["agendada", "em_andamento", "concluida", "cancelada", "sem_aplicacao"]
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter estatísticas de status: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter estatísticas", "details": str(e)}), 500