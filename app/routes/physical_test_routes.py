# -*- coding: utf-8 -*-
"""
Rotas para sistema de formulários físicos de provas
"""

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.services.physical_test_form_service import PhysicalTestFormService
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
    Gera formulários físicos para uma prova específica
    
    Body:
        - output_dir (opcional): Diretório para salvar os PDFs
    
    Returns:
        - Lista de formulários gerados
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
            return jsonify({"error": "Você só pode gerar formulários para suas próprias provas"}), 403
        
        # Obter diretório de saída
        try:
            data = request.get_json() or {}
        except:
            data = {}
        output_dir = data.get('output_dir', 'physical_forms')
        
        # Gerar formulários
        service = PhysicalTestFormService()
        result = service.generate_physical_forms(test_id, output_dir)
        
        if result['success']:
            return jsonify({
                "message": result['message'],
                "generated_forms": result['generated_forms'],
                "test_title": result['test_title'],
                "total_questions": result['total_questions'],
                "total_students": result['total_students'],
                "forms": result['forms']
            }), 200
        else:
            return jsonify({
                "error": result['error']
            }), 400
            
    except Exception as e:
        logging.error(f"Erro ao gerar formulários físicos: {str(e)}")
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
        
        # Obter dados da imagem
        image_data = None
        correction_image_url = None
        
        if 'image' in request.files:
            # Upload de arquivo
            file = request.files['image']
            if file and file.filename:
                image_data = file.read()
        elif 'image' in request.json:
            # Base64
            try:
                image_base64 = request.json['image']
                if image_base64.startswith('data:image'):
                    image_base64 = image_base64.split(',')[1]
                image_data = base64.b64decode(image_base64)
            except Exception as e:
                return jsonify({"error": "Formato de imagem inválido"}), 400
        
        if not image_data:
            return jsonify({"error": "Imagem não fornecida"}), 400
        
        # Obter URL da imagem corrigida
        data = request.get_json() or {}
        correction_image_url = data.get('correction_image_url')
        
        # Processar correção
        service = PhysicalTestFormService()
        result = service.process_physical_correction(test_id, image_data, correction_image_url)
        
        if result['success']:
            # Salvar resultado na tabela evaluation_results se necessário
            if result.get('evaluation_results'):
                self._save_evaluation_result(test_id, result)
            
            response_data = {
                "message": result['message'],
                "student_id": result['student_id'],
                "correction_results": result['correction_results'],
                "physical_form_id": result['physical_form_id']
            }
            
            # Adicionar imagem corrigida se disponível
            if 'corrected_image' in result:
                corrected_image_b64 = base64.b64encode(result['corrected_image']).decode('utf-8')
                response_data['corrected_image'] = f"data:image/jpeg;base64,{corrected_image_b64}"
            
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
