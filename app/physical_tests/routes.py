# -*- coding: utf-8 -*-
"""
Rotas para formulários físicos
Sistema de correção: AnswerSheetCorrectionNewGrid (novo pipeline OMR robusto)
Suporta correção única (síncrona) e em lote (assíncrona com polling)
"""

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.decorators.role_required import role_required, get_current_user_from_token as get_user_for_permission_check
from app.decorators import requires_city_context
from app import db
from app.models.test import Test
from app.models.student import Student
from app.models.user import User
from app.models.evaluationResult import EvaluationResult
from app.models.physicalTestForm import PhysicalTestForm
from app.models.classTest import ClassTest
from app.models.studentClass import Class
from app.models.school import School
from app.models.grades import Grade
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.physical_tests.pdf_generator import PhysicalTestPDFGenerator
from app.physical_tests.form_service import PhysicalTestFormService
from app.services.cartao_resposta.correction_new_grid import AnswerSheetCorrectionNewGrid  # NOVO SISTEMA DE CORREÇÃO
from app.services.progress_store import (
    create_job, update_item_processing, update_item_done,
    update_item_error, complete_job, get_job
)
from typing import Dict, List, Optional
import tempfile
import threading
import uuid
import logging
import base64
import os
import json

bp = Blueprint('physical_tests', __name__, url_prefix='/physical-tests')


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def _generate_complete_structure(num_questions: int, use_blocks: bool,
                                 blocks_config: Dict, questions_options: Dict = None) -> Dict:
    """
    Gera estrutura completa de questões e alternativas por bloco
    Formato (será salvo em blocks_config['topology']):
    {
        "blocks": [
            {
                "block_id": 1,
                "questions": [
                    {"q": 1, "alternatives": ["A", "B"]},
                    {"q": 2, "alternatives": ["A", "B", "C", "D"]},
                    ...
                ]
            },
            ...
        ]
    }
    """
    # Processar questions_options: garantir formato correto
    questions_map = {}
    if questions_options:
        for key, value in questions_options.items():
            try:
                q_num = int(key)
                if isinstance(value, list) and len(value) >= 2:
                    questions_map[q_num] = value
                else:
                    questions_map[q_num] = ['A', 'B', 'C', 'D']
            except (ValueError, TypeError):
                continue
    
    # Se questions_map vazio, preencher com padrão
    if not questions_map:
        for q in range(1, num_questions + 1):
            questions_map[q] = ['A', 'B', 'C', 'D']
    else:
        # Garantir que todas questões existam
        for q in range(1, num_questions + 1):
            if q not in questions_map:
                questions_map[q] = ['A', 'B', 'C', 'D']
    
    # Estrutura topology (sem use_blocks, apenas blocks)
    topology = {}
    
    if use_blocks:
        # Organizar por blocos
        num_blocks = blocks_config.get('num_blocks', 1)
        questions_per_block = blocks_config.get('questions_per_block', 12)
        
        blocks = []
        for block_num in range(1, num_blocks + 1):
            start_question = (block_num - 1) * questions_per_block + 1
            end_question = min(block_num * questions_per_block, num_questions)
            
            questions = []
            for q_num in range(start_question, end_question + 1):
                alternatives = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
                questions.append({
                    "q": q_num,
                    "alternatives": alternatives
                })
            
            blocks.append({
                "block_id": block_num,
                "questions": questions
            })
        
        topology["blocks"] = blocks
    else:
        # Sem blocos: um único bloco com todas questões
        questions = []
        for q_num in range(1, num_questions + 1):
            alternatives = questions_map.get(q_num, ['A', 'B', 'C', 'D'])
            questions.append({
                "q": q_num,
                "alternatives": alternatives
            })
        
        topology["blocks"] = [{
            "block_id": 1,
            "questions": questions
        }]
    
    return topology


def _extrair_respostas_corretas(test_id: str) -> Dict[int, str]:
    """
    Extrai respostas corretas das questões da prova e converte para formato {1: "A", 2: "B", ...}
    
    Args:
        test_id: ID da prova
        
    Returns:
        Dict com número da questão (order) como chave e letra correta como valor
    """
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    correct_answers = {}
    
    # Buscar questões da prova ordenadas por TestQuestion.order
    test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
    if not test_questions:
        logging.warning(f"Nenhuma questão encontrada para prova {test_id}")
        return correct_answers
    
    # Buscar questões completas
    question_ids = [tq.question_id for tq in test_questions]
    questions = Question.query.filter(Question.id.in_(question_ids)).all()
    questions_dict = {q.id: q for q in questions}
    
    # Para cada questão, converter correct_answer para letra
    for tq in test_questions:
        question = questions_dict.get(tq.question_id)
        if not question or not question.correct_answer:
            logging.warning(f"Questão {tq.question_id} não encontrada ou sem correct_answer")
            continue
        
        question_num = tq.order  # Número da questão na prova (baseado em order)
        correct_answer = str(question.correct_answer).strip()
        letter = None
        
        # Caso 1: Já é uma letra (A, B, C, D...)
        if correct_answer.upper() in letters:
            letter = correct_answer.upper()
        
        # Caso 2: É um ID do tipo "option-0", "option-1", etc.
        elif correct_answer.startswith('option-'):
            try:
                index = int(correct_answer.split('-')[1])
                if 0 <= index < len(letters):
                    letter = letters[index]
            except (ValueError, IndexError):
                pass
        
        # Caso 3: É um UUID ou outro ID - buscar nas alternativas
        if not letter and question.alternatives:
            alternatives = question.alternatives
            if isinstance(alternatives, str):
                try:
                    alternatives = json.loads(alternatives)
                except:
                    alternatives = []
            
            if isinstance(alternatives, list):
                for idx, alt in enumerate(alternatives):
                    if isinstance(alt, dict):
                        alt_id = alt.get('id', '')
                        if alt_id == correct_answer:
                            if idx < len(letters):
                                letter = letters[idx]
                                break
                    elif isinstance(alt, str):
                        # Se alternativa é string e correct_answer também, comparar
                        if correct_answer.lower() == alt.strip().lower():
                            if idx < len(letters):
                                letter = letters[idx]
                                break
        
        # Caso 4: É texto - buscar nas alternativas por texto
        if not letter and question.alternatives:
            alternatives = question.alternatives
            if isinstance(alternatives, str):
                try:
                    alternatives = json.loads(alternatives)
                except:
                    alternatives = []
            
            if isinstance(alternatives, list):
                for idx, alt in enumerate(alternatives):
                    alt_text = ''
                    if isinstance(alt, dict):
                        alt_text = alt.get('text', alt.get('answer', ''))
                    elif isinstance(alt, str):
                        alt_text = alt
                    
                    if alt_text and correct_answer.lower() == alt_text.strip().lower():
                        if idx < len(letters):
                            letter = letters[idx]
                            break
        
        if letter:
            correct_answers[question_num] = letter
        else:
            logging.warning(f"Questão {question_num} (ID: {question.id}): Não foi possível converter correct_answer '{correct_answer}' para letra")
    
    return correct_answers


def _extrair_questions_options(test_id: str) -> Dict[int, List[str]]:
    """
    Extrai alternativas disponíveis por questão
    Retorna: {1: ["A", "B", "C"], 2: ["A", "B", "C", "D"], ...}
    
    Args:
        test_id: ID da prova
        
    Returns:
        Dict com número da questão como chave e lista de letras como valor
    """
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    questions_options = {}
    
    # Buscar questões da prova ordenadas por TestQuestion.order
    test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
    if not test_questions:
        return questions_options
    
    # Buscar questões completas
    question_ids = [tq.question_id for tq in test_questions]
    questions = Question.query.filter(Question.id.in_(question_ids)).all()
    questions_dict = {q.id: q for q in questions}
    
    # Para cada questão, extrair alternativas
    for tq in test_questions:
        question = questions_dict.get(tq.question_id)
        if not question:
            continue
        
        question_num = tq.order
        alternatives_list = []
        
        if question.alternatives:
            alternatives = question.alternatives
            if isinstance(alternatives, str):
                try:
                    alternatives = json.loads(alternatives)
                except:
                    alternatives = []
            
            if isinstance(alternatives, list):
                for idx, alt in enumerate(alternatives):
                    if idx < len(letters):
                        alternatives_list.append(letters[idx])
        else:
            # Se não tem alternativas definidas, usar padrão A, B, C, D
            alternatives_list = ['A', 'B', 'C', 'D']
        
        # Garantir pelo menos 2 alternativas
        if len(alternatives_list) < 2:
            alternatives_list = ['A', 'B', 'C', 'D']
        
        questions_options[question_num] = alternatives_list
    
    return questions_options


def get_current_user_from_token():
    """Extrai informações do usuário do token JWT"""
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return None
        
        user = User.query.get(user_id)
        if not user:
            return None
        
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role
        }
    except Exception as e:
        print(f"❌ Erro ao extrair usuário do token: {str(e)}")
        return None

# ============================================================================
# ROTA DE ESCOPO DA AVALIAÇÃO (para montar filtros no front)
# ============================================================================

@bp.route('/test/<string:test_id>/scope', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def get_physical_test_scope(test_id):
    """
    Retorna em quais escolas, séries e turmas a avaliação foi aplicada (ClassTest).
    Usado pelo front para montar filtros e o usuário escolher para o quê gerar formulários.

    Returns:
        200 com:
        - test_id, test_title
        - schools: [{ id, name, grades: [{ id, name, classes: [{ id, name }] }] }]
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401

        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Prova não encontrada"}), 404

        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode ver escopo de suas próprias provas"}), 403

        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        if not class_tests:
            return jsonify({
                "test_id": test_id,
                "test_title": test.title,
                "schools": []
            }), 200

        class_ids = [ct.class_id for ct in class_tests]
        classes = Class.query.filter(Class.id.in_(class_ids)).all()

        # Montar árvore: escola -> série -> turmas (apenas turmas com ClassTest para este test_id)
        schools_map = {}
        for c in classes:
            school_id = str(c.school_id) if c.school_id else None
            grade_id = str(c.grade_id) if c.grade_id else None
            if not school_id:
                continue
            school = School.query.get(school_id)
            school_name = school.name if school else str(school_id)
            if school_id not in schools_map:
                schools_map[school_id] = {"id": school_id, "name": school_name, "grades": {}}
            grades_map = schools_map[school_id]["grades"]
            if grade_id not in grades_map:
                grade = Grade.query.get(grade_id) if grade_id else None
                grade_name = grade.name if grade else str(grade_id)
                grades_map[grade_id] = {"id": grade_id, "name": grade_name, "classes": []}
            grades_map[grade_id]["classes"].append({"id": str(c.id), "name": c.name or str(c.id)})

        schools = []
        for s in schools_map.values():
            grades_list = [{"id": g["id"], "name": g["name"], "classes": g["classes"]} for g in s["grades"].values()]
            schools.append({"id": s["id"], "name": s["name"], "grades": grades_list})

        return jsonify({
            "test_id": test_id,
            "test_title": test.title,
            "schools": schools
        }), 200
    except Exception as e:
        logging.error(f"Erro ao obter escopo da prova física: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================================================
# ROTAS DE GERAÇÃO DE FORMULÁRIOS
# ============================================================================

@bp.route('/test/<string:test_id>/generate-forms', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def generate_physical_forms(test_id):
    """
    Dispara geração ASSÍNCRONA de formulários físicos usando Celery.

    Fluxo atual: Arch4 + PDF Overlay — 1× WeasyPrint (prova base) + 1× WeasyPrint (template OMR)
    + por aluno apenas overlay ReportLab (nome, escola, turma, QR) aplicado sobre o template.
    A geração é feita em background para evitar timeout em turmas grandes.
    O frontend deve fazer polling na rota /task/<task_id>/status para acompanhar o progresso.
    
    Body:
        - force_regenerate (opcional): Forçar regeneração mesmo se já existirem formulários (padrão: false)
        - school_ids (opcional): Lista de IDs de escolas para gerar apenas para essas escolas
        - grade_ids (opcional): Lista de IDs de séries para gerar apenas para essas séries
        - class_ids (opcional): Lista de IDs de turmas para gerar apenas para essas turmas
        Filtros são aplicados em cascata (escola -> série -> turma). Se não enviar nenhum, gera para todas as turmas aplicadas.
    
    Returns:
        202 Accepted com:
        - status: "processing"
        - task_id: ID da task Celery para polling
        - polling_url: URL para verificar status
        - test_id: ID da prova
        - test_title: Título da prova
    
    Example Response:
        {
            "status": "processing",
            "message": "Formulários sendo gerados em background",
            "task_id": "abc-123-def-456",
            "test_id": "test-uuid",
            "test_title": "Avaliação de Matemática",
            "polling_url": "/physical-tests/task/abc-123-def-456/status"
        }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Verificar se a prova existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Prova não encontrada"}), 404
        
        # Verificar permissões do professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode gerar formulários para suas próprias provas"}), 403
        
        # Obter dados da requisição
        try:
            data = request.get_json() or {}
        except:
            data = {}
        force_regenerate = data.get('force_regenerate', False)
        school_ids = data.get('school_ids')  # opcional: list
        grade_ids = data.get('grade_ids')  # opcional: list
        class_ids = data.get('class_ids')  # opcional: list
        if school_ids is not None and not isinstance(school_ids, list):
            school_ids = [school_ids] if school_ids else []
        if grade_ids is not None and not isinstance(grade_ids, list):
            grade_ids = [grade_ids] if grade_ids else []
        if class_ids is not None and not isinstance(class_ids, list):
            class_ids = [class_ids] if class_ids else []

        # Extrair blocks_config do payload
        blocks_config = data.get('blocks_config')
        print(f"[ROTA] ========== INÍCIO GERAÇÃO FORMULÁRIOS ==========")
        print(f"[ROTA] test_id: {test_id}")
        print(f"[ROTA] Payload recebido: {data}")
        print(f"[ROTA] blocks_config recebido: {blocks_config}")
        
        if not blocks_config:
            # Se não vier como objeto, montar a partir dos parâmetros individuais
            blocks_config = {
                'use_blocks': data.get('use_blocks', False),
                'num_blocks': data.get('num_blocks', 1),
                'questions_per_block': data.get('questions_per_block', 12),
                'separate_by_subject': data.get('separate_by_subject', False)
            }
            print(f"[ROTA] blocks_config montado a partir de parâmetros: {blocks_config}")
        
        # ✅ OBTER CONTEXTO DA CIDADE
        from app.decorators.tenant_required import get_current_tenant_context
        context = get_current_tenant_context()
        city_id = context.city_id if context else None
        
        if not city_id:
            logging.error("❌ Contexto de cidade não encontrado")
            return jsonify({"error": "City context not found"}), 500
        
        # ✅ DISPARAR TASK CELERY (assíncrono)
        from app.physical_tests.tasks import generate_physical_forms_async
        
        print(f"[ROTA] 🚀 Disparando task Celery com blocks_config: {blocks_config}, city_id: {city_id}")
        logging.info(f"🚀 Disparando task Celery para geração de formulários: test_id={test_id}, city_id={city_id}, blocks_config={blocks_config}")
        
        task = generate_physical_forms_async.delay(
            test_id=test_id,
            city_id=city_id,
            force_regenerate=force_regenerate,
            blocks_config=blocks_config,
            school_ids=school_ids,
            grade_ids=grade_ids,
            class_ids=class_ids
        )
        
        print(f"[ROTA] ✅ Task disparada: task_id={task.id}")
        
        # ✅ RETORNA IMEDIATAMENTE (não espera a geração)
        logging.info(f"✅ Task disparada com sucesso: task_id={task.id}")
        
        return jsonify({
            "status": "processing",
            "message": "Formulários sendo gerados em background. Use o task_id para verificar o status.",
            "task_id": task.id,
            "test_id": test_id,
            "test_title": test.title,
            "polling_url": f"/physical-tests/task/{task.id}/status"
        }), 202  # 202 Accepted
        
        # OBS: Todo código abaixo foi movido para a task Celery e não é mais executado aqui
        # Mantido comentado para referência
        
        """
        # Extrair blocks_config do body
        blocks_config = data.get('blocks_config')
        if not blocks_config:
            # Se não vier como objeto, montar a partir dos parâmetros individuais
            blocks_config = {
                'use_blocks': data.get('use_blocks', False),
                'num_blocks': data.get('num_blocks', 1),
                'questions_per_block': data.get('questions_per_block', 12),
                'separate_by_subject': data.get('separate_by_subject', False)
            }
        
        # Buscar questões da prova
        from app.models.subject import Subject
        
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
        questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
        
        if not questions:
            return jsonify({"error": "Nenhuma questão encontrada para esta prova"}), 400
        
        num_questions = len(questions)
        
        # Extrair respostas corretas automaticamente das questões
        correct_answers = _extrair_respostas_corretas(test_id)
        if not correct_answers:
            return jsonify({"error": "Não foi possível extrair respostas corretas das questões. Verifique se todas as questões têm correct_answer definido."}), 400
        
        # Extrair alternativas por questão automaticamente
        questions_options = _extrair_questions_options(test_id)
        
        # Validar blocks_config
        use_blocks = blocks_config.get('use_blocks', False)
        if use_blocks:
            if 'num_blocks' not in blocks_config:
                blocks_config['num_blocks'] = 1
            if 'questions_per_block' not in blocks_config:
                blocks_config['questions_per_block'] = 12
        
        # Gerar estrutura completa (topology)
        complete_structure = _generate_complete_structure(
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            questions_options=questions_options
        )
        
        # Adicionar topology ao blocks_config
        blocks_config['topology'] = complete_structure
        
        # Buscar alunos das turmas que aplicaram a prova
        from app.models.studentClass import Class
        from app.models.school import School
        
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        if not class_tests:
            return jsonify({"error": "A prova não foi aplicada em nenhuma turma"}), 400
        
        # Usar primeira turma para metadados (escola, município, etc.)
        first_class_test = class_tests[0]
        class_id = first_class_test.class_id
        
        # Buscar informações da turma e escola
        class_obj = Class.query.get(class_id)
        school_id = None
        school_name = ''
        municipality = ''
        state = ''
        
        if class_obj:
            if class_obj.school_id:
                school = School.query.get(class_obj.school_id)
                if school:
                    school_id = school.id
                    school_name = school.name or ''
                    # Buscar município e estado através da cidade
                    if school.city_id:
                        from app.models.city import City
                        city = City.query.get(school.city_id)
                        if city:
                            municipality = city.name or ''
                            # City tem campo 'state' como string
                            if city.state:
                                state = city.state
        
        class_ids = [ct.class_id for ct in class_tests]
        students = Student.query.filter(Student.class_id.in_(class_ids)).all()
        
        if not students:
            return jsonify({"error": "Nenhum aluno encontrado nas turmas que aplicaram a prova"}), 400
        
        # Buscar dados dinâmicos das tabelas
        education_stage_name = None
        course_name = None
        
        # Buscar education_stage através do grade
        if test.grade and test.grade.education_stage_id:
            from app.models.educationStage import EducationStage
            education_stage = EducationStage.query.get(test.grade.education_stage_id)
            if education_stage:
                education_stage_name = education_stage.name
        
        # Buscar course (se for um ID de education_stage)
        if test.course:
            from app.models.educationStage import EducationStage
            course = EducationStage.query.get(test.course)
            if course:
                course_name = course.name
        
        # Preparar dados para o gerador
        test_data = {
            'id': test.id,
            'title': test.title,
            'description': test.description,
            'course': test.course,
            'course_name': course_name,
            'education_stage_id': test.grade.education_stage_id if test.grade else None,
            'education_stage_name': education_stage_name,
            'grade_name': test.grade.name if test.grade else '9° ANO',
            'blocks_config': blocks_config  # Incluir blocks_config do body
        }
        
        students_data = []
        for student in students:
            students_data.append({
                'id': student.id,
                'nome': student.name
            })
        
        questions_data = []
        for question in questions:
            # Buscar disciplina da questão
            subject = Subject.query.get(question.subject_id) if question.subject_id else None
            
            # Buscar código da habilidade
            skill_code = None
            if question.skill:
                from app.models.skill import Skill
                skill = Skill.query.get(question.skill)
                if skill:
                    skill_code = skill.code
            
            # Extrair IDs das alternativas
            alternative_ids = []
            if question.alternatives:
                try:
                    import json
                    alternatives_json = json.loads(question.alternatives) if isinstance(question.alternatives, str) else question.alternatives
                    alternative_ids = [alt.get('id', '') for alt in alternatives_json if alt.get('id')]
                except:
                    alternative_ids = []
            
            question_data = {
                'id': question.id,
                'title': question.title,
                'text': question.text,
                'formatted_text': question.formatted_text,
                'secondstatement': question.secondstatement,
                'alternatives': question.alternatives or [],
                'alternative_ids': alternative_ids,  # IDs das alternativas para o formulário
                'skills': [skill_code] if skill_code else [],
                'subject': {
                    'id': subject.id,
                    'name': subject.name
                } if subject else None
            }
            questions_data.append(question_data)
        
        # Criar ou atualizar AnswerSheetGabarito para esta prova
        # Verificar se já existe gabarito para esta prova
        existing_gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
        
        if existing_gabarito:
            # Atualizar gabarito existente
            existing_gabarito.num_questions = num_questions
            existing_gabarito.use_blocks = use_blocks
            existing_gabarito.blocks_config = blocks_config
            existing_gabarito.correct_answers = correct_answers
            existing_gabarito.class_id = class_id
            existing_gabarito.school_id = str(school_id) if school_id else None
            existing_gabarito.school_name = school_name
            existing_gabarito.municipality = municipality
            existing_gabarito.state = state
            existing_gabarito.grade_name = test.grade.name if test.grade else ''
            existing_gabarito.title = test.title
            gabarito = existing_gabarito
            logging.info(f"✅ Gabarito atualizado para prova {test_id}")
        else:
            # Criar novo gabarito
            gabarito = AnswerSheetGabarito(
                test_id=test_id,
                class_id=class_id,
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                correct_answers=correct_answers,
                title=test.title,
                created_by=str(user['id']) if user.get('id') else None,
                school_id=str(school_id) if school_id else None,
                school_name=school_name,
                municipality=municipality,
                state=state,
                grade_name=test.grade.name if test.grade else ''
            )
            db.session.add(gabarito)
            logging.info(f"✅ Novo gabarito criado para prova {test_id}")
        
        db.session.commit()
        logging.info(f"✅ Gabarito salvo: {len(correct_answers)} respostas corretas, {num_questions} questões")
        
        # Usar PhysicalTestFormService para gerar formulários
        logging.info(f"GERANDO FORMULARIOS PARA {len(students_data)} ALUNOS...")
        
        form_service = PhysicalTestFormService()
        
        # Gerar formulários usando o serviço
        with tempfile.TemporaryDirectory() as temp_dir:
            result = form_service.generate_physical_forms(
                test_id=test_id,
                output_dir=temp_dir,
                test_data=test_data  # Passar test_data com blocks_config
            )
            
            if result.get('success'):
                logging.info(f"SUCESSO: {result.get('generated_forms', 0)} formularios gerados")
                
                # Buscar formulários gerados para retornar
                forms = form_service.get_physical_forms_by_test(test_id)
                formularios_gerados = []
                
                for form in forms:
                    formularios_gerados.append({
                        'student_id': form['student_id'],
                        'student_name': form['student_name'],
                        'form_id': form['id'],
                        'form_type': form['form_type'],
                        'created_at': form['generated_at']
                    })
                
                return jsonify({
                    "message": f"Formulários gerados com sucesso para {len(formularios_gerados)} alunos",
                    "test_id": test_id,
                    "test_title": test.title,
                    "total_questions": num_questions,
                    "total_students": len(students_data),
                    "generated_forms": len(formularios_gerados),
                    "gabarito_id": str(gabarito.id),
                    "forms": formularios_gerados
                }), 200
            else:
                print(f"ERRO: {result.get('error')}")
                return jsonify({"error": result.get('error', 'Erro ao gerar formulários')}), 500
        """
        
    except Exception as e:
        logging.error(f"❌ Erro ao disparar geração de formulários: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

# ============================================================================
# ROTA DE POLLING - STATUS DA TASK CELERY
# ============================================================================

@bp.route('/task/<string:task_id>/status', methods=['GET'])
@jwt_required()
def get_task_status(task_id):
    """
    Verifica o status de uma task Celery de geração de formulários físicos.
    Retorna progresso em tempo real por turma e por aluno, além de erros detalhados.

    Resposta inclui:
    - status, progress (current/total/percentage)
    - summary (total_classes, completed_classes, successful_classes, failed_classes, total_students, zip_minio_url)
    - classes[] (por turma: class_id, class_name, school_name, status, total_students, completed, errors)
    - errors[] (por item com falha: class_id, class_name, student_id, student_name, error)
    """
    try:
        from celery.result import AsyncResult
        from app.physical_tests.tasks import generate_physical_forms_async

        task = AsyncResult(task_id, app=generate_physical_forms_async.app)
        job = get_job(task_id)

        # Status geral a partir do estado Celery
        if task.state == 'PENDING':
            status_key = 'pending'
            message = 'Aguardando processamento...'
        elif task.state == 'STARTED':
            status_key = 'processing'
            message = 'Gerando formulários PDF (isso pode levar alguns minutos)...'
        elif task.state == 'SUCCESS':
            status_key = 'completed'
            result_data = task.result
            message = result_data.get('message', 'Formulários gerados com sucesso') if result_data else 'Formulários gerados com sucesso'
        elif task.state == 'FAILURE':
            status_key = 'failed'
            message = 'Erro ao gerar formulários'
        elif task.state == 'RETRY':
            status_key = 'retrying'
            message = 'Tentando novamente após erro temporário...'
        else:
            status_key = task.state.lower() if task.state else 'unknown'
            message = f'Estado: {task.state}'

        response = {
            'task_id': task_id,
            'status': status_key,
            'message': message,
        }

        if task.state == 'FAILURE':
            response['error'] = str(task.info) if task.info else 'Erro desconhecido'
        if task.state == 'RETRY' and hasattr(task, 'info') and task.info:
            response['retries'] = task.info.get('retries', 0)

        # Progresso detalhado (job de progresso)
        if job:
            total = job.get('total', 0)
            completed = job.get('completed', 0)
            successful = job.get('successful', 0)
            failed = job.get('failed', 0)
            pct = int(round((completed / total * 100))) if total > 0 else 0

            response['progress'] = {
                'current': completed,
                'total': total,
                'percentage': min(100, pct),
            }

            items = job.get('items') or {}
            classes_map = {}
            errors_list = []

            for idx_str, item in items.items():
                st = item.get('status', 'pending')
                class_id = item.get('class_id') or ''
                class_name = item.get('class_name') or 'Turma não informada'
                school_name = item.get('school_name') or ''
                student_id = item.get('student_id')
                student_name = item.get('student_name') or ''

                key = (class_id, class_name, school_name)
                if key not in classes_map:
                    classes_map[key] = {
                        'class_id': class_id,
                        'class_name': class_name,
                        'school_name': school_name,
                        'status': 'pending',
                        'total_students': 0,
                        'completed': 0,
                        'successful': 0,
                        'failed': 0,
                        'errors': [],
                    }
                classes_map[key]['total_students'] += 1
                if st == 'done':
                    classes_map[key]['completed'] += 1
                    classes_map[key]['successful'] += 1
                elif st == 'error':
                    classes_map[key]['completed'] += 1
                    classes_map[key]['failed'] += 1
                    err_msg = item.get('error', 'Erro desconhecido')
                    classes_map[key]['errors'].append({
                        'student_id': student_id,
                        'student_name': student_name,
                        'error': err_msg,
                    })
                    errors_list.append({
                        'class_id': class_id,
                        'class_name': class_name,
                        'school_name': school_name,
                        'student_id': student_id,
                        'student_name': student_name,
                        'error': err_msg,
                    })
                elif st == 'processing':
                    classes_map[key]['status'] = 'processing'

                if classes_map[key]['status'] == 'pending' and st in ('processing', 'done', 'error'):
                    classes_map[key]['status'] = 'processing' if st == 'processing' else 'completed'

            classes_list = list(classes_map.values())
            for c in classes_list:
                if c['failed'] > 0:
                    c['status'] = 'completed_with_errors'
                elif c['completed'] == c['total_students'] and c['total_students'] > 0:
                    c['status'] = 'completed'

            response['summary'] = {
                'total_classes': len(classes_list),
                'completed_classes': sum(1 for c in classes_list if c['status'] in ('completed', 'completed_with_errors')),
                'successful_classes': sum(1 for c in classes_list if c['failed'] == 0 and c['completed'] == c['total_students']),
                'failed_classes': sum(1 for c in classes_list if c['failed'] > 0),
                'total_students': total,
                'completed_students': completed,
                'successful_students': successful,
                'failed_students': failed,
                'zip_minio_url': None,
                'can_download': False,
            }

            response['classes'] = classes_list
            response['errors'] = errors_list if errors_list else None

            # Mensagem e fase atuais (feedback por etapa: gerando, salvando, zip, upload, concluído)
            if job.get('stage_message'):
                response['message'] = job['stage_message']
            response['phase'] = job.get('phase')

            if task.state == 'SUCCESS' and task.result:
                res = task.result
                if isinstance(res, dict):
                    response['summary']['zip_minio_url'] = res.get('minio_url')
                    response['summary']['can_download'] = bool(res.get('minio_url'))
            if status_key == 'completed' and task.result and isinstance(task.result, dict):
                response['result'] = task.result
        else:
            response['progress'] = {
                'current': 0,
                'total': 0,
                'percentage': 0,
            }
            response['summary'] = None
            response['classes'] = []
            response['errors'] = None
            if task.state == 'SUCCESS' and task.result:
                response['result'] = task.result

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Erro ao verificar status da task {task_id}: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Erro ao verificar status da task",
            "error": str(e)
        }), 500


# ============================================================================
# ROTA DE GERAÇÃO INDIVIDUAL
# ============================================================================

@bp.route('/test/<string:test_id>/student/<string:student_id>/generate', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def generate_individual_physical_form(test_id, student_id):
    """
    Gera formulário físico individual para um aluno específico
    
    Body:
        - output_dir (opcional): Diretório para salvar o PDF
    
    Returns:
        - Formulário físico individual gerado
        - URL do PDF
        - Informações do aluno
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Verificar se a prova existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Prova não encontrada"}), 404
        
        # Verificar se o aluno existe
        student = Student.query.get(student_id)
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404
        
        # Verificar permissões do professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode gerar formulários para suas próprias provas"}), 403
        
        # Verificar se o aluno pertence a uma turma que aplicou a prova
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        if not class_tests:
            return jsonify({"error": "A prova não foi aplicada em nenhuma turma"}), 400
        
        class_ids = [ct.class_id for ct in class_tests]
        if student.class_id not in class_ids:
            return jsonify({"error": "O aluno não pertence a uma turma que aplicou esta prova"}), 400
        
        # Buscar questões da prova
        from app.models.testQuestion import TestQuestion
        from app.models.question import Question
        from app.models.subject import Subject
        
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
        questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
        
        if not questions:
            return jsonify({"error": "Nenhuma questão encontrada para esta prova"}), 400
        
        # Preparar dados para o gerador
        test_data = {
            'id': test.id,
            'title': test.title,
            'description': test.description,
            'grade_name': test.grade.name if test.grade else '9° ANO'
        }
        
        student_data = {
            'id': student.id,
            'nome': student.name
        }
        
        questions_data = []
        for question in questions:
            # Buscar disciplina da questão
            subject = Subject.query.get(question.subject_id) if question.subject_id else None
            
            question_data = {
                'id': question.id,
                'title': question.title,
                'text': question.text,
                'formatted_text': question.formatted_text,
                'alternatives': question.alternatives or [],
                'subject': {
                    'id': subject.id,
                    'name': subject.name
                } if subject else None
            }
            questions_data.append(question_data)
        
        # Obter class_test_id (usar o primeiro se houver múltiplos)
        class_test_id = class_tests[0].id if class_tests else None
        
        # Usar PhysicalTestFormService para gerar formulário individual
        form_service = PhysicalTestFormService()
        
        # Preparar dados
        students_data = [{'id': student.id, 'nome': student.name}]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = form_service.generate_individual_physical_form(
                test_id=test_id,
                student_id=student_id,
                output_dir=temp_dir
            )
            
            if result.get('success'):
                return jsonify({
                    "message": "Formulário individual gerado com sucesso",
                "test_id": test_id,
                    "student_id": student_id,
                    "student_name": student.name,
                    "form_id": result.get('form_id'),
                    "total_questions": len(questions_data),
                    "form_type": "formularios_style"
            }), 200
            else:
                return jsonify({"error": result.get('error', 'Erro ao gerar formulário individual')}), 500
        
    except Exception as e:
        print(f"❌ Erro ao gerar formulário individual: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

# ============================================================================
# FUNÇÃO DE PROCESSAMENTO EM BACKGROUND
# ============================================================================

def process_batch_in_background(job_id: str, test_id: str, images: list):
    """
    Processa correção em lote em background thread usando AnswerSheetCorrectionNewGrid
    
    Args:
        job_id: ID do job para tracking
        test_id: ID da prova
        images: Lista de imagens em base64
    """
    from app import create_app
    
    # Criar contexto da aplicação para a thread
    app = create_app()
    
    with app.app_context():
        try:
            correction_service = AnswerSheetCorrectionNewGrid(debug=False)
            
            for i, image_base64 in enumerate(images):
                try:
                    # Marcar como processando
                    update_item_processing(job_id, i)
                    
                    # Decodificar imagem
                    if image_base64.startswith('data:image'):
                        image_base64_clean = image_base64.split(',')[1]
                    else:
                        image_base64_clean = image_base64
                    image_data = base64.b64decode(image_base64_clean)
                    
                    # Processar correção com AnswerSheetCorrectionNewGrid
                    # O test_id e student_id são extraídos automaticamente do QR code
                    result = correction_service.corrigir_cartao_resposta(
                        image_data=image_data,
                        auto_detect_qr=True
                    )
                    
                    if result.get('success'):
                        # Buscar nome do aluno se não veio no resultado
                        student_name = None
                        if result.get('student_id'):
                            student = Student.query.get(result['student_id'])
                            if student:
                                student_name = student.name
                        
                        # Adaptar formato do resultado para compatibilidade com novo pipeline
                        adapted_result = {
                            'student_id': result.get('student_id'),
                            'student_name': student_name,
                            'test_id': result.get('test_id') or test_id,
                            'correct': result.get('correct_answers', 0),
                            'total': result.get('total_questions', 0),
                            'percentage': result.get('score', 0),
                            'score_percentage': result.get('score', 0),
                            'detailed_answers': result.get('detailed_answers', []),
                            'student_answers': result.get('student_answers', {}),
                            'evaluation_result_id': result.get('evaluation_result_id')
                        }
                        
                        update_item_done(job_id, i, adapted_result)
                        logging.info(f"✅ Job {job_id}: Imagem {i+1} processada com sucesso")
                    else:
                        update_item_error(job_id, i, result.get('error', 'Erro desconhecido'))
                        logging.warning(f"❌ Job {job_id}: Imagem {i+1} falhou: {result.get('error')}")
                        
                except Exception as e:
                    update_item_error(job_id, i, str(e))
                    logging.error(f"❌ Job {job_id}: Erro na imagem {i+1}: {str(e)}", exc_info=True)
            
            # Marcar job como concluído
            complete_job(job_id)
            logging.info(f"✅ Job {job_id} concluído")
            
        except Exception as e:
            logging.error(f"❌ Erro crítico no job {job_id}: {str(e)}", exc_info=True)
            complete_job(job_id)


# ============================================================================
# ROTAS DE CORREÇÃO
# ============================================================================

@bp.route('/test/<string:test_id>/process-correction', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def process_physical_correction(test_id):
    """
    Processa correção de formulário(s) físico(s) usando CorrecaoHybrid
    
    Aceita:
    - Uma única imagem (campo 'image') - processamento SÍNCRONO
    - Múltiplas imagens (campo 'images') - processamento ASSÍNCRONO com job_id
    
    Body (JSON) - Modo Único:
    {
        "image": "data:image/jpeg;base64,..."
    }
    
    Body (JSON) - Modo Lote:
    {
        "images": [
            "data:image/jpeg;base64,...",
            "data:image/jpeg;base64,...",
            ...
        ]
    }
    
    Returns (síncrono - 1 imagem):
        Resultado completo da correção
        
    Returns (assíncrono - múltiplas imagens):
        {"job_id": "uuid", "message": "Processamento iniciado", "total": N}
        Use GET /correction-progress/<job_id> para acompanhar o progresso
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Buscar a prova
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": f"Prova não encontrada: {test_id}"}), 404
        
        # Verificar permissões do professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode processar correções de suas próprias provas"}), 403
        
        # Obter dados da requisição
        data = None
        images = []
        single_image = None
        
        # Tentar obter de JSON
        try:
            data = request.get_json() or {}
            
            # Verificar se é lote (campo 'images') ou única (campo 'image')
            if 'images' in data and isinstance(data['images'], list):
                images = data['images']
            elif 'image' in data:
                single_image = data['image']
        except:
            pass
        
        # Tentar obter de form-data (arquivo)
        if not images and not single_image and 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                image_bytes = file.read()
                single_image = f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        
        # Tentar obter de form-data (base64)
        if not images and not single_image:
            image_base64 = request.form.get('image')
            if image_base64:
                single_image = image_base64
        
        # ==================================================================
        # MODO ÚNICO (1 imagem) - Processamento SÍNCRONO
        # ==================================================================
        if single_image and not images:
            logging.info(f"🔧 Processando correção única para prova física")
            
            # Decodificar imagem
            if single_image.startswith('data:image'):
                single_image_clean = single_image.split(',')[1]
            else:
                single_image_clean = single_image
            image_data = base64.b64decode(single_image_clean)
            
            # Processar com AnswerSheetCorrectionNewGrid
            # O test_id e student_id são extraídos automaticamente do QR code
            correction_service = AnswerSheetCorrectionNewGrid(debug=False)
            result = correction_service.corrigir_cartao_resposta(
                image_data=image_data,
                auto_detect_qr=True
            )
            
            if result.get('success'):
                # Adaptar formato do resultado para compatibilidade com novo pipeline
                return jsonify({
                    "message": "Correção processada com sucesso",
                    "system": "new_grid_pipeline",
                    "student_id": result.get('student_id'),
                    "test_id": result.get('test_id') or test_id,
                    "correct": result.get('correct_answers', 0),
                    "wrong": result.get('wrong_answers', 0),
                    "blank": result.get('blank_answers', 0),
                    "invalid": result.get('invalid_answers', 0),
                    "total": result.get('total_questions', 0),
                    "score": result.get('score', 0),
                    "percentage": result.get('score', 0),
                    "detailed_answers": result.get('detailed_answers', []),
                    "student_answers": result.get('student_answers', {}),
                    "answer_key": result.get('answer_key', {}),
                    "evaluation_result_id": result.get('evaluation_result_id')
                }), 200
            else:
                return jsonify({
                    "error": result.get('error', 'Erro desconhecido na correção'),
                    "system": "new_grid_pipeline"
                }), 500
        
        # ==================================================================
        # MODO LOTE (múltiplas imagens) - Processamento ASSÍNCRONO
        # ==================================================================
        if images:
            # Validar quantidade
            if len(images) > 50:
                return jsonify({"error": "Máximo de 50 imagens por lote"}), 400
            
            if len(images) == 0:
                return jsonify({"error": "Nenhuma imagem fornecida"}), 400
            
            logging.info(f"🔧 Iniciando correção em lote: {len(images)} imagens para prova {test_id}")
            
            # Criar job ID
            job_id = str(uuid.uuid4())
            
            # Criar job no store
            create_job(job_id, len(images), test_id)
            
            # Iniciar thread de processamento
            thread = threading.Thread(
                target=process_batch_in_background,
                args=(job_id, test_id, images),
                daemon=True
            )
            thread.start()
            
            return jsonify({
                "job_id": job_id,
                "message": "Processamento em lote iniciado",
                "total": len(images),
                "status": "processing"
            }), 202  # 202 Accepted
        
        # Nenhuma imagem fornecida
        return jsonify({"error": "Imagem não fornecida. Use 'image' para única ou 'images' para lote."}), 400
        
    except Exception as e:
        logging.error(f"❌ Erro ao processar correção: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500


# ============================================================================
# ROTA DE PROGRESSO DA CORREÇÃO EM LOTE
# ============================================================================

@bp.route('/correction-progress/<string:job_id>', methods=['GET'])
@jwt_required()
def get_correction_progress(job_id):
    """
    Consulta progresso de uma correção em lote
    
    Returns:
    {
        "job_id": "uuid",
        "total": 5,
        "completed": 2,
        "successful": 2,
        "failed": 0,
        "status": "processing",  // "processing" | "completed"
        "percentage": 40.0,
        "items": {
            "0": {"status": "done", "student_id": "xxx", "student_name": "João", ...},
            "1": {"status": "done", "student_id": "yyy", "student_name": "Maria", ...},
            "2": {"status": "processing"},
            "3": {"status": "pending"},
            "4": {"status": "pending"}
        },
        "results": [...]  // Resultados completos quando status = "completed"
    }
    """
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job não encontrado"}), 404
    
    # Calcular porcentagem
    percentage = (job["completed"] / job["total"] * 100) if job["total"] > 0 else 0
    
    response = {
        "job_id": job_id,
        "total": job["total"],
        "completed": job["completed"],
        "successful": job["successful"],
        "failed": job["failed"],
        "status": job["status"],
        "percentage": round(percentage, 1),
        "items": job["items"]
    }
    
    # Incluir resultados completos apenas quando finalizado
    if job["status"] == "completed":
        response["results"] = job["results"]
    
    return jsonify(response), 200

# ============================================================================
# ROTAS DE LISTAGEM E CONSULTA
# ============================================================================

@bp.route('/forms', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def list_physical_forms():
    """
    Lista formulários físicos com filtros opcionais
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Obter parâmetros de filtro
        test_id = request.args.get('test_id')
        student_id = request.args.get('student_id')
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Buscar formulários
        forms = PhysicalTestFormService.get_physical_forms(
            test_id=test_id,
            student_id=student_id,
            status=status,
            page=page,
            per_page=per_page,
            user=user
        )
        
        return jsonify({
            "message": "Formulários listados com sucesso",
            "forms": forms['forms'],
            "total": forms['total'],
            "page": page,
            "per_page": per_page,
            "pages": forms['pages']
        }), 200
        
    except Exception as e:
        print(f"❌ Erro ao listar formulários: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/forms/<string:form_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_physical_form(form_id):
    """
    Obtém detalhes de um formulário físico específico
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Buscar formulário
        form = PhysicalTestFormService.get_physical_form_by_id(form_id, user)
        
        if not form:
            return jsonify({"error": "Formulário não encontrado"}), 404
        
        return jsonify({
            "message": "Formulário obtido com sucesso",
            "form": form
        }), 200
        
    except Exception as e:
        print(f"❌ Erro ao obter formulário: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/status', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_physical_test_status(test_id):
    """
    Verifica status de aplicação da prova para formulários físicos
    
    Returns:
        - Status da aplicação
        - Informações sobre turmas aplicadas
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Verificar se a prova existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Prova não encontrada"}), 404
        
        # Verificar permissões do professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode ver status de suas próprias provas"}), 403
        
        # Buscar aplicações da prova
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
        if not class_tests:
            return jsonify({
                "can_generate_forms": False,
                "reason": "A prova não foi aplicada em nenhuma turma",
                "class_tests": []
            }), 200
        
        # Para formulários físicos, consideramos aplicada se existe class_test
        # O status 'agendada' indica que a prova foi aplicada e está disponível
        applied_tests = class_tests
        
        can_generate = len(applied_tests) > 0
        
        class_tests_info = []
        for ct in class_tests:
            class_tests_info.append({
                "id": ct.id,
                "class_id": ct.class_id,
                "status": ct.status,
                "application": ct.application,
                "expiration": ct.expiration
            })
        
        return jsonify({
            "can_generate_forms": can_generate,
            "reason": "A prova foi aplicada" if can_generate else "A prova precisa ser aplicada primeiro",
            "class_tests": class_tests_info,
            "total_applications": len(class_tests),
            "applied_applications": len(applied_tests)
        }), 200
        
    except Exception as e:
        print(f"❌ Erro ao verificar status da prova: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/forms', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_physical_forms(test_id):
    """
    Lista formulários físicos de uma prova
    
    Por padrão, retorna TODOS os formulários físicos da prova, incluindo:
    - Formulários combinados (PDF único com todas as provas)
    - Formulários individuais (um PDF por aluno)
    
    Query params:
        - student_id (opcional): Filtrar por aluno específico
    
    Returns:
        - Lista de formulários físicos (todos ou filtrados por aluno)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Verificar se a prova existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Prova não encontrada"}), 404
        
        # Verificar permissões do professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode ver formulários de suas próprias provas"}), 403
        
        # Filtrar por aluno se especificado
        student_id = request.args.get('student_id')
        
        if student_id:
            # Buscar formulário específico do aluno
            form = PhysicalTestForm.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if form:
                return jsonify({
                    "form": form.to_dict()
                }), 200
            else:
                return jsonify({"error": "Formulário não encontrado para este aluno"}), 404
        else:
            # Usar PhysicalTestFormService para buscar formulários
            form_service = PhysicalTestFormService()
            forms = form_service.get_physical_forms_by_test(test_id)
            
            # forms já é uma lista de dicionários, não precisa chamar .to_dict()
            return jsonify({
                "forms": forms,
                "total": len(forms)
            }), 200
            
    except Exception as e:
        print(f"❌ Erro ao buscar formulários físicos: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/download/<string:form_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def download_physical_form(test_id, form_id):
    """
    Download de formulário físico específico (URL pré-assinada do MinIO)

    Returns:
        - JSON com URL pré-assinada válida por 1 hora
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Buscar formulário
        form = PhysicalTestForm.query.filter_by(
            id=form_id,
            test_id=test_id
        ).first()
        
        if not form:
            return jsonify({"error": "Formulário não encontrado"}), 404
        
        # Verificar permissões
        test = Test.query.get(test_id)
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você não tem permissão para baixar este formulário"}), 403

        # ============================================================
        # NOVO FLUXO: usar MinIO como fonte única (sem legado Postgres)
        # ============================================================
        # Verificar se temos URL do PDF salva no formulário
        if not form.form_pdf_url:
            return jsonify({"error": "URL do PDF não encontrada para este formulário"}), 404

        # Gerar URL pré-assinada a partir da URL salva (MinIO)
        from app.services.storage.minio_service import MinIOService
        from datetime import timedelta

        minio = MinIOService()
        bucket_name = minio.BUCKETS['PHYSICAL_TESTS']
        file_url = form.form_pdf_url

        # Extrair object_name da URL:
        # Exemplo: http://minio-server:9000/physical-tests/<object_name>
        #          https://files.afirmeplay.com.br/physical-tests/<object_name>
        marker = f"/{bucket_name}/"
        idx = file_url.find(marker)
        if idx == -1:
            # URL em formato inesperado - não conseguimos derivar o object_name
            return jsonify({
                "error": "Formato de URL do arquivo inválido para download",
                "details": "URL não contém o caminho do bucket esperado",
                "form_id": form_id,
                "test_id": test_id
            }), 400

        object_name = file_url[idx + len(marker):]
        if not object_name:
            return jsonify({
                "error": "Nome do objeto MinIO não encontrado na URL",
                "form_id": form_id,
                "test_id": test_id
            }), 400

        # Gerar URL pré-assinada (válida por 1 hora)
        try:
            presigned_url = minio.get_presigned_url(
                bucket_name=bucket_name,
                object_name=object_name,
                expires=timedelta(hours=1)
            )

            return jsonify({
                "download_url": presigned_url,
                "expires_in": "1 hour",
                "test_id": test_id,
                "form_id": form_id,
                "student_id": form.student_id,
                "student_name": getattr(form, "student", None).name if getattr(form, "student", None) else None,
                "created_at": form.generated_at.isoformat() if form.generated_at else None
            }), 200

        except Exception as minio_error:
            logging.error(f"Erro ao gerar URL pré-assinada para formulário físico: {str(minio_error)}")
            return jsonify({
                "error": "Erro ao gerar URL de download",
                "details": str(minio_error)
            }), 500
        
    except Exception as e:
        print(f"❌ Erro ao baixar formulário físico: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/download-all', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def download_all_physical_forms(test_id):
    """
    Retorna URL pré-assinada para download do ZIP de provas físicas do MinIO
    
    Se o ZIP ainda não foi gerado, retorna erro pedindo para gerar primeiro.
    O ZIP é gerado automaticamente pela task Celery após POST /physical-tests/test/{test_id}/generate-forms.
    
    Returns:
        JSON com URL pré-assinada válida por 1 hora
    """
    try:
        from app.services.storage.minio_service import MinIOService
        from datetime import timedelta
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Verificar se a prova existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Prova não encontrada"}), 404
        
        # Verificar permissões do professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você não tem permissão para baixar formulários desta prova"}), 403
        
        # Buscar gabarito associado à prova
        gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
        
        if not gabarito or not gabarito.minio_object_name:
            return jsonify({
                "error": "ZIP de provas físicas ainda não foi gerado",
                "message": "Use a rota POST /physical-tests/test/{test_id}/generate-forms para gerar as provas primeiro. Após a geração (verifique status via polling), o ZIP estará disponível para download.",
                "test_id": test_id,
                "status": "not_generated"
            }), 400
        
        # Gerar URL pré-assinada (válida por 1 hora)
        minio = MinIOService()
        
        try:
            presigned_url = minio.get_presigned_url(
                bucket_name=gabarito.minio_bucket or minio.BUCKETS['PHYSICAL_TESTS'],
                object_name=gabarito.minio_object_name,
                expires=timedelta(hours=1)
            )
            
            return jsonify({
                "download_url": presigned_url,
                "expires_in": "1 hour",
                "test_id": test_id,
                "test_title": test.title,
                "gabarito_id": str(gabarito.id) if gabarito else None,
                "generated_at": gabarito.zip_generated_at.isoformat() if gabarito and gabarito.zip_generated_at else None,
                "minio_url": gabarito.minio_url
            }), 200
            
        except Exception as minio_error:
            logging.error(f"Erro ao gerar URL pré-assinada: {str(minio_error)}")
            return jsonify({
                "error": "Erro ao gerar URL de download",
                "details": str(minio_error)
            }), 500
        
    except Exception as e:
        print(f"❌ Erro ao baixar formulários físicos: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

# ============================================================================
# ROTAS DE EXCLUSÃO
# ============================================================================

@bp.route('/form/<string:form_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def delete_physical_form(form_id):
    """
    Exclui um formulário físico específico
    
    Returns:
        - Confirmação de exclusão
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Buscar formulário
        form = PhysicalTestForm.query.get(form_id)
        if not form:
            return jsonify({"error": "Formulário não encontrado"}), 404
        
        # Verificar permissões
        test = Test.query.get(form.test_id)
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você não tem permissão para excluir este formulário"}), 403
        
        # Usar PhysicalTestFormService para excluir formulário
        form_service = PhysicalTestFormService()
        result = form_service.delete_physical_form(form_id)
        
        if result.get('success'):
            return jsonify({
                "message": "Formulário excluído com sucesso",
                "form_id": form_id
            }), 200
        else:
            return jsonify({"error": result.get('error', 'Erro ao excluir formulário')}), 500
        
    except Exception as e:
        print(f"❌ Erro ao excluir formulário: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/forms', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def delete_all_physical_forms_by_test(test_id):
    """
    Exclui todos os formulários físicos de uma prova
    
    Returns:
        - Confirmação de exclusão
        - Número de formulários excluídos
    """
    try:
        # Usar get_user_for_permission_check (role como string) para a checagem admin/criador/município
        user = get_user_for_permission_check()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Verificar se a prova existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Prova não encontrada"}), 404
        
        # Verificar permissões (user.role já é string, ex.: 'admin')
        user_role = user.get('role')
        user_id = user.get('id')
        user_city_id = user.get('tenant_id') or user.get('city_id')
        
        can_delete = False
        
        # Admin pode excluir qualquer formulário (usar role do JWT para evitar 403 quando user do DB não reflete admin)
        if get_jwt().get('role') == 'admin':
            can_delete = True
        elif user_role == 'admin':
            can_delete = True
        elif test.created_by == user_id:
            # Criador pode excluir seus próprios formulários
            can_delete = True
        elif user_city_id and test.creator and test.creator.city_id == user_city_id:
            # Usuários do mesmo município podem excluir
            can_delete = True
        
        if not can_delete:
            return jsonify({"error": "Você não tem permissão para excluir formulários desta prova"}), 403
        
        # Buscar todos os formulários da prova
        forms = PhysicalTestForm.query.filter_by(test_id=test_id).all()
        
        if not forms:
            return jsonify({
                "message": "Nenhum formulário encontrado para esta prova",
                "deleted_count": 0
            }), 200
        
        # Usar PhysicalTestFormService para excluir todos os formulários
        form_service = PhysicalTestFormService()
        result = form_service.delete_all_physical_forms_by_test(test_id)
        
        if result.get('success'):
            return jsonify({
                "message": f"{result.get('deleted_count', 0)} formulários excluídos com sucesso",
                "test_id": test_id,
                "deleted_count": result.get('deleted_count', 0)
            }), 200
        else:
            return jsonify({"error": result.get('error', 'Erro ao excluir formulários')}), 500
        
    except Exception as e:
        print(f"❌ Erro ao excluir formulários: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500
