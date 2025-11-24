from typing import List, Dict, Any, Set, Tuple
from datetime import datetime
from sqlalchemy import or_, and_
from app import db
from app.models import (
    CalendarEvent,
    CalendarEventTarget,
    CalendarEventUser,
    CalendarVisibilityScope,
    CalendarTargetType,
    User,
    Student,
    Teacher,
    School,
    City,
    Class,
    ClassSubject,
    SchoolTeacher,
    Grade,
    Manager,
)
from app.models.teacherClass import TeacherClass


class CalendarEventService:
    @staticmethod
    def validate_targets_by_role(creator: Dict[str, Any], targets: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Valida se o criador tem permissão para criar eventos para os targets especificados.
        
        Args:
            creator: Dicionário com informações do criador (id, role, city_id)
            targets: Lista de targets no formato [{'target_type': '...', 'target_id': '...'}]
        
        Returns:
            Tuple[bool, str]: (True, '') se válido, (False, mensagem_erro) se inválido
        """
        from app.permissions.utils import get_manager_school, get_manager_city, get_teacher_schools, get_teacher_classes
        
        creator_role = creator.get('role', '').lower()
        
        # Admin pode tudo
        if creator_role == 'admin':
            return True, ''
        
        for target in targets:
            target_type = target.get('target_type', '').upper()
            target_id = target.get('target_id')
            
            if not target_id:
                continue
            
            if creator_role == 'tecadm':
                creator_city_id = creator.get('city_id') or creator.get('tenant_id')
                if not creator_city_id:
                    return False, 'Tecadm não vinculado a um município'
                
                if target_type == 'MUNICIPALITY':
                    if target_id != creator_city_id:
                        return False, 'Acesso negado ao município'
                elif target_type == 'SCHOOL':
                    school = School.query.get(target_id)
                    if not school or school.city_id != creator_city_id:
                        return False, 'Acesso negado à escola'
                elif target_type == 'GRADE':
                    grade = Grade.query.get(target_id)
                    if not grade:
                        return False, 'Série não encontrada'
                    # Buscar escolas que têm turmas dessa série
                    classes = Class.query.filter_by(grade_id=target_id).all()
                    school_ids = {c.school_id for c in classes if c.school_id}
                    # Verificar se todas as escolas pertencem ao município
                    schools = School.query.filter(School.id.in_(list(school_ids))).all()
                    if not all(s.city_id == creator_city_id for s in schools):
                        return False, 'Acesso negado à série'
                elif target_type == 'CLASS':
                    class_obj = Class.query.get(target_id)
                    if not class_obj:
                        return False, 'Turma não encontrada'
                    school = School.query.get(class_obj.school_id) if class_obj.school_id else None
                    if not school or school.city_id != creator_city_id:
                        return False, 'Acesso negado à turma'
                else:
                    return False, 'Tipo de target não permitido para tecadm'
            
            elif creator_role in ['diretor', 'coordenador']:
                manager_school_id = get_manager_school(creator['id'])
                if not manager_school_id:
                    return False, 'Usuário não vinculado a uma escola'
                
                if target_type == 'SCHOOL':
                    if target_id != manager_school_id:
                        return False, 'Acesso negado à escola'
                elif target_type == 'GRADE':
                    grade = Grade.query.get(target_id)
                    if not grade:
                        return False, 'Série não encontrada'
                    # Verificar se a série pertence à escola do manager
                    classes = Class.query.filter_by(grade_id=target_id, school_id=manager_school_id).all()
                    if not classes:
                        return False, 'Acesso negado à série'
                elif target_type == 'CLASS':
                    class_obj = Class.query.get(target_id)
                    if not class_obj:
                        return False, 'Turma não encontrada'
                    if class_obj.school_id != manager_school_id:
                        return False, 'Acesso negado à turma'
                else:
                    return False, 'Tipo de target não permitido para diretor/coordenador'
            
            elif creator_role == 'professor':
                teacher_classes = get_teacher_classes(creator['id'])
                if not teacher_classes:
                    return False, 'Professor não vinculado a nenhuma turma'
                
                if target_type == 'CLASS':
                    if target_id not in teacher_classes:
                        return False, 'Acesso negado à turma'
                else:
                    return False, 'Professor só pode enviar para turmas vinculadas'
            
            else:
                return False, f'Role {creator_role} não autorizado para criar eventos'
        
        return True, ''
    
    @staticmethod
    def create_event(data: Dict[str, Any], creator: Dict[str, Any]) -> CalendarEvent:
        event = CalendarEvent(
            title=data['title'],
            description=data.get('description'),
            location=data.get('location'),
            start_at=datetime.fromisoformat(data['start_at']),
            end_at=datetime.fromisoformat(data['end_at']) if data.get('end_at') else None,
            all_day=bool(data.get('all_day', False)),
            timezone=data.get('timezone'),
            recurrence_rule=data.get('recurrence_rule'),
            is_published=bool(data.get('is_published', False)),
            created_by_user_id=creator['id'],
            created_by_role=creator['role'],
            visibility_scope=CalendarVisibilityScope(data['visibility_scope'])
        )
        db.session.add(event)
        db.session.flush()

        targets = data.get('targets', [])
        for t in targets:
            db.session.add(CalendarEventTarget(
                event_id=event.id,
                target_type=CalendarTargetType(t['target_type']),
                target_id=str(t['target_id'])
            ))

        # Materializar destinatários
        CalendarEventService.materialize_recipients(event.id)

        db.session.commit()
        return event

    @staticmethod
    def update_event(event: CalendarEvent, data: Dict[str, Any]) -> CalendarEvent:
        for field in ['title', 'description', 'location', 'timezone', 'recurrence_rule']:
            if field in data:
                setattr(event, field, data[field])

        if 'start_at' in data:
            event.start_at = datetime.fromisoformat(data['start_at'])
        if 'end_at' in data:
            event.end_at = datetime.fromisoformat(data['end_at']) if data['end_at'] else None
        if 'all_day' in data:
            event.all_day = bool(data['all_day'])
        if 'is_published' in data:
            event.is_published = bool(data['is_published'])

        if 'visibility_scope' in data:
            event.visibility_scope = CalendarVisibilityScope(data['visibility_scope'])

        if 'targets' in data:
            # Replace targets
            CalendarEventTarget.query.filter_by(event_id=event.id).delete()
            for t in data['targets']:
                db.session.add(CalendarEventTarget(
                    event_id=event.id,
                    target_type=CalendarTargetType(t['target_type']),
                    target_id=str(t['target_id'])
                ))
            # Re-materialize recipients
            CalendarEventUser.query.filter_by(event_id=event.id).delete()
            CalendarEventService.materialize_recipients(event.id)

        db.session.commit()
        return event

    @staticmethod
    def publish_event(event: CalendarEvent) -> CalendarEvent:
        event.is_published = True
        db.session.commit()
        return event

    @staticmethod
    def materialize_recipients(event_id: str) -> None:
        event: CalendarEvent = CalendarEvent.query.get(event_id)
        if not event:
            return

        user_ids: Set[str] = set()
        context_map: Dict[str, Tuple[str, str, str]] = {}

        def add_user(uid: str, school_id: str = None, class_id: str = None, role_snapshot: str = None):
            if uid:
                user_ids.add(uid)
                context_map[uid] = (school_id, class_id, role_snapshot)

        # Buscar role do criador para determinar comportamento
        creator = User.query.get(event.created_by_user_id)
        creator_role = None
        if creator:
            if hasattr(creator.role, 'value'):
                creator_role = creator.role.value
            else:
                creator_role = creator.role
        if not creator_role:
            creator_role = event.created_by_role

        targets = CalendarEventTarget.query.filter_by(event_id=event_id).all()

        for tgt in targets:
            if tgt.target_type == CalendarTargetType.USER:
                add_user(tgt.target_id)
            elif tgt.target_type == CalendarTargetType.CLASS:
                # Se criado por professor: apenas alunos da turma
                if creator_role == 'professor':
                    for s in Student.query.filter_by(class_id=tgt.target_id).all():
                        add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                else:
                    # Se criado por diretor/coordenador/admin/tecadm: todos da turma
                    # Students
                    for s in Student.query.filter_by(class_id=tgt.target_id).all():
                        add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                    # Buscar escola da turma primeiro
                    class_obj = Class.query.get(tgt.target_id)
                    school_id_for_class = class_obj.school_id if class_obj else None
                    # Teachers da turma
                    teacher_ids = [cs.teacher_id for cs in ClassSubject.query.filter_by(class_id=tgt.target_id).all()]
                    if teacher_ids:
                        for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                            add_user(t.user_id, school_id=school_id_for_class, class_id=tgt.target_id, role_snapshot='professor')
                    # Incluir diretores/coordenadores da escola
                    if class_obj and class_obj.school_id:
                        managers = Manager.query.filter_by(school_id=class_obj.school_id).all()
                        for manager in managers:
                            if manager.user_id:
                                user = User.query.get(manager.user_id)
                                if user:
                                    user_role = user.role.value if hasattr(user.role, 'value') else user.role
                                    if user_role in ['diretor', 'coordenador']:
                                        add_user(manager.user_id, school_id=class_obj.school_id, role_snapshot=user_role)
            elif tgt.target_type == CalendarTargetType.GRADE:
                # Students da série
                for s in Student.query.filter_by(grade_id=tgt.target_id).all():
                    add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                # Teachers que lecionam na série
                class_ids = [c.id for c in Class.query.filter_by(grade_id=tgt.target_id).all()]
                if class_ids:
                    # Buscar escolas das turmas para incluir diretores/coordenadores
                    schools_in_grade = set()
                    for class_id in class_ids:
                        class_obj = Class.query.get(class_id)
                        if class_obj and class_obj.school_id:
                            schools_in_grade.add(class_obj.school_id)
                    
                    teacher_ids = [cs.teacher_id for cs in ClassSubject.query.filter(ClassSubject.class_id.in_(class_ids)).all()]
                    if teacher_ids:
                        for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                            # Buscar escola do professor
                            school_teachers = SchoolTeacher.query.filter_by(teacher_id=t.id).all()
                            for st in school_teachers:
                                if st.school_id in schools_in_grade:
                                    add_user(t.user_id, school_id=st.school_id, role_snapshot='professor')
                                    break
                    
                    # Diretores e Coordenadores das escolas da série
                    if schools_in_grade:
                        managers = Manager.query.filter(Manager.school_id.in_(list(schools_in_grade))).all()
                        for manager in managers:
                            if manager.user_id:
                                user = User.query.get(manager.user_id)
                                if user:
                                    user_role = user.role.value if hasattr(user.role, 'value') else user.role
                                    if user_role in ['diretor', 'coordenador']:
                                        add_user(manager.user_id, school_id=manager.school_id, role_snapshot=user_role)
            elif tgt.target_type == CalendarTargetType.SCHOOL:
                # Students da escola
                for s in Student.query.filter_by(school_id=tgt.target_id).all():
                    add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                # Teachers da escola
                teacher_ids = [st.teacher_id for st in SchoolTeacher.query.filter_by(school_id=tgt.target_id).all()]
                if teacher_ids:
                    for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                        add_user(t.user_id, school_id=tgt.target_id, role_snapshot='professor')
                # Diretores e Coordenadores da escola
                managers = Manager.query.filter_by(school_id=tgt.target_id).all()
                for manager in managers:
                    if manager.user_id:
                        user = User.query.get(manager.user_id)
                        if user:
                            user_role = user.role.value if hasattr(user.role, 'value') else user.role
                            if user_role in ['diretor', 'coordenador']:
                                add_user(manager.user_id, school_id=tgt.target_id, role_snapshot=user_role)
            elif tgt.target_type == CalendarTargetType.MUNICIPALITY:
                # Todas as escolas do município
                school_ids = [s.id for s in School.query.filter_by(city_id=tgt.target_id).all()]
                if school_ids:
                    # Students de todas as escolas
                    for s in Student.query.filter(Student.school_id.in_(school_ids)).all():
                        add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                    # Teachers de todas as escolas
                    teacher_ids = [st.teacher_id for st in SchoolTeacher.query.filter(SchoolTeacher.school_id.in_(school_ids)).all()]
                    if teacher_ids:
                        for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                            add_user(t.user_id, role_snapshot='professor')
                    # Diretores e Coordenadores de todas as escolas do município
                    managers = Manager.query.filter(Manager.school_id.in_(school_ids)).all()
                    for manager in managers:
                        if manager.user_id:
                            user = User.query.get(manager.user_id)
                            if user:
                                user_role = user.role.value if hasattr(user.role, 'value') else user.role
                                if user_role in ['diretor', 'coordenador']:
                                    add_user(manager.user_id, school_id=manager.school_id, role_snapshot=user_role)
                    # Tecadm do município
                    tecadm_managers = Manager.query.filter_by(city_id=tgt.target_id).all()
                    for manager in tecadm_managers:
                        if manager.user_id:
                            user = User.query.get(manager.user_id)
                            if user:
                                user_role = user.role.value if hasattr(user.role, 'value') else user.role
                                if user_role == 'tecadm':
                                    add_user(manager.user_id, role_snapshot='tecadm')

        # If scope is SCHOOL_ALL and event.school_id set
        if event.visibility_scope == CalendarVisibilityScope.SCHOOL_ALL and event.school_id:
            # Students
            for s in Student.query.filter_by(school_id=event.school_id).all():
                add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
            # Teachers
            teacher_ids = [st.teacher_id for st in SchoolTeacher.query.filter_by(school_id=event.school_id).all()]
            if teacher_ids:
                for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                    add_user(t.user_id, school_id=event.school_id, role_snapshot='professor')
            # Diretores e Coordenadores da escola
            managers = Manager.query.filter_by(school_id=event.school_id).all()
            for manager in managers:
                if manager.user_id:
                    user = User.query.get(manager.user_id)
                    if user:
                        user_role = user.role.value if hasattr(user.role, 'value') else user.role
                        if user_role in ['diretor', 'coordenador']:
                            add_user(manager.user_id, school_id=event.school_id, role_snapshot=user_role)

        # Persist distinct recipients
        for uid in user_ids:
            school_id, class_id, role_snapshot = context_map.get(uid, (None, None, None))
            db.session.add(CalendarEventUser(
                event_id=event.id,
                user_id=uid,
                school_id=school_id,
                class_id=class_id,
                role_snapshot=role_snapshot
            ))
        
        db.session.commit()

    @staticmethod
    def list_my_events(user_id: str, start: datetime, end: datetime) -> List[CalendarEvent]:
        q = (
            db.session.query(CalendarEvent)
            .join(CalendarEventUser, CalendarEventUser.event_id == CalendarEvent.id)
            .filter(CalendarEventUser.user_id == user_id)
            .filter(
                or_(
                    and_(CalendarEvent.start_at >= start, CalendarEvent.start_at <= end),
                    and_(CalendarEvent.end_at != None, CalendarEvent.end_at >= start, CalendarEvent.end_at <= end)
                )
            )
        )
        return q.all()

    @staticmethod
    def mark_read(event_id: str, user_id: str) -> None:
        rec = CalendarEventUser.query.filter_by(event_id=event_id, user_id=user_id).first()
        if rec and not rec.read_at:
            rec.read_at = datetime.utcnow()
            db.session.commit()

    @staticmethod
    def mark_dismiss(event_id: str, user_id: str) -> None:
        rec = CalendarEventUser.query.filter_by(event_id=event_id, user_id=user_id).first()
        if rec and not rec.dismissed_at:
            rec.dismissed_at = datetime.utcnow()
            db.session.commit()


