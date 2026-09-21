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
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
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
            selected_classes: Lista opcional de IDs de turmas (quando informada, restringe o escopo)
            
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
            
            # 1. Buscar turmas das séries/escolas selecionadas
            # class.school_id é VARCHAR → comparar com strings para evitar operator does not exist: character varying = uuid
            school_ids_uuids = ensure_uuid_list(school_ids)
            school_ids_str = [str(s) for s in school_ids_uuids]

            query = Class.query.filter(Class.grade_id.in_(grade_uuids))

            if len(school_ids_str) == 1:
                query = query.filter(Class.school_id == school_ids_str[0])
            else:
                query = query.filter(Class.school_id.in_(school_ids_str))

            # Se selected_classes for fornecido, filtrar apenas essas turmas
            if selected_classes:
                class_ids_uuids = ensure_uuid_list(selected_classes)
                if len(class_ids_uuids) == 1:
                    query = query.filter(Class.id == class_ids_uuids[0])
                else:
                    query = query.filter(Class.id.in_(class_ids_uuids))

            classes = query.all()
            
            print("[distribution/aluno-jovem] school_ids=%s grades_count=%s classes_filter=%s → turmas encontradas: %s" % (
                school_ids_str,
                len(grade_uuids),
                len(selected_classes) if selected_classes else 0,
                len(classes),
            ))
            if not classes:
                return recipients  # Nenhuma turma encontrada
            
            class_ids = [c.id for c in classes]
            
            # 2. Buscar todos os alunos dessas turmas
            students = Student.query.filter(
                Student.class_id.in_(class_ids),
                Student.user_id.isnot(None)
            ).all()
            
            total_alunos_turmas = Student.query.filter(Student.class_id.in_(class_ids)).count()
            sem_user_id = Student.query.filter(Student.class_id.in_(class_ids), Student.user_id.is_(None)).count()
            print("[distribution/aluno-jovem] alunos nas turmas: total=%s com user_id=%s sem user_id=%s → destinatários: %s" % (total_alunos_turmas, len(students), sem_user_id, len(students)))
            if sem_user_id:
                print("[distribution/aluno-jovem] aviso: %s aluno(s) nas turmas sem user_id (não entram como destinatário)" % sem_user_id)
            
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
            # class.school_id é VARCHAR → comparar com strings para evitar operator does not exist: character varying = uuid
            school_ids_uuids = ensure_uuid_list(school_ids)
            school_ids_str = [str(s) for s in school_ids_uuids]
            
            # Construir query de forma que evite inferência de tipo incorreta quando há apenas 1 elemento
            query = Class.query.filter(Class.grade_id.in_(grade_uuids))
            
            if len(school_ids_str) == 1:
                query = query.filter(Class.school_id == school_ids_str[0])
            else:
                query = query.filter(Class.school_id.in_(school_ids_str))
            
            # Se selected_classes for fornecido, filtrar apenas essas turmas
            # Converter class_ids para UUID (Class.id é UUID)
            if selected_classes:
                class_ids_uuids = ensure_uuid_list(selected_classes)
                # Usar == quando há apenas 1 elemento para evitar inferência de tipo incorreta
                if len(class_ids_uuids) == 1:
                    query = query.filter(Class.id == class_ids_uuids[0])
                else:
                    query = query.filter(Class.id.in_(class_ids_uuids))
            
            classes = query.all()
            
            print("[distribution/aluno-velho] school_ids=%s grades_count=%s → turmas encontradas: %s" % (school_ids_str, len(grade_uuids), len(classes)))
            if not classes:
                return recipients  # Nenhuma turma encontrada
            
            class_ids = [c.id for c in classes]
            
            # 2. Buscar todos os alunos dessas turmas
            students = Student.query.filter(
                Student.class_id.in_(class_ids),
                Student.user_id.isnot(None)
            ).all()
            
            total_alunos_turmas = Student.query.filter(Student.class_id.in_(class_ids)).count()
            sem_user_id = Student.query.filter(Student.class_id.in_(class_ids), Student.user_id.is_(None)).count()
            print("[distribution/aluno-velho] alunos nas turmas: total=%s com user_id=%s sem user_id=%s → destinatários: %s" % (total_alunos_turmas, len(students), sem_user_id, len(students)))
            if sem_user_id:
                print("[distribution/aluno-velho] aviso: %s aluno(s) nas turmas sem user_id (não entram como destinatário)" % sem_user_id)
            
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
                # school.id é VARCHAR → comparar com strings
                school_ids_str = [str(s) for s in school_ids]
                schools = School.query.filter(School.id.in_(school_ids_str)).all()
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
                from app.socioeconomic_forms.services.filter_utils import normalize_id_list

                # Prioridade: turma > serie > escola > municipio > estado
                if filters.get('turma'):
                    # Filtrar apenas pela turma específica
                    turma_ids = normalize_id_list(filters['turma'])
                    if turma_ids:
                        turma_id_uuid = ensure_uuid(turma_ids[0])
                        turma = Class.query.get(turma_id_uuid)
                        if turma and turma.school_id:
                            school_ids = [turma.school_id]
                elif filters.get('serie'):
                    # Filtrar por série na escola
                    if filters.get('escola'):
                        school_ids = normalize_id_list(filters['escola'])
                    else:
                        # Buscar todas as escolas que têm turmas dessa série
                        serie_ids = normalize_id_list(filters['serie'])
                        grade_uuids = ensure_uuid_list(serie_ids) if serie_ids else []
                        classes = Class.query.filter(Class.grade_id.in_(grade_uuids)).all() if grade_uuids else []
                        school_ids = list(set([c.school_id for c in classes if c.school_id]))
                elif filters.get('escola'):
                    school_ids = normalize_id_list(filters['escola'])
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
                from app.socioeconomic_forms.services.filter_utils import normalize_id_list
                grade_ids = normalize_id_list(filters['serie'])
            elif selected_grades:
                grade_ids = selected_grades
            
            # Determinar turmas baseado nos filtros
            class_ids = []
            if filters and filters.get('turma'):
                from app.socioeconomic_forms.services.filter_utils import normalize_id_list
                class_ids = normalize_id_list(filters['turma'])
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

    @staticmethod
    def _normalize_id_list(values):
        if not values:
            return []
        return [str(v) for v in values if v is not None]

    @staticmethod
    def _student_matches_form_scope(form, school_id, grade_id, class_id):
        """Verifica se a colocação atual do aluno entra no escopo persistido do form."""
        from app.socioeconomic_forms.services.filter_utils import filter_value_includes_id

        if form.form_type not in ('aluno-jovem', 'aluno-velho'):
            return False
        if not school_id or not grade_id:
            return False

        school_id = str(school_id)
        grade_id = str(grade_id)
        class_id = str(class_id) if class_id else None

        selected_schools = DistributionService._normalize_id_list(form.selected_schools)
        selected_grades = DistributionService._normalize_id_list(form.selected_grades)
        selected_classes = DistributionService._normalize_id_list(form.selected_classes)
        filters = form.filters or {}

        if filters.get('turma'):
            if not filter_value_includes_id(filters['turma'], class_id):
                return False
        if filters.get('serie') and not filter_value_includes_id(filters['serie'], grade_id):
            return False
        if filters.get('escola') and not filter_value_includes_id(filters['escola'], school_id):
            # selected_schools pode ampliar o escopo; se filter.escola diverge, respeitar filter
            if not selected_schools or school_id not in selected_schools:
                return False

        if selected_schools and school_id not in selected_schools:
            return False

        if selected_classes:
            return bool(class_id and class_id in selected_classes)

        if selected_grades:
            return grade_id in selected_grades

        # Sem séries/turmas no form: não dá para inferir com segurança
        return False

    @staticmethod
    def _add_recipient_if_missing(form, user_id, school_id):
        existing = FormRecipient.query.filter_by(
            form_id=form.id,
            user_id=user_id,
        ).first()
        if existing:
            return False
        recipient = FormRecipient(
            form_id=form.id,
            user_id=user_id,
            school_id=school_id,
            status='pending',
            sent_at=datetime.utcnow(),
        )
        db.session.add(recipient)
        return True

    @staticmethod
    def ensure_recipients_for_student(student, commit=False):
        """
        Garante FormRecipient em formulários ativos cujo escopo inclui a
        colocação atual do aluno (escola/série/turma).

        Usado quando o aluno é criado ou entra/muda de turma depois do form.
        """
        try:
            if not student or not getattr(student, 'user_id', None):
                return 0
            if not getattr(student, 'class_id', None) or not getattr(student, 'school_id', None):
                return 0

            school_id = str(student.school_id)
            class_id = str(student.class_id) if student.class_id else None
            grade_id = str(student.grade_id) if student.grade_id else None

            if not grade_id and student.class_id:
                cls = Class.query.get(student.class_id)
                if cls and cls.grade_id:
                    grade_id = str(cls.grade_id)

            if not grade_id:
                return 0

            forms = Form.query.filter(
                Form.is_active.is_(True),
                Form.form_type.in_(['aluno-jovem', 'aluno-velho']),
            ).all()

            created = 0
            for form in forms:
                if not DistributionService._student_matches_form_scope(
                    form, school_id, grade_id, class_id
                ):
                    continue
                if DistributionService._add_recipient_if_missing(
                    form, student.user_id, school_id
                ):
                    created += 1

            if commit and created:
                db.session.commit()

            if created:
                logging.info(
                    "[distribution/sync] student_id=%s user_id=%s → %s FormRecipient(s) criado(s)",
                    getattr(student, 'id', None),
                    student.user_id,
                    created,
                )
            return created
        except SQLAlchemyError as e:
            if commit:
                db.session.rollback()
            logging.error(f"Erro ao sincronizar recipients do aluno: {str(e)}")
            raise

    @staticmethod
    def sync_missing_recipients_for_form(form, commit=False):
        """
        Reprocessa o escopo do form e cria FormRecipient apenas para alunos
        que ainda não estão na lista (não remove existentes).
        """
        try:
            if not form or form.form_type not in ('aluno-jovem', 'aluno-velho'):
                return 0
            if not form.is_active:
                return 0

            recipients_data = DistributionService.determine_recipients_by_filters(
                form.form_type,
                filters=form.filters,
                selected_schools=form.selected_schools,
                selected_grades=form.selected_grades,
                selected_classes=form.selected_classes if form.selected_classes else None,
            )

            created = 0
            for recipient_data in recipients_data:
                if DistributionService._add_recipient_if_missing(
                    form,
                    recipient_data['user_id'],
                    recipient_data.get('school_id'),
                ):
                    created += 1

            if commit and created:
                db.session.commit()

            if created:
                logging.info(
                    "[distribution/sync] form_id=%s → %s FormRecipient(s) faltantes criados",
                    form.id,
                    created,
                )
            return created
        except SQLAlchemyError as e:
            if commit:
                db.session.rollback()
            logging.error(f"Erro ao sincronizar recipients do formulário: {str(e)}")
            raise

    @staticmethod
    def sync_missing_recipients_for_school(school_id, commit=False):
        """Sincroniza recipients faltantes de forms ativos que abrangem a escola."""
        if not school_id:
            return 0
        school_id = str(school_id)
        forms = Form.query.filter(
            Form.is_active.is_(True),
            Form.form_type.in_(['aluno-jovem', 'aluno-velho']),
        ).all()
        created = 0
        for form in forms:
            from app.socioeconomic_forms.services.filter_utils import filter_value_includes_id

            selected_schools = DistributionService._normalize_id_list(form.selected_schools)
            filters = form.filters or {}
            in_scope = False
            if selected_schools and school_id in selected_schools:
                in_scope = True
            elif filters.get('escola') and filter_value_includes_id(filters['escola'], school_id):
                in_scope = True
            elif not selected_schools and not filters.get('escola'):
                # Sem escola no escopo: ainda pode ter recipients nessa escola
                has_rec = FormRecipient.query.filter_by(
                    form_id=form.id, school_id=school_id
                ).first()
                in_scope = bool(has_rec)
            if not in_scope:
                continue
            created += DistributionService.sync_missing_recipients_for_form(form, commit=False)
        if commit and created:
            db.session.commit()
        return created

