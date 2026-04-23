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
    def _extract_user_role(user: User) -> str:
        if not user:
            return ''
        return user.role.value if hasattr(user.role, 'value') else str(user.role or '')

    @staticmethod
    def _get_school_ids_for_target(target_type: str, target_id: str) -> Set[str]:
        school_ids: Set[str] = set()
        if target_type == 'SCHOOL':
            school_ids.add(str(target_id))
        elif target_type == 'CLASS':
            class_obj = Class.query.get(target_id)
            if class_obj and class_obj.school_id:
                school_ids.add(str(class_obj.school_id))
        elif target_type == 'GRADE':
            for cls in Class.query.filter_by(grade_id=target_id).all():
                if cls.school_id:
                    school_ids.add(str(cls.school_id))
        elif target_type == 'USER':
            student = Student.query.filter_by(user_id=target_id).first()
            if student and student.school_id:
                school_ids.add(str(student.school_id))
            teacher = Teacher.query.filter_by(user_id=target_id).first()
            if teacher:
                for st in SchoolTeacher.query.filter_by(teacher_id=teacher.id).all():
                    if st.school_id:
                        school_ids.add(str(st.school_id))
            manager = Manager.query.filter_by(user_id=target_id).first()
            if manager and manager.school_id:
                school_ids.add(str(manager.school_id))
        return school_ids

    @staticmethod
    def _normalize_role_group_filters(filters: Dict[str, Any]) -> Dict[str, List[str]]:
        f = filters or {}
        school_ids = [str(x) for x in (f.get('school_ids') or []) if x]
        grade_ids = [str(x) for x in (f.get('grade_ids') or []) if x]
        class_ids = [str(x) for x in (f.get('class_ids') or []) if x]
        return {
            'school_ids': school_ids,
            'grade_ids': grade_ids,
            'class_ids': class_ids,
        }

    @staticmethod
    def _matches_role_group_filters_for_user(role_group: str, user_id: str, filters: Dict[str, List[str]]) -> Tuple[bool, Tuple[str, str, str]]:
        school_ids = set(filters.get('school_ids') or [])
        grade_ids = set(filters.get('grade_ids') or [])
        class_ids = set(filters.get('class_ids') or [])

        if role_group == 'aluno':
            student = Student.query.filter_by(user_id=user_id).first()
            if not student:
                return False, (None, None, None)
            if school_ids and str(student.school_id) not in school_ids:
                return False, (None, None, None)
            if grade_ids and str(student.grade_id) not in grade_ids:
                return False, (None, None, None)
            if class_ids and str(student.class_id) not in class_ids:
                return False, (None, None, None)
            return True, (student.school_id, student.class_id, 'aluno')

        if role_group == 'professor':
            teacher = Teacher.query.filter_by(user_id=user_id).first()
            if not teacher:
                return False, (None, None, None)

            teacher_school_ids = {str(st.school_id) for st in SchoolTeacher.query.filter_by(teacher_id=teacher.id).all() if st.school_id}
            tc_class_ids = {str(tc.class_id) for tc in TeacherClass.query.filter_by(teacher_id=teacher.id).all() if tc.class_id}
            cs_class_ids = {str(cs.class_id) for cs in ClassSubject.query.filter_by(teacher_id=teacher.id).all() if cs.class_id}
            teacher_class_ids = tc_class_ids.union(cs_class_ids)
            teacher_grade_ids: Set[str] = set()
            if teacher_class_ids:
                for c in Class.query.filter(Class.id.in_(list(teacher_class_ids))).all():
                    if c.grade_id:
                        teacher_grade_ids.add(str(c.grade_id))
                    if c.school_id:
                        teacher_school_ids.add(str(c.school_id))

            if school_ids and teacher_school_ids.isdisjoint(school_ids):
                return False, (None, None, None)
            if grade_ids and teacher_grade_ids.isdisjoint(grade_ids):
                return False, (None, None, None)
            if class_ids and teacher_class_ids.isdisjoint(class_ids):
                return False, (None, None, None)

            ctx_school = next(iter(teacher_school_ids), None)
            ctx_class = next(iter(teacher_class_ids), None)
            return True, (ctx_school, ctx_class, 'professor')

        if role_group in ['diretor', 'coordenador', 'tecadm']:
            manager = Manager.query.filter_by(user_id=user_id).first()
            if not manager:
                return False, (None, None, None)

            manager_school_id = str(manager.school_id) if manager.school_id else None
            if school_ids and (not manager_school_id or manager_school_id not in school_ids):
                return False, (None, None, None)

            if grade_ids:
                if not manager_school_id:
                    return False, (None, None, None)
                has_grade = Class.query.filter(
                    Class.school_id == manager_school_id,
                    Class.grade_id.in_(list(grade_ids))
                ).first() is not None
                if not has_grade:
                    return False, (None, None, None)

            if class_ids:
                q = Class.query.filter(Class.id.in_(list(class_ids)))
                if manager_school_id:
                    q = q.filter(Class.school_id == manager_school_id)
                has_class = q.first() is not None
                if not has_class:
                    return False, (None, None, None)

            return True, (manager.school_id, None, role_group)

        if role_group == 'admin':
            # Admin não é tenant-table; por padrão, só filtra por city quando houver.
            user = User.query.get(user_id)
            if not user:
                return False, (None, None, None)
            return True, (None, None, 'admin')

        return False, (None, None, None)

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
        from app.permissions.utils import get_manager_school, get_teacher_schools
        
        creator_role = creator.get('role', '').lower()

        if not targets:
            return False, 'Informe ao menos um target'

        # Admin pode direcionar eventos para qualquer target no contexto do tenant.
        if creator_role == 'admin':
            return True, ''

        for target in targets:
            target_type = target.get('target_type', '').upper()
            target_id = target.get('target_id')
            target_filters = CalendarEventService._normalize_role_group_filters(target.get('filters') or {})
            
            if target_type == 'ALL':
                if creator_role not in ['admin', 'tecadm']:
                    return False, 'Apenas admin e tecadm podem enviar para ALL'
                continue
            if target_type == 'ROLE_GROUP':
                allowed_roles = {'admin', 'tecadm', 'diretor', 'coordenador', 'professor', 'aluno'}
                role_group = str(target_id or '').lower()
                if role_group not in allowed_roles:
                    return False, 'ROLE_GROUP inválido'
                if creator_role == 'aluno':
                    return False, 'Aluno não pode enviar para grupos de role'
                if creator_role in ['diretor', 'coordenador'] and role_group not in ['aluno', 'professor', 'diretor', 'coordenador']:
                    return False, 'Diretor/coordenador não podem usar esse ROLE_GROUP'
                if creator_role == 'professor' and role_group not in ['aluno', 'professor']:
                    return False, 'Professor não pode usar esse ROLE_GROUP'
                if creator_role == 'tecadm' and role_group == 'admin':
                    return False, 'Tecadm não pode usar ROLE_GROUP admin'
                # role_group com filtros é permitido; filtros vazios também
                continue
            if not target_id:
                return False, 'target_id é obrigatório'
            
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
                elif target_type == 'USER':
                    target_user = User.query.get(target_id)
                    if not target_user:
                        return False, 'Usuário target não encontrado'
                    target_city_id = getattr(target_user, 'city_id', None)
                    if target_city_id and str(target_city_id) != str(creator_city_id):
                        return False, 'Acesso negado ao usuário target'
                elif target_type == 'ALL':
                    continue
                else:
                    return False, 'Tipo de target não permitido para tecadm'
            
            elif creator_role in ['diretor', 'coordenador']:
                manager_school_id = get_manager_school(creator['id'])
                if not manager_school_id:
                    return False, 'Usuário não vinculado a uma escola'
                
                if target_type == 'SCHOOL':
                    if str(target_id) != str(manager_school_id):
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
                elif target_type == 'USER':
                    school_ids = CalendarEventService._get_school_ids_for_target('USER', target_id)
                    if school_ids and str(manager_school_id) not in {str(sid) for sid in school_ids}:
                        return False, 'Acesso negado ao usuário target'
                else:
                    return False, 'Tipo de target não permitido para diretor/coordenador'
            
            elif creator_role == 'professor':
                teacher_school_ids = {str(s) for s in get_teacher_schools(creator['id'])}
                if not teacher_school_ids:
                    return False, 'Professor não vinculado a nenhuma escola'

                if target_type == 'SCHOOL':
                    if str(target_id) not in teacher_school_ids:
                        return False, 'Acesso negado à escola'
                elif target_type in ['GRADE', 'CLASS', 'USER']:
                    school_ids = CalendarEventService._get_school_ids_for_target(target_type, target_id)
                    if not school_ids:
                        return False, 'Target sem vínculo escolar válido'
                    if not school_ids.issubset(teacher_school_ids):
                        return False, 'Acesso negado ao target'
                else:
                    return False, 'Professor não pode usar esse tipo de target'

            elif creator_role == 'aluno':
                if target_type != 'USER' or str(target_id) != str(creator['id']):
                    return False, 'Aluno só pode criar evento para si mesmo'
            
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
            target_type = str(t['target_type']).upper()
            target_id = t.get('target_id')
            if target_type == 'ALL' and not target_id:
                target_id = 'ALL'
            db.session.add(CalendarEventTarget(
                event_id=event.id,
                target_type=CalendarTargetType(target_type),
                target_id=str(target_id) if target_id is not None else None,
                target_filters=CalendarEventService._normalize_role_group_filters(t.get('filters') or {})
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
                target_type = str(t['target_type']).upper()
                target_id = t.get('target_id')
                if target_type == 'ALL' and not target_id:
                    target_id = 'ALL'
                db.session.add(CalendarEventTarget(
                    event_id=event.id,
                    target_type=CalendarTargetType(target_type),
                    target_id=str(target_id) if target_id is not None else None,
                    target_filters=CalendarEventService._normalize_role_group_filters(t.get('filters') or {})
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
            if tgt.target_type == CalendarTargetType.ALL:
                seen: Set[str] = set()
                # Alunos
                for s in Student.query.all():
                    if s.user_id:
                        seen.add(s.user_id)
                        add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                # Professores
                for t in Teacher.query.all():
                    if t.user_id and t.user_id not in seen:
                        seen.add(t.user_id)
                        school_links = SchoolTeacher.query.filter_by(teacher_id=t.id).all()
                        school_id = school_links[0].school_id if school_links else None
                        add_user(t.user_id, school_id=school_id, role_snapshot='professor')
                # Gestores (diretor/coordenador/tecadm)
                for m in Manager.query.all():
                    if not m.user_id or m.user_id in seen:
                        continue
                    user = User.query.get(m.user_id)
                    if not user:
                        continue
                    user_role = CalendarEventService._extract_user_role(user)
                    if user_role in ['diretor', 'coordenador', 'tecadm', 'admin']:
                        seen.add(m.user_id)
                        add_user(m.user_id, school_id=m.school_id, role_snapshot=user_role)
            elif tgt.target_type == CalendarTargetType.USER:
                add_user(tgt.target_id)
            elif tgt.target_type == CalendarTargetType.ROLE_GROUP:
                role_group = str(tgt.target_id or '').lower()
                filters = CalendarEventService._normalize_role_group_filters(tgt.target_filters or {})
                if role_group == 'aluno':
                    for s in Student.query.all():
                        if not s.user_id:
                            continue
                        ok, ctx = CalendarEventService._matches_role_group_filters_for_user('aluno', s.user_id, filters)
                        if ok:
                            school_id, class_id, role_snapshot = ctx
                            add_user(s.user_id, school_id=school_id, class_id=class_id, role_snapshot=role_snapshot)
                elif role_group == 'professor':
                    for t in Teacher.query.all():
                        if not t.user_id:
                            continue
                        ok, ctx = CalendarEventService._matches_role_group_filters_for_user('professor', t.user_id, filters)
                        if ok:
                            school_id, class_id, role_snapshot = ctx
                            add_user(t.user_id, school_id=school_id, class_id=class_id, role_snapshot=role_snapshot)
                elif role_group in ['diretor', 'coordenador', 'tecadm']:
                    managers = Manager.query.all()
                    for m in managers:
                        if not m.user_id:
                            continue
                        user = User.query.get(m.user_id)
                        if not user:
                            continue
                        user_role = CalendarEventService._extract_user_role(user)
                        if user_role != role_group:
                            continue
                        ok, ctx = CalendarEventService._matches_role_group_filters_for_user(role_group, m.user_id, filters)
                        if ok:
                            school_id, class_id, role_snapshot = ctx
                            add_user(m.user_id, school_id=school_id, class_id=class_id, role_snapshot=role_snapshot)
                elif role_group == 'admin':
                    for u in User.query.all():
                        user_role = CalendarEventService._extract_user_role(u)
                        if user_role != 'admin':
                            continue
                        ok, ctx = CalendarEventService._matches_role_group_filters_for_user('admin', u.id, filters)
                        if ok:
                            school_id, class_id, role_snapshot = ctx
                            add_user(u.id, school_id=school_id, class_id=class_id, role_snapshot=role_snapshot)
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
        date_clause = or_(
            and_(CalendarEvent.start_at >= start, CalendarEvent.start_at <= end),
            and_(CalendarEvent.end_at != None, CalendarEvent.end_at >= start, CalendarEvent.end_at <= end)
        )
        q_recipient = (
            db.session.query(CalendarEvent)
            .join(CalendarEventUser, CalendarEventUser.event_id == CalendarEvent.id)
            .filter(CalendarEventUser.user_id == user_id)
            .filter(date_clause)
        )
        q_creator = (
            db.session.query(CalendarEvent)
            .filter(CalendarEvent.created_by_user_id == user_id)
            .filter(date_clause)
        )
        by_id = {e.id: e for e in q_recipient.all()}
        for ev in q_creator.all():
            by_id[ev.id] = ev
        return sorted(by_id.values(), key=lambda e: e.start_at, reverse=True)

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


