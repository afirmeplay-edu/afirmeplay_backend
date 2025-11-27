# -*- coding: utf-8 -*-
"""
Rotas para formulários físicos - Versão simplificada sem SSE
"""

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators.role_required import role_required
from app.models.test import Test
from app.models.student import Student
from app.models.user import User
from app.models.evaluationResult import EvaluationResult
from app.models.physicalTestForm import PhysicalTestForm
from app.models.classTest import ClassTest
from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
from app.services.physical_test_form_service import PhysicalTestFormService
from app.services.sistemaORM import SistemaORM  # NOVO SISTEMA OMR
import tempfile
from app.services.batch_correction_service import batch_correction_service
import logging
import base64
import os
import json

bp = Blueprint('physical_tests', __name__, url_prefix='/physical-tests')

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
# ROTAS DE GERAÇÃO DE FORMULÁRIOS
# ============================================================================

@bp.route('/test/<string:test_id>/generate-forms', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def generate_physical_forms(test_id):
    """
    Gera PDFs institucionais para uma prova específica (formato das imagens fornecidas)
    
    Body:
        - output_dir (opcional): Diretório para salvar os PDFs
        - logo_data (opcional): Dados do logo (base64 ou URL)
        - force_regenerate (opcional): Forçar regeneração de formulários existentes (padrão: false)
    
    Returns:
        - Lista de PDFs institucionais gerados
        - URLs dos PDFs
        - Informações dos alunos
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
            return jsonify({"error": "Você só pode gerar PDFs institucionais para suas próprias provas"}), 403
        
        # Obter dados da requisição
        try:
            data = request.get_json() or {}
        except:
            data = {}
        logo_data = data.get('logo_data')  # Logo será implementado posteriormente
        force_regenerate = data.get('force_regenerate', False)  # Forçar regeneração de formulários existentes
        
        # Parâmetros de configuração de blocos
        use_blocks = data.get('use_blocks', False)
        num_blocks = data.get('num_blocks', None)
        questions_per_block = data.get('questions_per_block', None)
        separate_by_subject = data.get('separate_by_subject', False)
        
        # Buscar questões da prova
        from app.models.testQuestion import TestQuestion
        from app.models.question import Question
        from app.models.subject import Subject
        
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
        questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
        
        if not questions:
            return jsonify({"error": "Nenhuma questão encontrada para esta prova"}), 400
        
        # Buscar alunos das turmas que aplicaram a prova
        from app.models.student import Student
        from app.models.studentClass import Class
        
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        if not class_tests:
            return jsonify({"error": "A prova não foi aplicada em nenhuma turma"}), 400
        
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
        
        # Preparar dados para o gerador (blocks_config será adicionado após validação)
        test_data = {
            'id': test.id,
            'title': test.title,
            'description': test.description,
            'course': test.course,
            'course_name': course_name,
            'education_stage_id': test.grade.education_stage_id if test.grade else None,
            'education_stage_name': education_stage_name,
            'grade_name': test.grade.name if test.grade else '9° ANO'
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
        
        # Validar configuração de blocos
        total_questions = len(questions_data)
        unique_subjects = set()
        for q in questions_data:
            if q.get('subject') and q['subject'].get('name'):
                unique_subjects.add(q['subject']['name'])
        num_subjects = len(unique_subjects) if unique_subjects else 1
        
        if use_blocks:
            if separate_by_subject:
                # Se separar por disciplina, num_blocks deve ser igual ao número de disciplinas
                if num_blocks is not None and num_blocks != num_subjects:
                    return jsonify({
                        "error": f"Se separar por disciplina, o número de blocos deve ser igual ao número de disciplinas ({num_subjects}). Você informou {num_blocks} blocos."
                    }), 400
                # Se não informou num_blocks, usar número de disciplinas
                if num_blocks is None:
                    num_blocks = num_subjects
            else:
                # Se não separar por disciplina, validar quantidade de questões
                if num_blocks is None or questions_per_block is None:
                    return jsonify({
                        "error": "Quando use_blocks=true e separate_by_subject=false, é necessário informar num_blocks e questions_per_block"
                    }), 400
                
                max_questions = num_blocks * questions_per_block
                if max_questions < total_questions:
                    return jsonify({
                        "error": f"Configuração inválida: {num_blocks} blocos × {questions_per_block} questões = {max_questions} questões, mas a prova tem {total_questions} questões"
                    }), 400
        
        # Adicionar configuração de blocos ao test_data
        test_data['blocks_config'] = {
            'use_blocks': use_blocks,
            'num_blocks': num_blocks,
            'questions_per_block': questions_per_block,
            'separate_by_subject': separate_by_subject
        }
        
        # Obter class_test_id (usar o primeiro se houver múltiplos)
        class_test_id = class_tests[0].id if class_tests else None
        
        # Usar PhysicalTestFormService para gerar formulários
        print(f"GERANDO FORMULARIOS PARA {len(students_data)} ALUNOS...")
        
        form_service = PhysicalTestFormService()
        
        # Gerar formulários usando o serviço (passar test_data com blocks_config)
        with tempfile.TemporaryDirectory() as temp_dir:
            result = form_service.generate_physical_forms(
                test_id=test_id,
                output_dir=temp_dir,
                test_data=test_data  # Passar test_data com blocks_config
            )
            
            if result.get('success'):
                print(f"SUCESSO: {result.get('generated_forms', 0)} formularios gerados")
                
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
                    "total_questions": len(questions_data),
                    "total_students": len(students_data),
                    "generated_forms": len(formularios_gerados),
                    "forms": formularios_gerados
                }), 200
            else:
                print(f"ERRO: {result.get('error')}")
                return jsonify({"error": result.get('error', 'Erro ao gerar formulários')}), 500
        
    except Exception as e:
        print(f"❌ Erro ao gerar formulários: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

# ============================================================================
# ROTA DE GERAÇÃO INDIVIDUAL
# ============================================================================

@bp.route('/test/<string:test_id>/student/<string:student_id>/generate', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
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
# ROTAS DE CORREÇÃO
# ============================================================================

@bp.route('/test/<string:test_id>/process-correction', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def process_physical_correction(test_id):
    """
    Processa correção de gabarito físico preenchido usando gabarito de referência
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
        
        # Obter dados da imagem
        image_data = None
        
        if 'image' in request.files:
            # Upload de arquivo
            file = request.files['image']
            if file and file.filename:
                image_data = file.read()
        else:
            # Tentar obter dados JSON
            try:
                data = request.get_json() or {}
                if 'image' in data:
                    # Base64
                    image_base64 = data['image']
                    if image_base64.startswith('data:image'):
                        image_base64 = image_base64.split(',')[1]
                    image_data = base64.b64decode(image_base64)
            except Exception as e:
                # Se não conseguir obter JSON, tentar form data
                try:
                    image_base64 = request.form.get('image')
                    if image_base64:
                        if image_base64.startswith('data:image'):
                            image_base64 = image_base64.split(',')[1]
                        image_data = base64.b64decode(image_base64)
                except Exception as e2:
                    return jsonify({"error": "Formato de dados inválido. Envie como JSON ou form-data"}), 400
        
        if not image_data:
            return jsonify({"error": "Imagem não fornecida"}), 400
        
        # Verificar se deve usar o novo sistema OMR (parâmetro opcional)
        data = request.get_json() or {}
        use_new_orm = data.get('use_new_orm', False) or request.form.get('use_new_orm', 'false').lower() == 'true'
        
        if use_new_orm:
            # NOVO SISTEMA OMR - Alinhamento pela página inteira
            print("🆕 Usando NOVO SISTEMA OMR (alinhamento pela página)")
            
            try:
                # Converter image_data para base64 string
                if isinstance(image_data, bytes):
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                    image_data_str = f"data:image/jpeg;base64,{image_base64}"
                else:
                    image_data_str = image_data
                
                # Criar instância do novo sistema
                sistema_orm = SistemaORM(debug=True)
                
                # Processar correção
                result = sistema_orm.process_exam(
                    image_data=image_data_str,
                    num_questions=None  # Será buscado do banco
                )
                
                if result.get('success'):
                    return jsonify({
                        "message": "Correção processada com sucesso (NOVO SISTEMA OMR)",
                        "system": "new_orm",
                        "student_id": result.get('student_id'),
                        "test_id": result.get('test_id'),
                        "correct": result.get('correct'),
                        "total": result.get('total'),
                        "score": result.get('score'),
                        "percentage": result.get('percentage'),
                        "answers": result.get('answers'),
                        "saved_answers": result.get('saved_answers'),
                        "evaluation_result": result.get('evaluation_result')
                    }), 200
                else:
                    return jsonify({
                        "error": result.get('error', 'Erro desconhecido na correção'),
                        "system": "new_orm"
                    }), 500
                    
            except Exception as e:
                logging.error(f"Erro no novo sistema OMR: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
                return jsonify({
                    "error": f"Erro no novo sistema OMR: {str(e)}",
                    "system": "new_orm"
                }), 500
        
        else:
            # SISTEMA ANTIGO - Mantido para compatibilidade
            print("📋 Usando SISTEMA ANTIGO (alinhamento por marcadores)")
            
            form_service = PhysicalTestFormService()
            
            result = form_service.process_physical_correction(
                test_id=test_id,
                image_data=image_data,
                correction_image_url=None
            )
            
            if result.get('success'):
                return jsonify({
                    "message": "Correção processada com sucesso",
                    "system": "old",
                    "student_id": result.get('student_id'),
                    "test_id": test_id,
                    "correct_answers": result.get('correct_answers'),
                    "total_questions": result.get('total_questions'),
                    "score_percentage": result.get('score_percentage'),
                    "grade": result.get('grade'),
                    "proficiency": result.get('proficiency'),
                    "classification": result.get('classification'),
                    "answers_detected": result.get('answers_detected'),
                    "student_answers": result.get('student_answers'),
                    "evaluation_result_id": result.get('evaluation_result_id')
                }), 200
            else:
                return jsonify({
                    "error": result.get('error', 'Erro desconhecido na correção'),
                    "system": "old"
                }), 500
        
    except Exception as e:
        print(f"❌ Erro ao processar correção: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500


@bp.route('/test/<string:test_id>/process-correction-orm', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def process_physical_correction_orm(test_id):
    """
    ROTA TEMPORÁRIA: Processa correção usando o NOVO SISTEMA OMR
    Alinhamento pela página inteira (não pelos 4 quadradinhos)
    
    Esta rota usa exclusivamente o novo sistema OMR para testes
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
        
        # Obter dados da imagem
        image_data = None
        
        if 'image' in request.files:
            # Upload de arquivo
            file = request.files['image']
            if file and file.filename:
                image_data = file.read()
        else:
            # Tentar obter dados JSON
            try:
                data = request.get_json() or {}
                if 'image' in data:
                    # Base64
                    image_base64 = data['image']
                    if image_base64.startswith('data:image'):
                        image_base64 = image_base64.split(',')[1]
                    image_data = base64.b64decode(image_base64)
            except Exception as e:
                # Se não conseguir obter JSON, tentar form data
                try:
                    image_base64 = request.form.get('image')
                    if image_base64:
                        if image_base64.startswith('data:image'):
                            image_base64 = image_base64.split(',')[1]
                        image_data = base64.b64decode(image_base64)
                except Exception as e2:
                    return jsonify({"error": "Formato de dados inválido. Envie como JSON ou form-data"}), 400
        
        if not image_data:
            return jsonify({"error": "Imagem não fornecida"}), 400
        
        # NOVO SISTEMA OMR
        print("🆕 Processando correção com NOVO SISTEMA OMR")
        
        try:
            # Converter image_data para base64 string
            if isinstance(image_data, bytes):
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                image_data_str = f"data:image/jpeg;base64,{image_base64}"
            else:
                image_data_str = image_data
            
            # Criar instância do novo sistema
            sistema_orm = SistemaORM(debug=True)
            
            # Processar correção
            result = sistema_orm.process_exam(
                image_data=image_data_str,
                num_questions=None  # Será buscado do banco
            )
            
            if result.get('success'):
                return jsonify({
                    "message": "Correção processada com sucesso (NOVO SISTEMA OMR)",
                    "system": "new_orm",
                    "student_id": result.get('student_id'),
                    "test_id": result.get('test_id'),
                    "correct": result.get('correct'),
                    "total": result.get('total'),
                    "score": result.get('score'),
                    "percentage": result.get('percentage'),
                    "answers": result.get('answers'),
                    "saved_answers": result.get('saved_answers'),
                    "evaluation_result": result.get('evaluation_result')
                }), 200
            else:
                return jsonify({
                    "error": result.get('error', 'Erro desconhecido na correção'),
                    "system": "new_orm"
                }), 500
                
        except Exception as e:
            logging.error(f"Erro no novo sistema OMR: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return jsonify({
                "error": f"Erro no novo sistema OMR: {str(e)}",
                "system": "new_orm",
                "traceback": traceback.format_exc() if logging.getLogger().level == logging.DEBUG else None
            }), 500
        
    except Exception as e:
        print(f"❌ Erro ao processar correção: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

# ============================================================================
# ROTAS DE CORREÇÃO EM LOTE SÍNCRONA
# ============================================================================

@bp.route('/test/<string:test_id>/batch-process-correction', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def batch_process_correction(test_id):
    """
    Processa correção em lote de múltiplos formulários físicos de forma síncrona
    
    Body (JSON):
    {
        "images": [
            {
                "student_id": "uuid1", // opcional
                "student_name": "João Silva", // opcional
                "image": "data:image/jpeg;base64,..."
            },
            {
                "student_id": "uuid2",
                "image": "data:image/jpeg;base64,..."
            }
        ]
    }
    
    Returns:
        - Resultados de todas as correções
        - Resumo final
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Validar prova
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": f"Prova não encontrada: {test_id}"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode processar correções de suas próprias provas"}), 403
        
        # Obter dados das imagens
        data = request.get_json()
        if not data or 'images' not in data:
            return jsonify({"error": "Campo 'images' é obrigatório"}), 400
        
        images = data['images']
        if not isinstance(images, list) or len(images) == 0:
            return jsonify({"error": "Lista de imagens deve ser um array não vazio"}), 400
        
        # Limitar número de imagens por lote
        if len(images) > 50:
            return jsonify({"error": "Máximo de 50 imagens por lote"}), 400
        
        # Validar formato das imagens
        for i, img_data in enumerate(images):
            if not isinstance(img_data, dict) or 'image' not in img_data:
                return jsonify({"error": f"Imagem {i+1} deve ter campo 'image'"}), 400
            
            # Validar formato base64
            image_str = img_data['image']
            if not image_str.startswith('data:image'):
                return jsonify({"error": f"Imagem {i+1} deve estar em formato base64"}), 400
        
        # Processar correção em lote de forma síncrona
        results = batch_correction_service.process_batch_sync(
            test_id=test_id,
            created_by=user['id'],
            images_data=images
        )
        
        logging.info(f"Correção em lote concluída: {len(images)} imagens processadas")
        
        return jsonify({
            "message": "Correção em lote concluída com sucesso",
            "test_id": test_id,
            "total_images": len(images),
            "successful_corrections": results['successful_corrections'],
            "failed_corrections": results['failed_corrections'],
            "success_rate": results['success_rate'],
            "results": results['results'],
            "errors": results['errors']
        }), 200
        
    except Exception as e:
        print(f"❌ Erro ao processar correção em lote: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

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
@role_required("admin", "professor", "coordenador", "diretor")
def download_physical_form(test_id, form_id):
    """
    Download de formulário físico específico
    
    Returns:
        - Arquivo PDF do formulário
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
        
        # Verificar se PDF existe no banco
        if not form.form_pdf_data:
            return jsonify({"error": "Arquivo PDF não encontrado no banco de dados"}), 404
        
        # Criar arquivo temporário em memória
        from io import BytesIO
        pdf_buffer = BytesIO(form.form_pdf_data)
        pdf_buffer.seek(0)
        
        # Enviar arquivo do banco
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"prova_{test_id}_{form.student_id}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"❌ Erro ao baixar formulário físico: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/download-all', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def download_all_physical_forms(test_id):
    """
    Download de todos os formulários físicos de uma prova em um arquivo ZIP
    
    Returns:
        - Arquivo ZIP contendo todos os PDFs dos alunos
    """
    try:
        import zipfile
        from io import BytesIO
        
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
        
        # Buscar todos os formulários da prova
        forms = PhysicalTestForm.query.filter_by(test_id=test_id).all()
        
        if not forms:
            return jsonify({"error": "Nenhum formulário encontrado para esta prova"}), 404
        
        # Criar ZIP em memória
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for form in forms:
                if form.form_pdf_data:
                    filename = f"prova_{test_id}_{form.student_id}.pdf"
                    zip_file.writestr(filename, form.form_pdf_data)
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"provas_fisicas_{test_id}.zip",
            mimetype='application/zip'
        )
        
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
@role_required("admin", "professor", "coordenador", "diretor")
def delete_all_physical_forms_by_test(test_id):
    """
    Exclui todos os formulários físicos de uma prova
    
    Returns:
        - Confirmação de exclusão
        - Número de formulários excluídos
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Verificar se a prova existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Prova não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
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
