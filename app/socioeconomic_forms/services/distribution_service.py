# -*- coding: utf-8 -*-
"""
Serviço para distribuição de formulários socioeconômicos
"""

from app import db
from app.socioeconomic_forms.models import Form, FormRecipient
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User, RoleEnum
from app.models.schoolTeacher import SchoolTeacher
from app.models.grades import Grade
from app.models.educationStage import EducationStage
from app.models.studentClass import Class
from app.models.school import School
from app.models.city import City
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
import logging
from datetime import datetime


class DistributionService:
    """Serviço para distribuição de formulários para destinatários"""
    
    @staticmethod
    def get_aluno_jovem_recipients(school_ids, selected_grades, selected_classes=None):
        """
        Obtém destinatários para questionários de alunos jovens (anos iniciais)
        
        Alunos jovens: 1° ao 5° ano, EJA 1° ao 5° período, Educação Infantil
        
        Args:
            school_ids: Lista de IDs de escolas
            selected_grades: Lista de IDs de séries (obrigatório)
            
        Returns:
            list: Lista de dicionários com user_id e school_id
        """
        try:
            if not selected_grades or len(selected_grades) == 0:
                raise ValueError("selected_grades é obrigatório para aluno-jovem")
            
            recipients = []
            
            # Converter strings para UUID se necessário
            import uuid as uuid_lib
            grade_uuids = []
            for g in selected_grades:
                if isinstance(g, str):
                    try:
                        # Tentar converter string para UUID
                        uuid_obj = uuid_lib.UUID(g)
                        grade_uuids.append(uuid_obj)
                    except (ValueError, AttributeError):
                        # Se falhar, manter como string (pode ser que o banco aceite)
                        grade_uuids.append(g)
                else:
                    grade_uuids.append(g)
            
            # 1. Buscar todas as turmas que pertencem às séries selecionadas e escolas selecionadas
            classes = Class.query.filter(
                Class.grade_id.in_(grade_uuids),
                Class.school_id.in_(school_ids)
            ).all()
            
            if not classes:
                return recipients  # Nenhuma turma encontrada
            
            class_ids = [c.id for c in classes]
            
            # 2. Buscar todos os alunos dessas turmas
            students = Student.query.filter(
                Student.class_id.in_(class_ids),
                Student.user_id.isnot(None)
            ).all()
            
            for student in students:
                if student.user_id:
                    recipients.append({
                        'user_id': student.user_id,
                        'school_id': student.school_id
                    })
            
            return recipients
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao buscar alunos jovens: {str(e)}")
            raise
    
    @staticmethod
    def get_aluno_velho_recipients(school_ids, selected_grades, selected_classes=None):
        """
        Obtém destinatários para questionários de alunos velhos (anos finais)
        
        Alunos velhos: 6° ao 9° ano, EJA 6° ao 9° período
        
        Args:
            school_ids: Lista de IDs de escolas
            selected_grades: Lista de IDs de séries (obrigatório)
            
        Returns:
            list: Lista de dicionários com user_id e school_id
        """
        try:
            if not selected_grades or len(selected_grades) == 0:
                raise ValueError("selected_grades é obrigatório para aluno-velho")
            
            recipients = []
            
            # Converter strings para UUID se necessário
            import uuid as uuid_lib
            grade_uuids = []
            for g in selected_grades:
                if isinstance(g, str):
                    try:
                        # Tentar converter string para UUID
                        uuid_obj = uuid_lib.UUID(g)
                        grade_uuids.append(uuid_obj)
                    except (ValueError, AttributeError):
                        # Se falhar, manter como string (pode ser que o banco aceite)
                        grade_uuids.append(g)
                else:
                    grade_uuids.append(g)
            
            # 1. Buscar todas as turmas que pertencem às séries selecionadas e escolas selecionadas
            query = Class.query.filter(
                Class.grade_id.in_(grade_uuids),
                Class.school_id.in_(school_ids)
            )
            
            # Se selected_classes for fornecido, filtrar apenas essas turmas
            if selected_classes:
                import uuid as uuid_lib
                class_uuids = []
                for c in selected_classes:
                    if isinstance(c, str):
                        try:
                            uuid_obj = uuid_lib.UUID(c)
                            class_uuids.append(uuid_obj)
                        except (ValueError, AttributeError):
                            class_uuids.append(c)
                    else:
                        class_uuids.append(c)
                query = query.filter(Class.id.in_(class_uuids))
            
            classes = query.all()
            
            if not classes:
                return recipients  # Nenhuma turma encontrada
            
            class_ids = [c.id for c in classes]
            
            # 2. Buscar todos os alunos dessas turmas
            students = Student.query.filter(
                Student.class_id.in_(class_ids),
                Student.user_id.isnot(None)
            ).all()
            
            for student in students:
                if student.user_id:
                    recipients.append({
                        'user_id': student.user_id,
                        'school_id': student.school_id
                    })
            
            return recipients
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao buscar alunos velhos: {str(e)}")
            raise
    
    @staticmethod
    def get_professor_recipients(school_ids):
        """
        Obtém destinatários para questionários de professores
        
        Args:
            school_ids: Lista de IDs de escolas
            
        Returns:
            list: Lista de dicionários com user_id e school_id
        """
        try:
            recipients = []
            
            # Buscar professores vinculados às escolas
            school_teachers = SchoolTeacher.query.filter(
                SchoolTeacher.school_id.in_(school_ids)
            ).options(
                joinedload(SchoolTeacher.teacher)
            ).all()
            
            for st in school_teachers:
                if st.teacher and st.teacher.user_id:
                    recipients.append({
                        'user_id': st.teacher.user_id,
                        'school_id': st.school_id
                    })
            
            return recipients
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao buscar professores: {str(e)}")
            raise
    
    @staticmethod
    def get_diretor_recipients(school_ids):
        """
        Obtém destinatários para questionários de diretores
        
        Args:
            school_ids: Lista de IDs de escolas
            
        Returns:
            list: Lista de dicionários com user_id e school_id
        """
        try:
            recipients = []
            
            # Buscar usuários com role 'diretor' vinculados às escolas
            # Diretores podem estar vinculados via Manager.school_id ou diretamente no User
            from app.models.manager import Manager
            
            # Buscar diretores via Manager
            managers = Manager.query.filter(
                Manager.school_id.in_(school_ids),
                Manager.user_id.isnot(None)
            ).all()
            
            for manager in managers:
                if manager.user_id:
                    # Verificar se o user tem role diretor
                    user = User.query.get(manager.user_id)
                    if user and user.role == RoleEnum.DIRETOR:
                        recipients.append({
                            'user_id': manager.user_id,
                            'school_id': manager.school_id
                        })
            
            # Também buscar diretores diretamente no User (caso não tenham Manager)
            users = User.query.filter(
                User.role == RoleEnum.DIRETOR,
                User.id.notin_([m.user_id for m in managers if m.user_id])
            ).all()
            
            # Para diretores sem Manager, precisamos verificar se estão vinculados às escolas
            # Isso pode ser feito via city_id ou outras relações
            # Por enquanto, vamos incluir todos os diretores do mesmo city_id das escolas
            if school_ids:
                from app.models.school import School
                schools = School.query.filter(School.id.in_(school_ids)).all()
                city_ids = [s.city_id for s in schools if s.city_id]
                
                for user in users:
                    if user.city_id in city_ids:
                        # Pegar a primeira escola do city_id como referência
                        school = next((s for s in schools if s.city_id == user.city_id), None)
                        if school:
                            recipients.append({
                                'user_id': user.id,
                                'school_id': school.id
                            })
            
            return recipients
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao buscar diretores: {str(e)}")
            raise
    
    @staticmethod
    def get_secretario_recipients(tecadmin_user_ids):
        """
        Obtém destinatários para questionários de secretários
        
        Args:
            tecadmin_user_ids: Lista de IDs de usuários TecAdmin
            
        Returns:
            list: Lista de dicionários com user_id (school_id será None)
        """
        try:
            recipients = []
            
            # Buscar usuários TecAdmin
            users = User.query.filter(
                User.id.in_(tecadmin_user_ids),
                User.role == RoleEnum.TECADM
            ).all()
            
            for user in users:
                recipients.append({
                    'user_id': user.id,
                    'school_id': None  # Secretários não têm escola específica
                })
            
            return recipients
            
        except SQLAlchemyError as e:
            logging.error(f"Erro ao buscar secretários: {str(e)}")
            raise
    
    @staticmethod
    def determine_recipients_by_filters(form_type, filters=None, selected_schools=None, 
                                         selected_grades=None, selected_classes=None):
        """
        Determina destinatários baseado em filtros hierárquicos e seleções
        
        Args:
            form_type: Tipo do formulário (aluno-jovem, aluno-velho, professor, diretor, secretario)
            filters: Dicionário com filtros {estado, municipio, escola, serie, turma}
            selected_schools: Lista de IDs de escolas
            selected_grades: Lista de IDs de séries
            selected_classes: Lista de IDs de turmas
            
        Returns:
            list: Lista de dicionários com user_id e school_id
        """
        try:
            # Determinar escolas baseado nos filtros
            school_ids = []
            
            if filters:
                # Prioridade: turma > serie > escola > municipio > estado
                if filters.get('turma'):
                    # Filtrar apenas pela turma específica
                    turma = Class.query.get(filters['turma'])
                    if turma and turma.school_id:
                        school_ids = [turma.school_id]
                elif filters.get('serie'):
                    # Filtrar por série na escola
                    if filters.get('escola'):
                        school_ids = [filters['escola']]
                    else:
                        # Buscar todas as escolas que têm turmas dessa série
                        classes = Class.query.filter_by(grade_id=filters['serie']).all()
                        school_ids = list(set([c.school_id for c in classes if c.school_id]))
                elif filters.get('escola'):
                    school_ids = [filters['escola']]
                elif filters.get('municipio'):
                    # Buscar todas as escolas do município
                    schools = School.query.filter_by(city_id=filters['municipio']).all()
                    school_ids = [s.id for s in schools]
                elif filters.get('estado'):
                    # Buscar todas as escolas do estado
                    cities = City.query.filter_by(state=filters['estado']).all()
                    city_ids = [c.id for c in cities]
                    schools = School.query.filter(School.city_id.in_(city_ids)).all()
                    school_ids = [s.id for s in schools]
            
            # Se selected_schools for fornecido, usar essas escolas (ou intersecção)
            if selected_schools:
                if school_ids:
                    # Intersecção: apenas escolas que estão em ambos
                    school_ids = [s for s in school_ids if s in selected_schools]
                else:
                    school_ids = selected_schools
            
            if not school_ids:
                return []
            
            # Determinar séries baseado nos filtros
            grade_ids = []
            if filters and filters.get('serie'):
                grade_ids = [filters['serie']]
            elif selected_grades:
                grade_ids = selected_grades
            
            # Determinar turmas baseado nos filtros
            class_ids = []
            if filters and filters.get('turma'):
                class_ids = [filters['turma']]
            elif selected_classes:
                class_ids = selected_classes
            
            # Chamar método apropriado baseado no tipo de formulário
            if form_type == 'aluno-jovem':
                return DistributionService.get_aluno_jovem_recipients(
                    school_ids, 
                    grade_ids if grade_ids else [],
                    class_ids if class_ids else None
                )
            elif form_type == 'aluno-velho':
                return DistributionService.get_aluno_velho_recipients(
                    school_ids,
                    grade_ids if grade_ids else [],
                    class_ids if class_ids else None
                )
            elif form_type == 'professor':
                return DistributionService.get_professor_recipients(school_ids)
            elif form_type == 'diretor':
                return DistributionService.get_diretor_recipients(school_ids)
            elif form_type == 'secretario':
                # Para secretários, não usa filtros de escola
                # Precisa de selected_tecadmin_users que vem do form
                return []
            else:
                return []
                
        except SQLAlchemyError as e:
            logging.error(f"Erro ao determinar destinatários por filtros: {str(e)}")
            raise
    
    @staticmethod
    def send_form_to_recipients(form_id, notify_users=True):
        """
        Envia formulário para todos os destinatários baseado no tipo
        
        Args:
            form_id: ID do formulário
            notify_users: Se deve criar notificações (futuro)
            
        Returns:
            dict: Estatísticas do envio
        """
        try:
            form = Form.query.get(form_id)
            if not form:
                raise ValueError("Formulário não encontrado")
            
            if not form.is_active:
                raise ValueError("Formulário não está ativo")
            
            # Verificar se já foi enviado (se já tem recipients)
            existing_recipients = FormRecipient.query.filter_by(form_id=form_id).count()
            if existing_recipients > 0:
                raise ValueError("Formulário já foi enviado. Use reenvio se necessário.")
            
            # Identificar destinatários baseado no tipo
            recipients_data = []
            
            # Usar filtros se disponíveis, senão usar método tradicional
            if form.filters or form.selected_classes:
                recipients_data = DistributionService.determine_recipients_by_filters(
                    form.form_type,
                    filters=form.filters,
                    selected_schools=form.selected_schools,
                    selected_grades=form.selected_grades,
                    selected_classes=form.selected_classes
                )
            elif form.form_type == 'aluno-jovem':
                if not form.selected_schools:
                    raise ValueError("Escolas devem ser selecionadas para questionários de alunos")
                if not form.selected_grades:
                    raise ValueError("Séries devem ser selecionadas para questionários de alunos")
                recipients_data = DistributionService.get_aluno_jovem_recipients(
                    form.selected_schools,
                    form.selected_grades
                )
            
            elif form.form_type == 'aluno-velho':
                if not form.selected_schools:
                    raise ValueError("Escolas devem ser selecionadas para questionários de alunos")
                if not form.selected_grades:
                    raise ValueError("Séries devem ser selecionadas para questionários de alunos")
                recipients_data = DistributionService.get_aluno_velho_recipients(
                    form.selected_schools,
                    form.selected_grades
                )
            
            elif form.form_type == 'professor':
                if not form.selected_schools:
                    raise ValueError("Escolas devem ser selecionadas para questionários de professores")
                recipients_data = DistributionService.get_professor_recipients(form.selected_schools)
            
            elif form.form_type == 'diretor':
                if not form.selected_schools:
                    raise ValueError("Escolas devem ser selecionadas para questionários de diretores")
                recipients_data = DistributionService.get_diretor_recipients(form.selected_schools)
            
            elif form.form_type == 'secretario':
                if not form.selected_tecadmin_users:
                    raise ValueError("Usuários TecAdmin devem ser selecionados para questionários de secretários")
                recipients_data = DistributionService.get_secretario_recipients(form.selected_tecadmin_users)
            
            # Criar registros de FormRecipient
            recipients_created = 0
            for recipient_data in recipients_data:
                # Verificar se já existe (evitar duplicatas)
                existing = FormRecipient.query.filter_by(
                    form_id=form_id,
                    user_id=recipient_data['user_id']
                ).first()
                
                if not existing:
                    recipient = FormRecipient(
                        form_id=form_id,
                        user_id=recipient_data['user_id'],
                        school_id=recipient_data.get('school_id'),
                        status='pending',
                        sent_at=datetime.utcnow()
                    )
                    db.session.add(recipient)
                    recipients_created += 1
            
            db.session.commit()
            
            # TODO: Implementar notificações aqui se notify_users=True
            
            return {
                'formId': form_id,
                'totalRecipients': recipients_created,
                'sentAt': datetime.utcnow().isoformat(),
                'notificationsSent': recipients_created if notify_users else 0,
                'emailsSent': 0,  # TODO: Implementar envio de emails
                'message': f'Questionário enviado para {recipients_created} destinatários'
            }
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Erro ao enviar formulário: {str(e)}")
            raise

