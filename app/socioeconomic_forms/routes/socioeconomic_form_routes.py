# -*- coding: utf-8 -*-
"""
Rotas para API de Formulários Socioeconômicos
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.socioeconomic_forms.services.form_service import FormService
from app.socioeconomic_forms.services.distribution_service import DistributionService
from app.socioeconomic_forms.services.response_service import ResponseService
from app.socioeconomic_forms.services.report_service import ReportService
from app.socioeconomic_forms.models import Form, FormRecipient, FormResponse
from app import db
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import logging

bp = Blueprint('socioeconomic_forms', __name__, url_prefix='/forms')


@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"error": "Database error occurred", "details": str(error)}), 500


@bp.errorhandler(ValueError)
def handle_value_error(error):
    return jsonify({"error": str(error)}), 400


# ==================== GERENCIAMENTO DE FORMULÁRIOS ====================

@bp.route('', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm")
def create_form():
    """Cria um novo questionário"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Validações básicas
        if not data.get('title'):
            return jsonify({"error": "Título é obrigatório"}), 400
        
        if not data.get('formType'):
            return jsonify({"error": "Tipo de formulário é obrigatório"}), 400
        
        # Criar formulário
        form = FormService.create_form(data, user['id'])
        
        # Se filtros ou seleções estiverem presentes, enviar automaticamente
        filters = data.get('filters')
        selected_schools = data.get('selectedSchools', [])
        selected_grades = data.get('selectedGrades', [])
        selected_classes = data.get('selectedClasses', [])
        
        recipients_count = 0
        sent_at = None
        
        if filters or selected_schools or selected_grades or selected_classes:
            # Determinar destinatários e enviar
            recipients_data = DistributionService.determine_recipients_by_filters(
                form.form_type,
                filters=filters,
                selected_schools=selected_schools if selected_schools else None,
                selected_grades=selected_grades if selected_grades else None,
                selected_classes=selected_classes if selected_classes else None
            )
            
            # Criar registros de FormRecipient
            sent_at = datetime.utcnow()
            for recipient_data in recipients_data:
                # Verificar se já existe (evitar duplicatas)
                existing = FormRecipient.query.filter_by(
                    form_id=form.id,
                    user_id=recipient_data['user_id']
                ).first()
                
                if not existing:
                    recipient = FormRecipient(
                        form_id=form.id,
                        user_id=recipient_data['user_id'],
                        school_id=recipient_data.get('school_id'),
                        status='pending',
                        sent_at=sent_at
                    )
                    db.session.add(recipient)
                    recipients_count += 1
            
            db.session.commit()
        
        # Preparar resposta
        response_data = form.to_dict(include_questions=True)
        if recipients_count > 0:
            response_data['recipientsCount'] = recipients_count
            response_data['sentAt'] = sent_at.isoformat() if sent_at else None
        
        return jsonify(response_data), 201
        
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar formulário: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao criar formulário", "details": str(e)}), 500


@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")
def list_forms():
    """Lista questionários"""
    try:
        form_type = request.args.get('formType')
        is_active = request.args.get('isActive')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
        else:
            is_active = None
        
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        
        result = FormService.list_forms(
            form_type=form_type,
            is_active=is_active,
            page=page,
            limit=limit
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar formulários: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar formulários", "details": str(e)}), 500


@bp.route('/<form_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")
def get_form(form_id):
    """Obtém um questionário específico"""
    try:
        include_statistics = request.args.get('includeStatistics', 'false').lower() == 'true'
        
        form = FormService.get_form(
            form_id,
            include_questions=True,
            include_statistics=include_statistics
        )
        
        if not form:
            return jsonify({"error": "Questionário não encontrado"}), 404
        
        form_dict = form.to_dict(include_questions=True, include_statistics=include_statistics)
        
        # Adicionar informações do criador
        if form.creator:
            form_dict['createdBy'] = {
                'id': form.creator.id,
                'name': form.creator.name
            }
        
        return jsonify(form_dict), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar formulário: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar formulário", "details": str(e)}), 500


@bp.route('/<form_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "tecadm")
def update_form(form_id):
    """Atualiza um questionário"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        form = FormService.update_form(form_id, data)
        
        if not form:
            return jsonify({"error": "Questionário não encontrado"}), 404
        
        return jsonify(form.to_dict(include_questions=True)), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao atualizar formulário: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao atualizar formulário", "details": str(e)}), 500


@bp.route('/<form_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "tecadm")
def delete_form(form_id):
    """Deleta um questionário"""
    try:
        success = FormService.delete_form(form_id)
        
        if not success:
            return jsonify({"error": "Questionário não encontrado"}), 404
        
        return '', 204
        
    except Exception as e:
        logging.error(f"Erro ao deletar formulário: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao deletar formulário", "details": str(e)}), 500


@bp.route('/<form_id>/duplicate', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm")
def duplicate_form(form_id):
    """Duplica um questionário"""
    try:
        data = request.get_json() or {}
        new_title = data.get('title')
        is_active = data.get('isActive', False)
        
        new_form = FormService.duplicate_form(form_id, new_title, is_active)
        
        if not new_form:
            return jsonify({"error": "Questionário não encontrado"}), 404
        
        return jsonify({
            'id': new_form.id,
            'title': new_form.title,
            'message': 'Questionário duplicado com sucesso'
        }), 201
        
    except Exception as e:
        logging.error(f"Erro ao duplicar formulário: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao duplicar formulário", "details": str(e)}), 500


# ==================== ENVIO E DISTRIBUIÇÃO ====================

@bp.route('/<form_id>/send', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm")
def send_form(form_id):
    """Envia questionário para grupos de destinatários"""
    try:
        data = request.get_json() or {}
        notify_users = data.get('notifyUsers', True)
        
        result = DistributionService.send_form_to_recipients(form_id, notify_users)
        
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao enviar formulário: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao enviar formulário", "details": str(e)}), 500


@bp.route('/<form_id>/recipients', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def list_recipients(form_id):
    """Lista destinatários do questionário"""
    try:
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        
        query = FormRecipient.query.filter_by(form_id=form_id)
        
        if status:
            query = query.filter(FormRecipient.status == status)
        
        query = query.order_by(FormRecipient.sent_at.desc())
        
        pagination = query.paginate(page=page, per_page=limit, error_out=False)
        
        recipients_data = []
        for recipient in pagination.items:
            recipient_dict = recipient.to_dict(include_user_details=True)
            recipients_data.append(recipient_dict)
        
        # Estatísticas
        total = FormRecipient.query.filter_by(form_id=form_id).count()
        pending = FormRecipient.query.filter_by(form_id=form_id, status='pending').count()
        in_progress = FormRecipient.query.filter_by(form_id=form_id, status='in_progress').count()
        completed = FormRecipient.query.filter_by(form_id=form_id, status='completed').count()
        
        return jsonify({
            'data': recipients_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': pagination.total,
                'totalPages': pagination.pages
            },
            'statistics': {
                'total': total,
                'pending': pending,
                'in_progress': in_progress,
                'completed': completed,
                'completionRate': round((completed / total * 100) if total > 0 else 0, 2)
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar destinatários: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar destinatários", "details": str(e)}), 500


# ==================== RESPOSTAS ====================

@bp.route('/me', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")
def get_my_forms():
    """Lista todos os questionários disponíveis para o usuário logado responder"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        # Buscar todos os recipients do usuário
        recipients = FormRecipient.query.filter_by(
            user_id=user['id']
        ).join(Form).filter(
            Form.is_active == True
        ).all()
        
        # Filtrar por deadline (se houver)
        now = datetime.utcnow()
        
        forms_data = []
        for recipient in recipients:
            form = recipient.form
            
            # Verificar se passou do deadline
            if form.deadline and form.deadline < now:
                continue  # Pular formulários com deadline expirado
            
            # Buscar resposta atual (se existir)
            response = FormResponse.query.filter_by(
                form_id=form.id,
                user_id=user['id']
            ).first()
            
            form_info = {
                'id': form.id,
                'title': form.title,
                'description': form.description,
                'formType': form.form_type,
                'deadline': form.deadline.isoformat() if form.deadline else None,
                'instructions': form.instructions,
                'status': recipient.status,  # pending, in_progress, completed
                'sentAt': recipient.sent_at.isoformat() if recipient.sent_at else None,
                'startedAt': recipient.started_at.isoformat() if recipient.started_at else None,
                'completedAt': recipient.completed_at.isoformat() if recipient.completed_at else None,
                'progress': float(response.progress) if response else 0.0,
                'totalQuestions': len(form.questions)
            }
            
            forms_data.append(form_info)
        
        # Ordenar por data de envio (mais recentes primeiro)
        forms_data.sort(key=lambda x: x['sentAt'] or '', reverse=True)
        
        return jsonify({
            'data': forms_data,
            'total': len(forms_data)
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar questionários do usuário: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar questionários", "details": str(e)}), 500


@bp.route('/<form_id>/respond', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")
def get_form_for_response(form_id):
    """Obtém questionário para resposta"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        form_data = ResponseService.get_form_for_response(form_id, user['id'])
        
        if not form_data:
            return jsonify({"error": "Questionário não encontrado"}), 404
        
        return jsonify(form_data), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao buscar formulário para resposta: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar formulário", "details": str(e)}), 500


@bp.route('/<form_id>/responses', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")
def save_response(form_id):
    """Salva resposta parcial ou completa"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        responses_data = data.get('responses', {})
        is_complete = data.get('isComplete', False)
        
        response = ResponseService.save_response(
            form_id,
            user['id'],
            responses_data,
            is_complete
        )
        
        return jsonify({
            'responseId': response.id,
            'formId': form_id,
            'status': response.status,
            'progress': float(response.progress),
            'savedAt': response.updated_at.isoformat() if response.updated_at else None
        }), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao salvar resposta: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao salvar resposta", "details": str(e)}), 500


@bp.route('/<form_id>/responses/finalize', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")
def finalize_response(form_id):
    """Finaliza resposta"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        responses_data = data.get('responses', {})
        
        response = ResponseService.save_response(
            form_id,
            user['id'],
            responses_data,
            is_complete=True
        )
        
        return jsonify({
            'responseId': response.id,
            'formId': form_id,
            'status': response.status,
            'completedAt': response.completed_at.isoformat() if response.completed_at else None,
            'message': 'Resposta finalizada com sucesso'
        }), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao finalizar resposta: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao finalizar resposta", "details": str(e)}), 500


@bp.route('/<form_id>/responses/me', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")
def get_my_response(form_id):
    """Obtém resposta do usuário"""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        response = ResponseService.get_user_response(form_id, user['id'])
        
        if not response:
            return jsonify({"error": "Resposta não encontrada"}), 404
        
        response_dict = response.to_dict(include_responses=True)
        
        # Calcular tempo gasto se ainda não foi calculado
        if response.started_at and not response.completed_at:
            time_spent = (datetime.utcnow() - response.started_at).total_seconds()
            response_dict['timeSpent'] = int(time_spent)
        
        return jsonify(response_dict), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar resposta: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar resposta", "details": str(e)}), 500


@bp.route('/<form_id>/responses', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def list_responses(form_id):
    """Lista todas as respostas de um questionário"""
    try:
        status = request.args.get('status')
        school_id = request.args.get('schoolId')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        
        result = ResponseService.list_form_responses(
            form_id,
            status=status,
            school_id=school_id,
            page=page,
            limit=limit
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar respostas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar respostas", "details": str(e)}), 500


# ==================== RELATÓRIOS ====================

@bp.route('/<form_id>/reports', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def get_form_report(form_id):
    """Obtém relatório agregado"""
    try:
        group_by = request.args.get('groupBy', 'all')
        
        report = ReportService.get_form_report(form_id, group_by=group_by)
        
        if not report:
            return jsonify({"error": "Questionário não encontrado"}), 404
        
        return jsonify(report), 200
        
    except Exception as e:
        logging.error(f"Erro ao gerar relatório: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao gerar relatório", "details": str(e)}), 500


@bp.route('/reports/statistics', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def get_general_statistics():
    """Obtém estatísticas gerais"""
    try:
        form_type = request.args.get('formType')
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        
        if start_date:
            from datetime import datetime
            start_date = datetime.fromisoformat(start_date)
        
        if end_date:
            from datetime import datetime
            end_date = datetime.fromisoformat(end_date)
        
        statistics = ReportService.get_general_statistics(
            form_type=form_type,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify(statistics), 200
        
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao calcular estatísticas", "details": str(e)}), 500

