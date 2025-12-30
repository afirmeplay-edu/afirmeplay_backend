# -*- coding: utf-8 -*-
"""
Serviço para gerenciamento de formulários socioeconômicos
"""

from app import db
from app.socioeconomic_forms.models import Form, FormQuestion
from sqlalchemy.exc import SQLAlchemyError
import logging
from datetime import datetime


class FormService:
    """Serviço para operações CRUD de formulários"""
    
    @staticmethod
    def create_form(data, created_by):
        """
        Cria um novo formulário
        
        Args:
            data: Dicionário com dados do formulário
            created_by: ID do usuário criador
            
        Returns:
            Form: Objeto do formulário criado
        """
        try:
            form_type = data['formType']
            
            # Validar selectedGrades para tipos de alunos
            if form_type in ['aluno-jovem', 'aluno-velho']:
                selected_grades = data.get('selectedGrades', [])
                if not selected_grades or len(selected_grades) == 0:
                    raise ValueError(f"selectedGrades é obrigatório para formulários do tipo {form_type}")
            
            # Criar formulário
            form = Form(
                title=data['title'],
                description=data.get('description'),
                form_type=form_type,
                target_groups=data.get('targetGroups', []),
                selected_schools=data.get('selectedSchools'),
                selected_grades=data.get('selectedGrades'),
                selected_tecadmin_users=data.get('selectedTecAdminUsers'),
                is_active=data.get('isActive', True),
                deadline=datetime.fromisoformat(data['deadline'].replace('Z', '+00:00')) if data.get('deadline') else None,
                instructions=data.get('instructions'),
                created_by=created_by
            )
            
            db.session.add(form)
            db.session.flush()  # Para obter o ID do formulário
            
            # Criar questões
            if 'questions' in data:
                for q_data in data['questions']:
                    question = FormQuestion(
                        form_id=form.id,
                        question_id=q_data['id'],
                        text=q_data['text'],
                        type=q_data['type'],
                        options=q_data.get('options'),
                        sub_questions=q_data.get('subQuestions'),
                        min_value=q_data.get('min'),
                        max_value=q_data.get('max'),
                        option_id=q_data.get('optionId'),
                        option_text=q_data.get('optionText'),
                        required=q_data.get('required', False),
                        question_order=q_data.get('order', 0),
                        depends_on=q_data.get('dependsOn')
                    )
                    db.session.add(question)
            
            db.session.commit()
            return form
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao criar formulário: {str(e)}")
            raise
    
    @staticmethod
    def get_form(form_id, include_questions=False, include_statistics=False):
        """
        Obtém um formulário por ID
        
        Args:
            form_id: ID do formulário
            include_questions: Se deve incluir questões
            include_statistics: Se deve incluir estatísticas
            
        Returns:
            Form ou None
        """
        try:
            form = Form.query.get(form_id)
            return form
        except SQLAlchemyError as e:
            logging.error(f"Erro ao buscar formulário: {str(e)}")
            raise
    
    @staticmethod
    def list_forms(form_type=None, is_active=None, page=1, limit=20):
        """
        Lista formulários com paginação
        
        Args:
            form_type: Filtrar por tipo (opcional)
            is_active: Filtrar por status ativo (opcional)
            page: Número da página
            limit: Itens por página
            
        Returns:
            dict: Dicionário com 'data' e 'pagination'
        """
        try:
            query = Form.query
            
            if form_type:
                query = query.filter(Form.form_type == form_type)
            
            if is_active is not None:
                query = query.filter(Form.is_active == is_active)
            
            # Ordenar por data de criação (mais recentes primeiro)
            query = query.order_by(Form.created_at.desc())
            
            # Paginação
            pagination = query.paginate(page=page, per_page=limit, error_out=False)
            
            # Calcular estatísticas básicas para cada formulário
            forms_data = []
            for form in pagination.items:
                form_dict = form.to_dict(include_questions=False, include_statistics=True)
                forms_data.append(form_dict)
            
            return {
                'data': forms_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': pagination.total,
                    'totalPages': pagination.pages
                }
            }
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao listar formulários: {str(e)}")
            raise
    
    @staticmethod
    def update_form(form_id, data):
        """
        Atualiza um formulário
        
        Args:
            form_id: ID do formulário
            data: Dicionário com dados para atualizar
            
        Returns:
            Form: Objeto do formulário atualizado
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                return None
            
            # Atualizar campos básicos
            if 'title' in data:
                form.title = data['title']
            if 'description' in data:
                form.description = data.get('description')
            if 'formType' in data:
                form.form_type = data['formType']
            if 'targetGroups' in data:
                form.target_groups = data['targetGroups']
            if 'selectedSchools' in data:
                form.selected_schools = data['selectedSchools']
            if 'selectedTecAdminUsers' in data:
                form.selected_tecadmin_users = data['selectedTecAdminUsers']
            if 'isActive' in data:
                form.is_active = data['isActive']
            if 'deadline' in data:
                form.deadline = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00')) if data.get('deadline') else None
            if 'instructions' in data:
                form.instructions = data.get('instructions')
            
            # Atualizar questões se fornecidas
            if 'questions' in data:
                # Deletar questões antigas
                FormQuestion.query.filter_by(form_id=form_id).delete()
                
                # Criar novas questões
                for q_data in data['questions']:
                    question = FormQuestion(
                        form_id=form.id,
                        question_id=q_data['id'],
                        text=q_data['text'],
                        type=q_data['type'],
                        options=q_data.get('options'),
                        sub_questions=q_data.get('subQuestions'),
                        min_value=q_data.get('min'),
                        max_value=q_data.get('max'),
                        option_id=q_data.get('optionId'),
                        option_text=q_data.get('optionText'),
                        required=q_data.get('required', False),
                        question_order=q_data.get('order', 0),
                        depends_on=q_data.get('dependsOn')
                    )
                    db.session.add(question)
            
            db.session.commit()
            return form
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao atualizar formulário: {str(e)}")
            raise
    
    @staticmethod
    def delete_form(form_id):
        """
        Deleta um formulário
        
        Args:
            form_id: ID do formulário
            
        Returns:
            bool: True se deletado com sucesso
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                return False
            
            db.session.delete(form)
            db.session.commit()
            return True
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao deletar formulário: {str(e)}")
            raise
    
    @staticmethod
    def duplicate_form(form_id, new_title=None, is_active=False):
        """
        Duplica um formulário
        
        Args:
            form_id: ID do formulário a duplicar
            new_title: Título para o novo formulário (opcional)
            is_active: Se o novo formulário deve estar ativo
            
        Returns:
            Form: Objeto do formulário duplicado
        """
        try:
            original_form = Form.query.get(form_id)
            if not original_form:
                return None
            
            # Criar novo formulário
            new_form = Form(
                title=new_title or f"Cópia de {original_form.title}",
                description=original_form.description,
                form_type=original_form.form_type,
                target_groups=original_form.target_groups,
                selected_schools=original_form.selected_schools,
                selected_grades=original_form.selected_grades,
                selected_tecadmin_users=original_form.selected_tecadmin_users,
                is_active=is_active,
                deadline=original_form.deadline,
                instructions=original_form.instructions,
                created_by=original_form.created_by
            )
            
            db.session.add(new_form)
            db.session.flush()
            
            # Duplicar questões
            for original_question in original_form.questions:
                new_question = FormQuestion(
                    form_id=new_form.id,
                    question_id=original_question.question_id,
                    text=original_question.text,
                    type=original_question.type,
                    options=original_question.options,
                    sub_questions=original_question.sub_questions,
                    min_value=original_question.min_value,
                    max_value=original_question.max_value,
                    option_id=original_question.option_id,
                    option_text=original_question.option_text,
                    required=original_question.required,
                    question_order=original_question.question_order,
                    depends_on=original_question.depends_on
                )
                db.session.add(new_question)
            
            db.session.commit()
            return new_form
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao duplicar formulário: {str(e)}")
            raise

