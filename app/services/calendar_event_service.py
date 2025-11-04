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
)


class CalendarEventService:
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

        targets = CalendarEventTarget.query.filter_by(event_id=event_id).all()

        for tgt in targets:
            if tgt.target_type == CalendarTargetType.USER:
                add_user(tgt.target_id)
            elif tgt.target_type == CalendarTargetType.CLASS:
                # Students
                for s in Student.query.filter_by(class_id=tgt.target_id).all():
                    add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                # Teachers (via ClassSubject)
                teacher_ids = [cs.teacher_id for cs in ClassSubject.query.filter_by(class_id=tgt.target_id).all()]
                if teacher_ids:
                    for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                        add_user(t.user_id, role_snapshot='professor')
            elif tgt.target_type == CalendarTargetType.GRADE:
                # Students of grade
                for s in Student.query.filter_by(grade_id=tgt.target_id).all():
                    add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                # Teachers teaching classes in grade
                class_ids = [c.id for c in Class.query.filter_by(grade_id=tgt.target_id).all()]
                if class_ids:
                    teacher_ids = [cs.teacher_id for cs in ClassSubject.query.filter(ClassSubject.class_id.in_(class_ids)).all()]
                    if teacher_ids:
                        for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                            add_user(t.user_id, role_snapshot='professor')
            elif tgt.target_type == CalendarTargetType.SCHOOL:
                # Students
                for s in Student.query.filter_by(school_id=tgt.target_id).all():
                    add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                # Teachers (via SchoolTeacher)
                teacher_ids = [st.teacher_id for st in SchoolTeacher.query.filter_by(school_id=tgt.target_id).all()]
                if teacher_ids:
                    for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                        add_user(t.user_id, role_snapshot='professor')
            elif tgt.target_type == CalendarTargetType.MUNICIPALITY:
                # All schools in city
                school_ids = [s.id for s in School.query.filter_by(city_id=tgt.target_id).all()]
                if school_ids:
                    # Students
                    for s in Student.query.filter(Student.school_id.in_(school_ids)).all():
                        add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
                    # Teachers
                    teacher_ids = [st.teacher_id for st in SchoolTeacher.query.filter(SchoolTeacher.school_id.in_(school_ids)).all()]
                    if teacher_ids:
                        for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                            add_user(t.user_id, role_snapshot='professor')

        # If scope is SCHOOL_ALL and event.school_id set
        if event.visibility_scope == CalendarVisibilityScope.SCHOOL_ALL and event.school_id:
            # Students
            for s in Student.query.filter_by(school_id=event.school_id).all():
                add_user(s.user_id, school_id=s.school_id, class_id=s.class_id, role_snapshot='aluno')
            # Teachers
            teacher_ids = [st.teacher_id for st in SchoolTeacher.query.filter_by(school_id=event.school_id).all()]
            if teacher_ids:
                for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all():
                    add_user(t.user_id, role_snapshot='professor')

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


