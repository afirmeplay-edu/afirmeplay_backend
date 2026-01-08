# -*- coding: utf-8 -*-
"""
Serviço para gerenciamento de respostas de formulários socioeconômicos
"""

from app import db
from app.socioeconomic_forms.models import Form, FormRecipient, FormResponse, FormQuestion
from sqlalchemy.exc import SQLAlchemyError
import logging
from datetime import datetime


class ResponseService:
    """Serviço para operações relacionadas a respostas de formulários"""
    
    @staticmethod
    def get_form_for_response(form_id, user_id):
        """
        Obtém formulário para resposta do usuário
        
        Args:
            form_id: ID do formulário
            user_id: ID do usuário
            
        Returns:
            dict: Dados do formulário com resposta atual (se existir)
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                return None
            
            if not form.is_active:
                raise ValueError("Formulário não está ativo")
            
            # Verificar se há deadline e se já passou
            if form.deadline and datetime.utcnow() > form.deadline:
                raise ValueError("Prazo para responder este questionário expirou")
            
            # Verificar se usuário é destinatário
            recipient = FormRecipient.query.filter_by(
                form_id=form_id,
                user_id=user_id
            ).first()
            
            if not recipient:
                raise ValueError("Você não é destinatário deste questionário")
            
            # Buscar resposta atual (se existir)
            current_response = FormResponse.query.filter_by(
                form_id=form_id,
                user_id=user_id
            ).first()
            
            # Preparar dados do formulário
            form_data = {
                'formId': form.id,
                'title': form.title,
                'description': form.description,
                'instructions': form.instructions,
                'deadline': form.deadline.isoformat() if form.deadline else None,
                'questions': [q.to_dict() for q in form.questions]
            }
            
            # Adicionar resposta atual se existir
            if current_response:
                form_data['currentResponse'] = {
                    'id': current_response.id,
                    'status': current_response.status,
                    'startedAt': current_response.started_at.isoformat() if current_response.started_at else None,
                    'responses': current_response.responses or {}
                }
            else:
                form_data['currentResponse'] = None
            
            return form_data
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao buscar formulário para resposta: {str(e)}")
            raise
    
    @staticmethod
    def save_response(form_id, user_id, responses_data, is_complete=False):
        """
        Salva resposta parcial ou completa
        
        Args:
            form_id: ID do formulário
            user_id: ID do usuário
            responses_data: Dicionário com as respostas
            is_complete: Se a resposta está completa
            
        Returns:
            FormResponse: Objeto da resposta salva
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                raise ValueError("Formulário não encontrado")
            
            if not form.is_active:
                raise ValueError("Formulário não está ativo")
            
            # Verificar deadline
            if form.deadline and datetime.utcnow() > form.deadline:
                raise ValueError("Prazo para responder este questionário expirou")
            
            # Verificar se usuário é destinatário
            recipient = FormRecipient.query.filter_by(
                form_id=form_id,
                user_id=user_id
            ).first()
            
            if not recipient:
                raise ValueError("Você não é destinatário deste questionário")
            
            # Validar respostas obrigatórias se is_complete=True
            if is_complete:
                ResponseService._validate_required_questions(form, responses_data)
            
            # Buscar resposta existente ou criar nova
            response = FormResponse.query.filter_by(
                form_id=form_id,
                user_id=user_id
            ).first()
            
            # Determinar respostas finais (mescladas ou não)
            if not response:
                final_responses = responses_data
                response = FormResponse(
                    form_id=form_id,
                    user_id=user_id,
                    recipient_id=recipient.id,
                    status='in_progress',
                    responses=final_responses,
                    started_at=datetime.utcnow()
                )
                db.session.add(response)
                
                # Atualizar recipient
                if recipient.status == 'pending':
                    recipient.status = 'in_progress'
                    recipient.started_at = datetime.utcnow()
            else:
                # Fazer merge defensivo das respostas
                final_responses = ResponseService._merge_responses(
                    form, 
                    response.responses or {}, 
                    responses_data
                )
                response.responses = final_responses
                response.updated_at = datetime.utcnow()
            
            # Calcular progresso usando as respostas finais
            # Contar o total de campos que precisam ser respondidos
            # (questões simples + questões com subperguntas contam como 1 cada)
            total_fields = 0
            for question in form.questions:
                if question.sub_questions:
                    # Questão com subperguntas: conta como 1 campo
                    # (todas as subperguntas devem estar respondidas)
                    total_fields += 1
                else:
                    # Questão simples: conta 1
                    total_fields += 1
            
            # Contar campos respondidos usando as respostas finais
            # Para questões com subperguntas, verificar se todas foram respondidas
            answered_fields = 0
            
            for question in form.questions:
                question_id = question.question_id
                
                if question.sub_questions:
                    # Para questões com subperguntas, verificar se todas as subperguntas foram respondidas
                    all_subquestions_answered = True
                    for sub_q in question.sub_questions:
                        sub_id = sub_q.get('id')
                        if sub_id:
                            if sub_id not in final_responses:
                                all_subquestions_answered = False
                                break
                            value = final_responses.get(sub_id)
                            if value is None or value == '':
                                all_subquestions_answered = False
                                break
                    
                    if all_subquestions_answered:
                        answered_fields += 1
                else:
                    # Questão simples: verificar se foi respondida
                    if question_id in final_responses:
                        value = final_responses.get(question_id)
                        if value is not None and value != '':
                            answered_fields += 1
            
            progress = (answered_fields / total_fields * 100) if total_fields > 0 else 0
            response.progress = round(progress, 2)
            
            # Se completo, finalizar
            if is_complete:
                response.status = 'completed'
                response.completed_at = datetime.utcnow()
                recipient.status = 'completed'
                recipient.completed_at = datetime.utcnow()
                
                # Calcular tempo gasto
                if response.started_at:
                    time_spent = (datetime.utcnow() - response.started_at).total_seconds()
                    response.time_spent = int(time_spent)
            
            db.session.commit()
            return response
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao salvar resposta: {str(e)}")
            raise
    
    @staticmethod
    def _merge_responses(form, existing_responses, new_responses):
        """
        Faz merge defensivo das respostas, preservando respostas existentes
        e aplicando lógica inteligente para questões com subperguntas.
        
        Args:
            form: Objeto Form com todas as questões
            existing_responses: Dicionário com respostas existentes no banco
            new_responses: Dicionário com novas respostas recebidas do frontend
            
        Returns:
            dict: Dicionário com respostas mescladas
        """
        # Criar mapa de questões: question_id -> lista de sub_question_ids
        question_map = {}
        sub_question_to_parent = {}
        
        for question in form.questions:
            question_id = question.question_id
            question_map[question_id] = []
            
            if question.sub_questions:
                for sub_q in question.sub_questions:
                    sub_id = sub_q.get('id')
                    if sub_id:
                        question_map[question_id].append(sub_id)
                        sub_question_to_parent[sub_id] = question_id
        
        # Identificar quais questões foram mencionadas no payload
        mentioned_questions = set()
        for key in new_responses.keys():
            # Verificar se é uma subpergunta
            if key in sub_question_to_parent:
                mentioned_questions.add(sub_question_to_parent[key])
            # Ou se é uma questão simples
            elif key in question_map:
                mentioned_questions.add(key)
        
        # Iniciar com respostas existentes
        merged = existing_responses.copy() if existing_responses else {}
        
        # Processar cada questão do formulário
        for question in form.questions:
            question_id = question.question_id
            
            if question.sub_questions:
                # Questão com subperguntas
                if question_id in mentioned_questions:
                    # Questão foi mencionada no payload - remover subperguntas antigas e adicionar novas
                    # Remover todas as subperguntas existentes desta questão
                    for sub_id in question_map[question_id]:
                        if sub_id in merged:
                            del merged[sub_id]
                    
                    # Adicionar apenas as subperguntas que vieram no payload
                    for sub_id in question_map[question_id]:
                        if sub_id in new_responses:
                            value = new_responses[sub_id]
                            # Só adicionar se o valor não for vazio/None
                            if value is not None and value != '':
                                merged[sub_id] = value
                # Se questão não foi mencionada, preservar subperguntas existentes
            else:
                # Questão simples
                if question_id in new_responses:
                    # Substituir valor se veio no payload
                    merged[question_id] = new_responses[question_id]
                # Se não veio no payload, preservar valor existente
        
        return merged
    
    @staticmethod
    def _validate_required_questions(form, responses_data):
        """
        Valida se todas as questões obrigatórias foram respondidas
        
        Args:
            form: Objeto Form
            responses_data: Dicionário com respostas
            
        Raises:
            ValueError: Se alguma questão obrigatória não foi respondida
        """
        required_questions = [q for q in form.questions if q.required]
        
        # Função auxiliar para verificar se uma resposta é válida
        def is_valid_response(value):
            if value is None:
                return False
            if isinstance(value, str):
                return value.strip() != ''
            if isinstance(value, (list, dict)):
                return len(value) > 0
            if isinstance(value, bool):
                return True  # True e False são válidos
            # Números e outros tipos são válidos
            return True
        
        missing_questions = []
        for question in required_questions:
            question_id = question.question_id
            has_response = False
            
            # Se a questão tem subperguntas, verificar se todas foram respondidas
            if question.sub_questions:
                all_subquestions_answered = True
                for sub_q in question.sub_questions:
                    sub_id = sub_q.get('id')
                    if sub_id:
                        if sub_id not in responses_data:
                            all_subquestions_answered = False
                            break
                        if not is_valid_response(responses_data.get(sub_id)):
                            all_subquestions_answered = False
                            break
                
                if all_subquestions_answered:
                    has_response = True
                else:
                    missing_questions.append(question.text)
            
            # Se a questão não tem subperguntas, verificar se a questão principal foi respondida
            else:
                if question_id in responses_data:
                    if is_valid_response(responses_data.get(question_id)):
                        has_response = True
                
                if not has_response:
                    missing_questions.append(question.text)
        
        if missing_questions:
            raise ValueError(f"Questões obrigatórias não respondidas: {', '.join(missing_questions[:3])}")
    
    @staticmethod
    def get_user_response(form_id, user_id):
        """
        Obtém resposta do usuário para um formulário
        
        Args:
            form_id: ID do formulário
            user_id: ID do usuário
            
        Returns:
            FormResponse ou None
        """
        try:
            response = FormResponse.query.filter_by(
                form_id=form_id,
                user_id=user_id
            ).first()
            
            return response
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao buscar resposta: {str(e)}")
            raise
    
    @staticmethod
    def list_form_responses(form_id, status=None, school_id=None, page=1, limit=20):
        """
        Lista todas as respostas de um formulário
        
        Args:
            form_id: ID do formulário
            status: Filtrar por status (opcional)
            school_id: Filtrar por escola (opcional)
            page: Número da página
            limit: Itens por página
            
        Returns:
            dict: Dicionário com 'data' e 'pagination'
        """
        try:
            query = FormResponse.query.filter_by(form_id=form_id)
            
            if status:
                query = query.filter(FormResponse.status == status)
            
            if school_id:
                # Filtrar por escola via recipient
                query = query.join(FormRecipient).filter(FormRecipient.school_id == school_id)
            
            # Ordenar por data de conclusão (mais recentes primeiro)
            query = query.order_by(FormResponse.completed_at.desc().nullslast(), FormResponse.updated_at.desc())
            
            # Paginação
            pagination = query.paginate(page=page, per_page=limit, error_out=False)
            
            # Preparar dados
            responses_data = []
            for response in pagination.items:
                response_dict = response.to_dict(include_responses=True)
                
                # Adicionar informações do usuário
                if response.user:
                    response_dict['userName'] = response.user.name
                    response_dict['userEmail'] = response.user.email
                
                # Adicionar informações da escola via recipient
                if response.recipient and response.recipient.school:
                    response_dict['schoolId'] = response.recipient.school_id
                    response_dict['schoolName'] = response.recipient.school.name
                
                responses_data.append(response_dict)
            
            return {
                'data': responses_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': pagination.total,
                    'totalPages': pagination.pages
                }
            }
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao listar respostas: {str(e)}")
            raise

