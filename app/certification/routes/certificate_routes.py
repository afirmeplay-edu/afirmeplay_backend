# -*- coding: utf-8 -*-
"""
Rotas para API de Certificados
"""
from io import BytesIO

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from app import db
from app.decorators.role_required import role_required, get_current_user_from_token
from app.decorators import requires_city_context
from app.certification.models import CertificateTemplate, Certificate
from app.certification.services.certificate_service import CertificateService
from app.models.student import Student
from app.models.test import Test
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

bp = Blueprint('certificates', __name__, url_prefix='/certificates')

# Error handlers seguindo padrão do app
@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"erro": "Erro no banco de dados", "detalhes": str(error)}), 500

@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error(f"Integrity error: {str(error)}")
    return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(error)}), 400

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"erro": "Erro interno do servidor", "detalhes": str(error)}), 500


# ==================== TEMPLATES DE CERTIFICADOS ====================

@bp.route('/template/<string:evaluation_id>/logo', methods=['GET'])
@jwt_required(locations=['headers', 'query_string'])
@requires_city_context
def get_template_logo(evaluation_id):
    """Proxy autenticado: imagem do logo no MinIO (bucket privado)."""
    try:
        data, ctype = CertificateService.load_template_asset(evaluation_id, 'logo')
        return send_file(
            BytesIO(data),
            mimetype=ctype,
            as_attachment=False,
            max_age=3600,
        )
    except LookupError as e:
        return jsonify({"erro": str(e)}), 404
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao obter logo do template: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao carregar imagem", "detalhes": str(e)}), 500


@bp.route('/template/<string:evaluation_id>/signature', methods=['GET'])
@jwt_required(locations=['headers', 'query_string'])
@requires_city_context
def get_template_signature(evaluation_id):
    """Proxy autenticado: imagem da assinatura no MinIO (bucket privado)."""
    try:
        data, ctype = CertificateService.load_template_asset(
            evaluation_id, 'signature'
        )
        return send_file(
            BytesIO(data),
            mimetype=ctype,
            as_attachment=False,
            max_age=3600,
        )
    except LookupError as e:
        return jsonify({"erro": str(e)}), 404
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao obter assinatura do template: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao carregar imagem", "detalhes": str(e)}), 500


@bp.route('/template/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@requires_city_context
def get_template(evaluation_id):
    """Busca template de certificado para uma avaliação"""
    try:
        template = CertificateService.get_template_by_evaluation(evaluation_id)
        
        if not template:
            return jsonify({"erro": "Template não encontrado"}), 404
        
        return jsonify(template.to_dict()), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar template: {str(e)}")
        return jsonify({"erro": "Erro ao buscar template", "detalhes": str(e)}), 500


@bp.route('/template', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def save_template():
    """Cria ou atualiza template de certificado"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        # Validações
        if not data.get('evaluation_id'):
            return jsonify({"erro": "evaluation_id é obrigatório"}), 400
        
        if not data.get('text_content'):
            return jsonify({"erro": "text_content é obrigatório"}), 400
        
        if not data.get('background_color'):
            return jsonify({"erro": "background_color é obrigatório"}), 400
        
        if not data.get('text_color'):
            return jsonify({"erro": "text_color é obrigatório"}), 400
        
        if not data.get('accent_color'):
            return jsonify({"erro": "accent_color é obrigatório"}), 400
        
        # Verificar se avaliação existe
        test = Test.query.get(data['evaluation_id'])
        if not test:
            return jsonify({"erro": "Avaliação não encontrada"}), 404
        
        # Salvar template
        template = CertificateService.save_template(data)
        
        return jsonify(template.to_dict()), 201 if not data.get('id') else 200
        
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao salvar template: {str(e)}")
        return jsonify({"erro": "Erro ao salvar template", "detalhes": str(e)}), 500


# ==================== APROVAÇÃO DE CERTIFICADOS ====================

@bp.route('/approved-students/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_approved_students(evaluation_id):
    """Retorna lista de alunos aprovados (grade >= 6) de uma avaliação"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Verificar se avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"erro": "Avaliação não encontrada"}), 404
        
        # Buscar alunos aprovados
        approved_students = CertificateService.get_approved_students(evaluation_id)
        
        return jsonify(approved_students), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar alunos aprovados: {str(e)}")
        return jsonify({"erro": "Erro ao buscar alunos aprovados", "detalhes": str(e)}), 500


@bp.route('/approve', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def approve_certificates():
    """Aprova e emite certificados para alunos aprovados"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400
        
        evaluation_id = data.get('evaluation_id')
        if not evaluation_id:
            return jsonify({"erro": "evaluation_id é obrigatório"}), 400
        
        student_ids = data.get('student_ids')  # Opcional
        
        # Aprovar certificados
        result = CertificateService.approve_certificates(evaluation_id, student_ids)
        
        message = f"Certificados processados: {result['total_processed']} emitidos/atualizados"
        if result['errors']:
            message += f". {len(result['errors'])} erros encontrados"
        
        return jsonify({
            "success": True,
            "message": message,
            "certificates_issued": result['certificates_issued'],
            "certificates_updated": result['certificates_updated'],
            "total_processed": result['total_processed'],
            "errors": result['errors'] if result['errors'] else None
        }), 200
        
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao aprovar certificados: {str(e)}")
        return jsonify({"erro": "Erro ao aprovar certificados", "detalhes": str(e)}), 500


# ==================== CONSULTA DE CERTIFICADOS ====================

@bp.route('/me', methods=['GET'])
@jwt_required()
def get_my_certificates():
    """Retorna certificados do aluno logado"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Buscar student vinculado ao user
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return jsonify({"erro": "Aluno não encontrado"}), 404
        
        certificates = CertificateService.get_student_certificates(student.id)
        
        return jsonify([cert.to_dict(include_template=True) for cert in certificates]), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar certificados do aluno: {str(e)}")
        return jsonify({"erro": "Erro ao buscar certificados", "detalhes": str(e)}), 500


@bp.route('/student/<string:student_id>', methods=['GET'])
@jwt_required()
def get_student_certificates(student_id):
    """Retorna certificados de um aluno específico"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Verificar permissão: admin/professor/diretor OU o próprio aluno
        student = Student.query.get(student_id)
        if not student:
            return jsonify({"erro": "Aluno não encontrado"}), 404
        
        # Verificar se é o próprio aluno
        is_own_student = student.user_id == user['id']
        
        # Verificar se tem permissão de admin/professor/etc
        has_permission = user.get('role') in ['admin', 'professor', 'coordenador', 'diretor', 'tecadm']
        
        if not (is_own_student or has_permission):
            return jsonify({"erro": "Acesso negado"}), 403
        
        certificates = CertificateService.get_student_certificates(student_id)
        
        return jsonify([cert.to_dict(include_template=True) for cert in certificates]), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar certificados do aluno: {str(e)}")
        return jsonify({"erro": "Erro ao buscar certificados", "detalhes": str(e)}), 500


@bp.route('/quantidade', methods=['GET'])
@jwt_required()
@requires_city_context
def get_certificates_count():
    """Retorna a quantidade de certificados emitidos no escopo do usuário logado."""
    try:
        from app.services.dashboard_service import DashboardService
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        scope = DashboardService._resolve_scope(user)
        school_ids = DashboardService._extract_school_ids(scope)
        quantidade = CertificateService.count_issued(school_ids)
        return jsonify({"quantidade": quantidade}), 200
    except Exception as e:
        logging.error(f"Erro ao buscar quantidade de certificados: {str(e)}")
        return jsonify({"erro": "Erro ao buscar quantidade de certificados", "detalhes": str(e)}), 500


@bp.route('/<string:certificate_id>', methods=['GET'])
@jwt_required()
def get_certificate(certificate_id):
    """Retorna um certificado específico"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        certificate = CertificateService.get_certificate_by_id(certificate_id)
        if not certificate:
            return jsonify({"erro": "Certificado não encontrado"}), 404
        
        # Verificar permissão: admin/professor/diretor OU o próprio aluno
        student = Student.query.get(certificate.student_id)
        is_own_student = student and student.user_id == user['id']
        has_permission = user.get('role') in ['admin', 'professor', 'coordenador', 'diretor', 'tecadm']
        
        if not (is_own_student or has_permission):
            return jsonify({"erro": "Acesso negado"}), 403
        
        return jsonify(certificate.to_dict(include_template=True)), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar certificado: {str(e)}")
        return jsonify({"erro": "Erro ao buscar certificado", "detalhes": str(e)}), 500
