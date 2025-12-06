# -*- coding: utf-8 -*-
"""
Rotas para geração e correção de cartões resposta
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators.role_required import role_required, get_current_user_from_token
from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.studentClass import Class
from app.models.student import Student
from app.models.user import User
from app.services.answer_sheet_generator import AnswerSheetGenerator
from app.services.answer_sheet_correction import AnswerSheetCorrection
import logging
import base64
import io

bp = Blueprint('answer_sheets', __name__, url_prefix='/answer-sheets')


@bp.route('/generate', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def generate_answer_sheets():
    """
    Gera cartões resposta para uma turma
    
    Body:
        {
            "class_id": "uuid",
            "num_questions": 48,
            "use_blocks": true,
            "blocks_config": {
                "num_blocks": 4,
                "questions_per_block": 12,
                "separate_by_subject": false
            },
            "correct_answers": {
                "1": "A",
                "2": "B",
                ...
            },
            "test_data": {
                "title": "Nome da Prova",
                "municipality": "...",
                "state": "...",
                ...
            },
            "test_id": "uuid" (opcional)
        }
    
    Returns:
        Lista de PDFs gerados (base64)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Validar campos obrigatórios
        class_id = data.get('class_id')
        num_questions = data.get('num_questions')
        correct_answers = data.get('correct_answers')
        test_data = data.get('test_data', {})
        
        if not class_id:
            return jsonify({"error": "class_id é obrigatório"}), 400
        if not num_questions or num_questions <= 0:
            return jsonify({"error": "num_questions deve ser maior que 0"}), 400
        if not correct_answers:
            return jsonify({"error": "correct_answers é obrigatório"}), 400
        
        # Validar turma
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({"error": "Turma não encontrada"}), 404
        
        # Validar permissões
        if user['role'] == 'professor':
            # Verificar se professor tem acesso à turma
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                teacher_class = TeacherClass.query.filter_by(
                    teacher_id=teacher.id,
                    class_id=class_id
                ).first()
                if not teacher_class:
                    return jsonify({"error": "Você não tem acesso a esta turma"}), 403
        
        # Configuração de blocos
        use_blocks = data.get('use_blocks', False)
        blocks_config = data.get('blocks_config', {})
        if use_blocks:
            blocks_config['use_blocks'] = True
            if 'num_blocks' not in blocks_config:
                blocks_config['num_blocks'] = 1
            if 'questions_per_block' not in blocks_config:
                blocks_config['questions_per_block'] = 12
        
        # Salvar gabarito no banco
        gabarito = AnswerSheetGabarito(
            test_id=data.get('test_id'),
            class_id=class_id,
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            title=test_data.get('title', 'Cartão Resposta'),
            created_by=user['id']
        )
        db.session.add(gabarito)
        db.session.commit()
        
        # Preparar test_data completo
        test_data_complete = {
            'id': data.get('test_id'),
            'title': test_data.get('title', 'Cartão Resposta'),
            'municipality': test_data.get('municipality', ''),
            'state': test_data.get('state', ''),
            'department': test_data.get('department', ''),
            'municipality_logo': test_data.get('municipality_logo'),
            'institution': test_data.get('institution', ''),
            'grade_name': test_data.get('grade_name', '')
        }
        
        # Gerar cartões resposta
        generator = AnswerSheetGenerator()
        generated_files = generator.generate_answer_sheets(
            class_id=class_id,
            test_data=test_data_complete,
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            gabarito_id=gabarito.id
        )
        
        # Converter PDFs para base64
        result = []
        for file_info in generated_files:
            pdf_data = file_info.get('pdf_data')
            if pdf_data:
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                result.append({
                    'student_id': file_info['student_id'],
                    'student_name': file_info['student_name'],
                    'pdf_base64': pdf_base64,
                    'gabarito_id': gabarito.id
                })
        
        return jsonify({
            "success": True,
            "gabarito_id": gabarito.id,
            "generated_count": len(result),
            "files": result
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao gerar cartões resposta: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao gerar cartões resposta: {str(e)}"}), 500


@bp.route('/correct', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def correct_answer_sheet():
    """
    Corrige um cartão resposta usando IA
    
    Body:
        {
            "image": "base64_encoded_image",
            "gabarito_id": "uuid" (opcional, se não tiver test_id),
            "test_id": "uuid" (opcional, se não tiver gabarito_id)
        }
    
    Returns:
        Resultado da correção com notas e respostas
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Validar campos
        image_base64 = data.get('image')
        gabarito_id = data.get('gabarito_id')
        test_id = data.get('test_id')
        
        if not image_base64:
            return jsonify({"error": "image é obrigatório"}), 400
        
        if not gabarito_id and not test_id:
            return jsonify({"error": "gabarito_id ou test_id é obrigatório"}), 400
        
        # Decodificar imagem
        try:
            image_data = base64.b64decode(image_base64)
        except Exception as e:
            return jsonify({"error": f"Erro ao decodificar imagem: {str(e)}"}), 400
        
        # Corrigir cartão resposta
        correction_service = AnswerSheetCorrection(debug=True)
        resultado = correction_service.corrigir_cartao_resposta(
            image_data=image_data,
            gabarito_id=gabarito_id,
            test_id=test_id
        )
        
        if not resultado.get('success'):
            return jsonify(resultado), 400
        
        return jsonify(resultado), 200
        
    except Exception as e:
        logging.error(f"Erro ao corrigir cartão resposta: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao corrigir cartão resposta: {str(e)}"}), 500


@bp.route('/gabarito/<string:gabarito_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_gabarito(gabarito_id):
    """
    Busca informações de um gabarito
    
    Returns:
        Dados do gabarito
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            return jsonify({"error": "Gabarito não encontrado"}), 404
        
        return jsonify({
            "id": gabarito.id,
            "test_id": gabarito.test_id,
            "class_id": gabarito.class_id,
            "num_questions": gabarito.num_questions,
            "use_blocks": gabarito.use_blocks,
            "blocks_config": gabarito.blocks_config,
            "correct_answers": gabarito.correct_answers,
            "title": gabarito.title,
            "created_at": gabarito.created_at.isoformat() if gabarito.created_at else None
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar gabarito: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro ao buscar gabarito: {str(e)}"}), 500
