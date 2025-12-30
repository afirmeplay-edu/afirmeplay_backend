# -*- coding: utf-8 -*-
"""
Serviço para geração de relatórios e estatísticas de formulários socioeconômicos
"""

from app import db
from app.socioeconomic_forms.models import Form, FormResponse, FormRecipient
from sqlalchemy.exc import SQLAlchemyError
from collections import defaultdict
import logging
from datetime import datetime


class ReportService:
    """Serviço para geração de relatórios e estatísticas"""
    
    @staticmethod
    def get_form_report(form_id, group_by='all'):
        """
        Gera relatório agregado de um formulário
        
        Args:
            form_id: ID do formulário
            group_by: Agrupar por ('school', 'question', 'all')
            
        Returns:
            dict: Relatório agregado
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                return None
            
            # Buscar todas as respostas completas
            responses = FormResponse.query.filter_by(
                form_id=form_id,
                status='completed'
            ).all()
            
            total_responses = len(responses)
            
            # Estatísticas por questão
            by_question = ReportService._aggregate_by_question(form, responses)
            
            # Estatísticas por escola
            by_school = {}
            if group_by in ['school', 'all']:
                by_school = ReportService._aggregate_by_school(form, responses)
            
            return {
                'formId': form.id,
                'formTitle': form.title,
                'totalResponses': total_responses,
                'completionRate': ReportService._calculate_completion_rate(form),
                'statistics': {
                    'byQuestion': by_question,
                    'bySchool': by_school if group_by in ['school', 'all'] else {}
                },
                'generatedAt': datetime.utcnow().isoformat()
            }
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao gerar relatório: {str(e)}")
            raise
    
    @staticmethod
    def _aggregate_by_question(form, responses):
        """
        Agrega estatísticas por questão
        
        Args:
            form: Objeto Form
            responses: Lista de FormResponse
            
        Returns:
            dict: Estatísticas por questão
        """
        by_question = {}
        
        for question in form.questions:
            question_stats = {
                'question': question.text,
                'type': question.type,
                'responses': {},
                'percentages': {}
            }
            
            # Contar respostas para cada opção
            response_counts = defaultdict(int)
            total_responses_for_question = 0
            
            for response in responses:
                responses_data = response.responses or {}
                
                # Para questões com subperguntas
                if question.sub_questions:
                    for sub_q in question.sub_questions:
                        sub_id = sub_q.get('id')
                        if sub_id in responses_data:
                            answer = responses_data[sub_id]
                            if answer is not None and answer != '':
                                response_counts[sub_id] = response_counts.get(sub_id, {})
                                if isinstance(response_counts[sub_id], dict):
                                    response_counts[sub_id] = defaultdict(int)
                                response_counts[sub_id][str(answer)] += 1
                                total_responses_for_question += 1
                else:
                    # Questão simples
                    answer = responses_data.get(question.question_id)
                    if answer is not None and answer != '':
                        response_counts[str(answer)] += 1
                        total_responses_for_question += 1
            
            # Converter defaultdict para dict normal
            if question.sub_questions:
                question_stats['responses'] = {
                    sub_id: dict(counts) if isinstance(counts, defaultdict) else counts
                    for sub_id, counts in response_counts.items()
                }
            else:
                question_stats['responses'] = dict(response_counts)
                
                # Calcular percentuais
                if total_responses_for_question > 0:
                    question_stats['percentages'] = {
                        option: round((count / total_responses_for_question) * 100, 2)
                        for option, count in question_stats['responses'].items()
                    }
            
            by_question[question.question_id] = question_stats
        
        return by_question
    
    @staticmethod
    def _aggregate_by_school(form, responses):
        """
        Agrega estatísticas por escola
        
        Args:
            form: Objeto Form
            responses: Lista de FormResponse
            
        Returns:
            dict: Estatísticas por escola
        """
        by_school = defaultdict(lambda: {
            'schoolName': '',
            'totalResponses': 0,
            'completionRate': 0.0,
            'responses': {}
        })
        
        for response in responses:
            if response.recipient and response.recipient.school:
                school_id = response.recipient.school_id
                school_name = response.recipient.school.name
                
                by_school[school_id]['schoolName'] = school_name
                by_school[school_id]['totalResponses'] += 1
                
                # Agregar respostas por questão
                responses_data = response.responses or {}
                for question in form.questions:
                    if question.question_id not in by_school[school_id]['responses']:
                        by_school[school_id]['responses'][question.question_id] = defaultdict(int)
                    
                    if question.sub_questions:
                        for sub_q in question.sub_questions:
                            sub_id = sub_q.get('id')
                            if sub_id in responses_data:
                                answer = responses_data[sub_id]
                                if answer is not None and answer != '':
                                    by_school[school_id]['responses'][question.question_id][sub_id] = \
                                        by_school[school_id]['responses'][question.question_id].get(sub_id, defaultdict(int))
                                    by_school[school_id]['responses'][question.question_id][sub_id][str(answer)] += 1
                    else:
                        answer = responses_data.get(question.question_id)
                        if answer is not None and answer != '':
                            by_school[school_id]['responses'][question.question_id][str(answer)] += 1
        
        # Calcular taxa de conclusão por escola
        for school_id in by_school:
            total_recipients = FormRecipient.query.filter_by(
                form_id=form.id,
                school_id=school_id
            ).count()
            
            completed = FormRecipient.query.filter_by(
                form_id=form.id,
                school_id=school_id,
                status='completed'
            ).count()
            
            by_school[school_id]['completionRate'] = round(
                (completed / total_recipients * 100) if total_recipients > 0 else 0, 2
            )
        
        # Converter defaultdict para dict normal
        return {
            school_id: {
                'schoolName': data['schoolName'],
                'totalResponses': data['totalResponses'],
                'completionRate': data['completionRate'],
                'responses': {
                    q_id: dict(q_responses) if isinstance(q_responses, defaultdict) else q_responses
                    for q_id, q_responses in data['responses'].items()
                }
            }
            for school_id, data in by_school.items()
        }
    
    @staticmethod
    def _calculate_completion_rate(form):
        """
        Calcula taxa de conclusão do formulário
        
        Args:
            form: Objeto Form
            
        Returns:
            float: Taxa de conclusão (0-100)
        """
        total_recipients = FormRecipient.query.filter_by(form_id=form.id).count()
        completed = FormRecipient.query.filter_by(
            form_id=form.id,
            status='completed'
        ).count()
        
        return round((completed / total_recipients * 100) if total_recipients > 0 else 0, 2)
    
    @staticmethod
    def get_general_statistics(form_type=None, start_date=None, end_date=None):
        """
        Obtém estatísticas gerais de todos os formulários
        
        Args:
            form_type: Filtrar por tipo (opcional)
            start_date: Data inicial (opcional)
            end_date: Data final (opcional)
            
        Returns:
            dict: Estatísticas gerais
        """
        try:
            query = Form.query
            
            if form_type:
                query = query.filter(Form.form_type == form_type)
            
            if start_date:
                query = query.filter(Form.created_at >= start_date)
            
            if end_date:
                query = query.filter(Form.created_at <= end_date)
            
            forms = query.all()
            
            total_forms = len(forms)
            active_forms = len([f for f in forms if f.is_active])
            
            # Calcular totais de respostas
            total_responses = 0
            completion_rates = []
            
            for form in forms:
                recipients = FormRecipient.query.filter_by(form_id=form.id).count()
                completed = FormRecipient.query.filter_by(
                    form_id=form.id,
                    status='completed'
                ).count()
                
                total_responses += completed
                
                if recipients > 0:
                    completion_rates.append((completed / recipients) * 100)
            
            average_completion_rate = round(
                sum(completion_rates) / len(completion_rates) if completion_rates else 0, 2
            )
            
            # Estatísticas por tipo
            by_type = defaultdict(lambda: {
                'total': 0,
                'active': 0,
                'totalResponses': 0,
                'completionRate': 0.0
            })
            
            for form in forms:
                form_type_key = form.form_type
                by_type[form_type_key]['total'] += 1
                
                if form.is_active:
                    by_type[form_type_key]['active'] += 1
                
                recipients = FormRecipient.query.filter_by(form_id=form.id).count()
                completed = FormRecipient.query.filter_by(
                    form_id=form.id,
                    status='completed'
                ).count()
                
                by_type[form_type_key]['totalResponses'] += completed
                
                if recipients > 0:
                    completion_rate = (completed / recipients) * 100
                    # Média ponderada
                    current_rate = by_type[form_type_key]['completionRate']
                    current_total = by_type[form_type_key]['total']
                    by_type[form_type_key]['completionRate'] = round(
                        ((current_rate * (current_total - 1)) + completion_rate) / current_total, 2
                    )
            
            return {
                'totalForms': total_forms,
                'activeForms': active_forms,
                'totalResponses': total_responses,
                'averageCompletionRate': average_completion_rate,
                'byType': dict(by_type)
            }
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao calcular estatísticas gerais: {str(e)}")
            raise

