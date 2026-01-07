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
from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
from app.services.physical_test_form_service import PhysicalTestFormService
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
        logging.error(f"Erro ao extrair usuário do token: {str(e)}")
        return None

# ============================================================================
# ROTAS DE GERAÇÃO DE FORMULÁRIOS
# ============================================================================

@bp.route('/test/<string:test_id>/generate-forms', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def generate_physical_forms(test_id):
    """
    Gera formulários físicos para uma prova específica
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found or token invalid"}), 401
        
        # Buscar prova
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": f"Prova não encontrada: {test_id}"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode gerar formulários de suas próprias provas"}), 403
        
        # Obter dados da requisição
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Validar dados obrigatórios
        required_fields = ['students']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Campo '{field}' é obrigatório"}), 400
        
        students = data['students']
        if not isinstance(students, list) or len(students) == 0:
            return jsonify({"error": "Lista de alunos deve ser um array não vazio"}), 400
        
        # Gerar formulários
        pdf_generator = PhysicalTestPDFGenerator()
        result = pdf_generator.gerar_formularios_adaptativos(test_id, students)
        
        if result['success']:
            return jsonify({
                "message": "Formulários gerados com sucesso",
                "test_id": test_id,
                "total_forms": len(students),
                "forms": result['forms']
            }), 200
        else:
            return jsonify({"error": result['error']}), 500
        
    except Exception as e:
        logging.error(f"Erro ao gerar formulários: {str(e)}")
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
        
        # Processar correção
        pdf_generator = PhysicalTestPDFGenerator()
        
        # Converter image_data para base64 string se necessário
        if isinstance(image_data, bytes):
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            image_data_str = f"data:image/jpeg;base64,{image_base64}"
        else:
            image_data_str = image_data
        
        # Usar função de correção completa (nova implementação)
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
                "evaluation_result_id": result.get('evaluation_result_id')
            }
            
            return jsonify(response_data), 200
        else:
            return jsonify({"error": result.get('error', 'Erro desconhecido na correção')}), 500
        
    except Exception as e:
        logging.error(f"Erro ao processar correção: {str(e)}")
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
        logging.error(f"Erro ao processar correção em lote: {str(e)}")
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
        logging.error(f"Erro ao listar formulários: {str(e)}")
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
        logging.error(f"Erro ao obter formulário: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500
