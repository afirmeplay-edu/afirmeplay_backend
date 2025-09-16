# -*- coding: utf-8 -*-
"""
Rotas para sistema de formulários físicos de provas
"""

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.services.physical_test_form_service import PhysicalTestFormService
from app.services.institutional_test_pdf_generator import InstitutionalTestPDFGenerator
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.physicalTestForm import PhysicalTestForm
from app.models.evaluationResult import EvaluationResult
from app import db
import logging
import os
import base64
from datetime import datetime
from typing import Dict, Any

bp = Blueprint('physical_tests', __name__, url_prefix='/physical-tests')

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
        
        # Preparar dados para o gerador
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
        
        # Obter class_test_id (usar o primeiro se houver múltiplos)
        class_test_id = class_tests[0].id if class_tests else None
        
        # Gerar PDFs institucionais e salvar no banco
        generator = InstitutionalTestPDFGenerator()
        generated_files = generator.generate_institutional_test_pdf(
            test_data, students_data, questions_data, class_test_id
        )
        
        # Gerar formulários individuais no estilo formularios.py para cada aluno
        print(f"🎯 GERANDO FORMULÁRIOS ESTILO FORMULARIOS.PY PARA {len(students_data)} ALUNOS...")
        
        from app.models.physicalTestForm import PhysicalTestForm
        from app import db
        
        formularios_gerados = []
        
        for student in students_data:
            try:
                # Verificar se já existe formulário para este aluno (evitar duplicatas)
                existing_form = PhysicalTestForm.query.filter_by(
                    test_id=test_id,
                    student_id=student['id']
                ).first()
                
                if existing_form and not force_regenerate:
                    print(f"  ⚠️ Formulário já existe para {student['nome']} (ID: {student['id']}) - pulando geração")
                    continue
                elif existing_form and force_regenerate:
                    print(f"  🔄 Formulário já existe para {student['nome']} (ID: {student['id']}) - forçando regeneração")
                    # Excluir formulário existente
                    db.session.delete(existing_form)
                    db.session.flush()  # Aplicar exclusão antes de criar novo
                
                # Gerar formulário estilo formularios.py
                form_image, form_coords, qr_coords = generator._create_formulario_style_form(
                    student['nome'], 
                    student['id'],
                    len(questions_data)  # Número total de questões
                )
                
                if form_image and form_coords and qr_coords:
                    # Salvar no banco de dados
                    form = PhysicalTestForm(
                        test_id=test_id,
                        student_id=student['id'],
                        class_test_id=class_test_id,
                        form_pdf_data=form_image.tobytes(),  # Converter PIL para bytes
                        qr_code_data=student['id'],  # APENAS o student_id, como no projeto.py
                        form_type='formularios_style'
                    )
                    
                    db.session.add(form)
                    
                    # Salvar coordenadas na tabela FormCoordinates (atualizar se existir)
                    from app.models.formCoordinates import FormCoordinates
                    
                    # Verificar se já existem coordenadas para este aluno
                    existing_coords = FormCoordinates.query.filter_by(
                        qr_code_id=student['id'],
                        test_id=test_id
                    ).first()
                    
                    if existing_coords:
                        # Atualizar coordenadas existentes
                        existing_coords.coordinates = form_coords
                        print(f"  🔄 Coordenadas atualizadas para {student['nome']} (ID: {student['id']})")
                    else:
                        # Criar novas coordenadas
                        form_coordinates = FormCoordinates(
                            test_id=test_id,
                            qr_code_id=student['id'],  # QR code contém apenas o student_id
                            student_id=student['id'],
                            coordinates=form_coords  # Lista de coordenadas [x, y, w, h]
                        )
                        db.session.add(form_coordinates)
                        print(f"  ➕ Novas coordenadas criadas para {student['nome']} (ID: {student['id']})")
                    
                    formularios_gerados.append({
                        'student_id': student['id'],
                        'student_name': student['nome'],
                        'form_type': 'formularios_style',
                        'coordinates': form_coords,
                        'qr_coordinates': qr_coords
                    })
                    
                    print(f"  ✅ Formulário gerado para {student['nome']} (ID: {student['id']}) - {len(form_coords)} coordenadas salvas")
                else:
                    print(f"  ❌ Erro ao gerar formulário para {student['nome']}")
                    
            except Exception as e:
                print(f"  ❌ Erro ao gerar formulário para {student['nome']}: {str(e)}")
                continue
        
        # Commit das alterações
        db.session.commit()
        
        print(f"🎯 FORMULÁRIOS ESTILO FORMULARIOS.PY GERADOS: {len(formularios_gerados)}/{len(students_data)}")
        
        if generated_files:
            return jsonify({
                "message": f"PDFs institucionais e formulários estilo projeto.py gerados para {len(generated_files)} alunos",
                "generated_forms": generated_files,
                "projeto_style_forms": formularios_gerados,
                "test_title": test.title,
                "total_questions": len(questions),
                "total_students": len(students)
            }), 200
        else:
            return jsonify({"error": "Nenhum PDF foi gerado"}), 400
            
    except Exception as e:
        logging.error(f"Erro ao gerar PDFs institucionais: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test-deteccao-bolhas', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def testar_deteccao_bolhas():
    """
    Rota de teste para verificar se a detecção de bolhas está funcionando
    com correção de perspectiva
    
    Body:
        - image: Imagem do gabarito preenchido (base64)
    
    Returns:
        - Resultado da detecção de bolhas
        - Respostas detectadas
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
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
                    image_data = base64.b64encode(base64.b64decode(image_base64)).decode('utf-8')
                    image_data = f"data:image/jpeg;base64,{image_data}"
            except Exception as e:
                return jsonify({"error": "Formato de dados inválido"}), 400
        
        if not image_data:
            return jsonify({"error": "Imagem não fornecida"}), 400
        
        # Testar detecção usando o serviço
        from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
        pdf_generator = PhysicalTestPDFGenerator()
        
        result = pdf_generator.testar_deteccao_bolhas(image_data)
        
        if result.get('success'):
            return jsonify({
                "message": "Teste de detecção concluído",
                "resultado": result
            }), 200
        else:
            return jsonify({
                "error": result.get('error', 'Erro desconhecido')
            }), 400
            
    except Exception as e:
        logging.error(f"Erro no teste de detecção: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/process-correction', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def process_physical_correction(test_id):
    """
    Processa correção de gabarito físico preenchido
    
    Body:
        - image: Imagem do gabarito preenchido (base64 ou file)
        - correction_image_url (opcional): URL para salvar imagem corrigida
    
    Returns:
        - Resultado da correção
        - Nota e classificação do aluno
        - Imagem corrigida (opcional)
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
            return jsonify({"error": "Você só pode processar correções de suas próprias provas"}), 403
        
        # Obter dados da imagem e parâmetros opcionais
        image_data = None
        student_id = None
        class_test_id = None
        
        if 'image' in request.files:
            # Upload de arquivo
            file = request.files['image']
            if file and file.filename:
                image_data = file.read()
            # Não precisamos mais de parâmetros adicionais
        else:
            # Tentar obter dados JSON (mais flexível)
            try:
                data = request.get_json() or {}
                if 'image' in data:
                    # Base64
                    image_base64 = data['image']
                    if image_base64.startswith('data:image'):
                        image_base64 = image_base64.split(',')[1]
                    image_data = base64.b64decode(image_base64)
                # Não precisamos mais de parâmetros adicionais
            except Exception as e:
                # Se não conseguir obter JSON, tentar form data
                try:
                    image_base64 = request.form.get('image')
                    if image_base64:
                        if image_base64.startswith('data:image'):
                            image_base64 = image_base64.split(',')[1]
                        image_data = base64.b64decode(image_base64)
                    # Não precisamos mais de parâmetros adicionais
                except Exception as e2:
                    return jsonify({"error": "Formato de dados inválido. Envie como JSON ou form-data"}), 400
        
        if not image_data:
            return jsonify({"error": "Imagem não fornecida"}), 400
        
        # Processar correção usando nossa nova função completa
        from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
        pdf_generator = PhysicalTestPDFGenerator()
        
        # Converter image_data para base64 string se necessário
        if isinstance(image_data, bytes):
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            image_data_str = f"data:image/jpeg;base64,{image_base64}"
        else:
            image_data_str = image_data
        
        # Usar função de correção completa (QR code + detecção + salvamento)
        print(f"🎯 USANDO PROCESSAMENTO COMPLETO (QR + DETECÇÃO + SALVAMENTO)")
        result = pdf_generator.processar_correcao_completa(test_id, image_data_str)
        
        if result.get('success'):
            # Preparar dados de resposta
            response_data = {
                "message": "Correção processada com sucesso",
                "student_id": result['student_id'],
                "test_id": result['test_id'],
                "correct_answers": result['correct_answers'],
                "total_questions": result['total_questions'],
                "score_percentage": result['score_percentage'],
                "grade": result['grade'],
                "proficiency": result['proficiency'],
                "classification": result['classification'],
                "answers_detected": result['answers_detected'],
                "student_answers": result['student_answers'],
                "evaluation_result_id": result['evaluation_result_id'],
                "method": "complete_processing"
            }
            
            return jsonify(response_data), 200
        else:
            return jsonify({
                "error": result['error']
            }), 400
            
    except Exception as e:
        logging.error(f"Erro ao processar correção física: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/forms', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
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
        
        service = PhysicalTestFormService()
        
        if student_id:
            form = service.get_physical_form_by_student(test_id, student_id)
            if form:
                return jsonify({"form": form}), 200
            else:
                return jsonify({"error": "Formulário não encontrado para este aluno"}), 404
        else:
            forms = service.get_physical_forms_by_test(test_id)
            return jsonify({
                "forms": forms,
                "total": len(forms)
            }), 200
            
    except Exception as e:
        logging.error(f"Erro ao buscar formulários físicos: {str(e)}")
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
        logging.error(f"Erro ao baixar formulário físico: {str(e)}")
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
        
        # Criar arquivo ZIP em memória
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for form in forms:
                if form.form_pdf_data:
                    # Buscar nome do aluno
                    from app.models.student import Student
                    student = Student.query.get(form.student_id)
                    student_name = student.name if student else f"aluno_{form.student_id}"
                    
                    # Nome do arquivo no ZIP
                    filename = f"prova_{test.title}_{student_name}_{form.student_id}.pdf"
                    # Limpar caracteres inválidos do nome do arquivo
                    filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                    
                    # Adicionar PDF ao ZIP
                    zip_file.writestr(filename, form.form_pdf_data)
        
        zip_buffer.seek(0)
        
        # Nome do arquivo ZIP
        zip_filename = f"provas_{test.title}_{test_id}.zip"
        zip_filename = "".join(c for c in zip_filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        
        # Enviar arquivo ZIP
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        logging.error(f"Erro ao baixar todos os formulários físicos: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/status', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
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
        logging.error(f"Erro ao verificar status da prova: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/answer-key', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def download_answer_key(test_id):
    """
    Download do gabarito da prova (apenas para professores)
    
    Returns:
        - Arquivo PDF do gabarito
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
            return jsonify({"error": "Você não tem permissão para baixar o gabarito desta prova"}), 403
        
        # Buscar formulário físico que contém o gabarito (primeiro registro)
        form = PhysicalTestForm.query.filter_by(test_id=test_id).first()
        
        if not form or not form.answer_sheet_data:
            return jsonify({"error": "Gabarito não encontrado"}), 404
        
        # Criar arquivo temporário em memória
        from io import BytesIO
        pdf_buffer = BytesIO(form.answer_sheet_data)
        pdf_buffer.seek(0)
        
        # Enviar arquivo do banco
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"gabarito_{test_id}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logging.error(f"Erro ao baixar gabarito: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/form/<string:form_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def delete_physical_form(form_id):
    """
    Exclui um formulário físico específico
    
    Returns:
        - Resultado da exclusão
        - Informações sobre dados excluídos
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Buscar formulário físico
        physical_form = PhysicalTestForm.query.get(form_id)
        if not physical_form:
            return jsonify({"error": "Formulário físico não encontrado"}), 404
        
        # Verificar se a prova existe
        test = Test.query.get(physical_form.test_id)
        if not test:
            return jsonify({"error": "Prova não encontrada"}), 404
        
        # Verificar permissões do professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode excluir formulários de suas próprias provas"}), 403
        
        # Excluir formulário usando o serviço
        service = PhysicalTestFormService()
        result = service.delete_physical_form(form_id)
        
        if result['success']:
            return jsonify({
                "message": result['message'],
                "deleted_form_id": result['deleted_form_id'],
                "test_id": result['test_id'],
                "student_id": result['student_id'],
                "deleted_answers": result['deleted_answers']
            }), 200
        else:
            return jsonify({
                "error": result['error']
            }), 400
            
    except Exception as e:
        logging.error(f"Erro ao excluir formulário físico: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/forms', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def delete_all_physical_forms_by_test(test_id):
    """
    Exclui todos os formulários físicos de uma prova
    
    Returns:
        - Resultado da exclusão
        - Quantidade de formulários e respostas excluídos
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
            return jsonify({"error": "Você só pode excluir formulários de suas próprias provas"}), 403
        
        # Excluir todos os formulários usando o serviço
        service = PhysicalTestFormService()
        result = service.delete_all_physical_forms_by_test(test_id)
        
        if result['success']:
            return jsonify({
                "message": result['message'],
                "test_id": result['test_id'],
                "deleted_forms": result['deleted_forms'],
                "deleted_answers": result['deleted_answers']
            }), 200
        else:
            return jsonify({
                "error": result['error']
            }), 400
            
    except Exception as e:
        logging.error(f"Erro ao excluir formulários físicos da prova: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/test/<string:test_id>/student/<string:student_id>/generate', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def generate_individual_physical_form(test_id, student_id):
    """
    Gera formulário físico individual para um aluno específico
    
    Body:
        - output_dir (opcional): Diretório para salvar o PDF
    
    Returns:
        - Formulário gerado para o aluno
        - Informações do PDF e gabarito
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
        from app.models.student import Student
        student = Student.query.get(student_id)
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404
        
        # Verificar permissões do professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode gerar formulários para suas próprias provas"}), 403
        
        # Verificar se o professor tem acesso ao aluno (mesma escola)
        if user['role'] == 'professor':
            # Buscar o professor pelo user_id
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Professor não encontrado"}), 404
            
            # Buscar turmas do professor
            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids = [tc.class_id for tc in teacher_classes]
            
            if student.class_id not in teacher_class_ids:
                return jsonify({"error": "Você não tem acesso a este aluno"}), 403
        
        # Obter diretório de saída
        try:
            data = request.get_json() or {}
        except:
            data = {}
        output_dir = data.get('output_dir', 'physical_forms')
        
        # Gerar formulário individual
        service = PhysicalTestFormService()
        result = service.generate_individual_physical_form(test_id, student_id, output_dir)
        
        if result['success']:
            return jsonify({
                "message": result['message'],
                "generated_forms": result['generated_forms'],
                "test_title": result['test_title'],
                "student_name": result['student_name'],
                "total_questions": result['total_questions'],
                "forms": result['forms']
            }), 200
        else:
            return jsonify({
                "error": result['error'],
                "existing_form_id": result.get('existing_form_id')
            }), 400
            
    except Exception as e:
        logging.error(f"Erro ao gerar formulário individual: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@bp.route('/tests', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_tests_with_physical_forms():
    """
    Lista provas que têm formulários físicos gerados
    
    Query params:
        - student_id (opcional): Filtrar por aluno específico
        - page (opcional): Página para paginação (padrão: 1)
        - per_page (opcional): Itens por página (padrão: 10, máximo: 100)
        - only_count (opcional): Apenas contagem (true/false)
    
    Returns:
        - Lista de provas com informações dos formulários físicos
        - Metadados de paginação
    """
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
        
        # Parâmetro opcional para filtrar por aluno específico
        student_id = request.args.get('student_id')
        
        # Verificar se o aluno existe (se especificado)
        student = None
        if student_id:
            from app.models.student import Student
            student = Student.query.get(student_id)
            if not student:
                return jsonify({"error": "Aluno não encontrado"}), 404
            
            # Verificar permissões do professor para o aluno
            if user['role'] == 'professor':
                from app.models.teacher import Teacher
                from app.models.teacherClass import TeacherClass
                
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if not teacher:
                    return jsonify({"error": "Professor não encontrado"}), 404
                
                # Verificar se o professor tem acesso ao aluno
                teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                teacher_class_ids = [tc.class_id for tc in teacher_classes]
                
                if student.class_id not in teacher_class_ids:
                    return jsonify({"error": "Você não tem acesso a este aluno"}), 403
        
        # Buscar formulários físicos
        if student_id:
            physical_forms = PhysicalTestForm.query.filter_by(student_id=student_id).all()
        else:
            physical_forms = PhysicalTestForm.query.all()
        
        if not physical_forms:
            response_data = {
                "message": "Nenhum formulário físico encontrado",
                "data": [],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": 0,
                    "pages": 0,
                    "has_next": False,
                    "has_prev": False,
                    "next_num": None,
                    "prev_num": None
                }
            }
            
            if student_id:
                response_data["student"] = {
                    "id": student.id,
                    "name": student.name
                }
            
            return jsonify(response_data), 200
        
        # Obter IDs das provas que têm formulários físicos
        test_ids = list(set([form.test_id for form in physical_forms]))
        
        # Buscar provas
        from app.models.test import Test
        from sqlalchemy.orm import joinedload
        
        query = Test.query.options(
            joinedload(Test.creator),
            joinedload(Test.subject_rel),
            joinedload(Test.grade)
        ).filter(Test.id.in_(test_ids))
        
        # Aplicar filtros de permissão
        if user['role'] == 'professor':
            query = query.filter(Test.created_by == user['id'])
        
        # Se é apenas contagem, retornar rapidamente
        if only_count:
            total = query.count()
            return jsonify({"total": total}), 200
        
        # Aplicar paginação
        paginated_query = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        tests = paginated_query.items
        
        # Criar dicionário de formulários físicos por test_id
        forms_by_test = {}
        for form in physical_forms:
            if form.test_id not in forms_by_test:
                forms_by_test[form.test_id] = []
            forms_by_test[form.test_id].append(form.to_dict())
        
        # Preparar resposta com informações dos formulários físicos
        tests_data = []
        for test in tests:
            test_forms = forms_by_test.get(test.id, [])
            
            # Se filtrando por aluno, mostrar apenas formulários desse aluno
            if student_id:
                test_forms = [form for form in test_forms if form.get('student_id') == student_id]
            
            test_data = {
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
                "status": test.status,
                "created_by": test.created_by,
                "created_at": test.created_at.isoformat() if test.created_at else None,
                "creator": {
                    "id": test.creator.id,
                    "name": test.creator.name,
                    "email": test.creator.email
                } if test.creator else None,
                "physical_forms": test_forms,
                "physical_forms_count": len(test_forms)
            }
            tests_data.append(test_data)
        
        # Resposta com metadados de paginação
        response_data = {
            "data": tests_data,
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
        
        if student_id:
            response_data["student"] = {
                "id": student.id,
                "name": student.name
            }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar provas com formulários físicos: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500

def _save_evaluation_result(test_id: str, correction_result: Dict) -> bool:
    """
    Salva resultado da correção na tabela evaluation_results
    """
    try:
        student_id = correction_result['student_id']
        evaluation_data = correction_result.get('evaluation_results')
        
        if not evaluation_data:
            return False
        
        # Verificar se já existe resultado
        existing_result = EvaluationResult.query.filter_by(
            test_id=test_id,
            student_id=student_id
        ).first()
        
        if existing_result:
            # Atualizar resultado existente
            existing_result.correct_answers = evaluation_data['correct_answers']
            existing_result.total_questions = evaluation_data['total_questions']
            existing_result.score_percentage = evaluation_data['score_percentage']
            existing_result.grade = evaluation_data['grade']
            existing_result.proficiency = evaluation_data['proficiency']
            existing_result.classification = evaluation_data['classification']
            existing_result.calculated_at = datetime.utcnow()
        else:
            # Criar novo resultado
            # Nota: session_id pode ser None para correções físicas
            new_result = EvaluationResult(
                test_id=test_id,
                student_id=student_id,
                session_id=None,  # Para correções físicas
                correct_answers=evaluation_data['correct_answers'],
                total_questions=evaluation_data['total_questions'],
                score_percentage=evaluation_data['score_percentage'],
                grade=evaluation_data['grade'],
                proficiency=evaluation_data['proficiency'],
                classification=evaluation_data['classification']
            )
            db.session.add(new_result)
        
        db.session.commit()
        return True
        
    except Exception as e:
        logging.error(f"Erro ao salvar resultado da avaliação: {str(e)}")
        db.session.rollback()
        return False


