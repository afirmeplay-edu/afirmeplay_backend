# -*- coding: utf-8 -*-
"""Serviço de Competições (Etapa 2 e 3)."""
from datetime import datetime

from sqlalchemy import func

from app import db
from app.competitions.models import Competition, CompetitionEnrollment
from app.competitions.constants import is_valid_level, student_grade_matches_level
from app.competitions.exceptions import ValidationError
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.student import Student
from app.models.studentTestOlimpics import StudentTestOlimpics

from .question_selection_service import QuestionSelectionService

# Formato esperado de reward_config: {"participation_coins": int, "ranking_rewards": [{"position": int, "coins": int}, ...]}
REWARD_CONFIG_PARTICIPATION_KEY = "participation_coins"
REWARD_CONFIG_RANKING_KEY = "ranking_rewards"


class CompetitionService:
    @staticmethod
    def create_competition(data: dict, created_by_user_id: str) -> Competition:
        """
        Cria competição.
        Se question_mode = 'auto_random': sorteia questões e cria Test.
        Se question_mode = 'manual': deixa test_id = None (adicionar depois).
        """
        enrollment_end = data.get('enrollment_end')
        application = data.get('application')
        if enrollment_end and application:
            enrollment_end = _parse_dt(enrollment_end)
            application = _parse_dt(application)
            if enrollment_end > application:
                raise ValidationError("Data de aplicação deve ser após fim da inscrição")

        level = data.get('level')
        if level is not None and not is_valid_level(level):
            raise ValidationError("Nível deve ser 1 (Educação Infantil, Anos Iniciais, Educação Especial, EJA) ou 2 (Anos Finais e Ensino Médio)")

        reward_config = data.get('reward_config')
        _validate_reward_config(reward_config)

        competition = Competition(
            name=data['name'],
            description=data.get('description'),
            subject_id=data['subject_id'],
            level=data['level'],
            scope=data.get('scope', 'individual'),
            scope_filter=data.get('scope_filter'),
            enrollment_start=_parse_dt(data['enrollment_start']),
            enrollment_end=_parse_dt(data['enrollment_end']),
            application=_parse_dt(data['application']),
            expiration=_parse_dt(data['expiration']),
            timezone=data.get('timezone', 'America/Sao_Paulo'),
            question_mode=data.get('question_mode', 'auto_random'),
            question_rules=data.get('question_rules'),
            reward_config=data['reward_config'],
            ranking_criteria=data.get('ranking_criteria', 'nota'),
            ranking_tiebreaker=data.get('ranking_tiebreaker', 'tempo_entrega'),
            ranking_visibility=data.get('ranking_visibility', 'final'),
            max_participants=data.get('max_participants'),
            recurrence=data.get('recurrence', 'manual'),
            template_id=data.get('template_id'),
            created_by=created_by_user_id,
            status='rascunho',
        )
        db.session.add(competition)
        db.session.flush()

        if competition.question_mode == 'auto_random':
            CompetitionService._create_test_with_random_questions(competition)

        db.session.commit()
        return competition

    @staticmethod
    def _create_test_with_random_questions(competition: Competition) -> None:
        """
        Sorteia questões aleatórias baseado em question_rules,
        delegando a lógica de filtros e aleatorização para QuestionSelectionService.
        """
        rules = competition.question_rules or {}
        selected_questions = QuestionSelectionService.select_questions(
            subject_id=competition.subject_id,
            level=competition.level,
            rules=rules,
        )
        test = Test(
            title=f"Prova - {competition.name}",
            description=competition.description,
            subject=competition.subject_id,
            evaluation_mode='virtual',
            created_by=competition.created_by,
        )
        db.session.add(test)
        db.session.flush()

        for idx, question in enumerate(selected_questions, start=1):
            db.session.add(TestQuestion(test_id=test.id, question_id=question.id, order=idx))
        competition.test_id = test.id

    @staticmethod
    def add_questions_manually(competition_id: str, question_ids: list) -> None:
        """Adiciona questões manualmente (para question_mode = 'manual')."""
        competition = Competition.query.get_or_404(competition_id)
        if competition.question_mode != 'manual':
            raise ValidationError("Competição não está em modo manual")

        if competition.test_id:
            test = Test.query.get(competition.test_id)
            if not test:
                raise ValidationError("Test da competição não encontrado")
            next_order = (
                db.session.query(func.max(TestQuestion.order))
                .filter_by(test_id=test.id)
                .scalar() or 0
            ) + 1
            for idx, qid in enumerate(question_ids, start=next_order):
                db.session.add(TestQuestion(test_id=test.id, question_id=qid, order=idx))
        else:
            test = Test(
                title=f"Prova - {competition.name}",
                description=competition.description,
                subject=competition.subject_id,
                evaluation_mode='virtual',
                created_by=competition.created_by,
            )
            db.session.add(test)
            db.session.flush()
            for idx, qid in enumerate(question_ids, start=1):
                db.session.add(TestQuestion(test_id=test.id, question_id=qid, order=idx))
            competition.test_id = test.id
        db.session.commit()

    @staticmethod
    def publish_competition(competition_id: str) -> Competition:
        """Publica competição (rascunho → aberta)."""
        competition = Competition.query.get_or_404(competition_id)
        if not competition.test_id:
            raise ValidationError("Test não foi criado ainda")
        if competition.enrollment_end > competition.application:
            raise ValidationError("Datas inválidas: fim da inscrição deve ser antes da aplicação")
        if not competition.reward_config:
            raise ValidationError("Configuração de recompensas ausente")
        competition.status = 'aberta'
        db.session.commit()
        return competition

    @staticmethod
    def cancel_competition(competition_id: str, reason: str = None) -> Competition:
        """Cancela competição."""
        competition = Competition.query.get_or_404(competition_id)
        competition.status = 'cancelada'
        db.session.commit()
        return competition

    # ---------- Etapa 3: Inscrição e listagem para aluno ----------

    @staticmethod
    def is_student_enrolled(competition_id: str, student_id: str) -> bool:
        """Retorna True se o aluno está inscrito (status='inscrito') na competição."""
        return CompetitionEnrollment.query.filter_by(
            competition_id=competition_id,
            student_id=student_id,
            status='inscrito',
        ).first() is not None

    @staticmethod
    def get_available_competitions_for_student(student_id: str, subject_id: str = None):
        """
        Lista competições disponíveis para o aluno: status aberta, no período de inscrição,
        nível e escopo compatíveis, com vagas (se houver limite).
        """
        student = Student.query.get(student_id)
        if not student:
            return []

        now = datetime.utcnow()
        query = (
            Competition.query.filter(
                Competition.status == 'aberta',
                Competition.test_id.isnot(None),
                Competition.enrollment_start <= now,
                Competition.enrollment_end >= now,
            )
        )
        if subject_id:
            query = query.filter(Competition.subject_id == subject_id)
        candidates = query.all()

        result = []
        for c in candidates:
            if not _student_level_matches(student, c.level):
                continue
            if not _student_in_scope(student, c):
                continue
            if c.max_participants is not None:
                try:
                    if c.enrolled_count >= c.max_participants:
                        continue
                except Exception:
                    continue
            result.append(c)
        return result

    @staticmethod
    def enroll_student(competition_id: str, student_id: str):
        """
        Inscreve o aluno na competição: cria CompetitionEnrollment e StudentTestOlimpics.
        Levanta ValidationError se não elegível ou já inscrito.
        """
        competition = Competition.query.get(competition_id)
        if not competition:
            raise ValidationError("Competição não encontrada")

        if competition.status != 'aberta':
            raise ValidationError("Competição não está aberta para inscrição")

        now = datetime.utcnow()
        if now < competition.enrollment_start or now > competition.enrollment_end:
            raise ValidationError("Fora do período de inscrição")

        if not competition.test_id:
            raise ValidationError("Competição sem prova vinculada")

        student = Student.query.get(student_id)
        if not student:
            raise ValidationError("Aluno não encontrado")

        available = CompetitionService.get_available_competitions_for_student(student_id)
        if not any(c.id == competition_id for c in available):
            raise ValidationError("Aluno não é elegível para esta competição (nível ou escopo)")

        if competition.max_participants is not None:
            try:
                if competition.enrolled_count >= competition.max_participants:
                    raise ValidationError("Vagas esgotadas")
            except Exception:
                pass

        existing = CompetitionEnrollment.query.filter_by(
            competition_id=competition_id,
            student_id=student_id,
            status='inscrito',
        ).first()
        if existing:
            raise ValidationError("Aluno já está inscrito nesta competição")

        if StudentTestOlimpics.query.filter_by(
            student_id=student_id,
            test_id=competition.test_id,
        ).first():
            raise ValidationError("Aluno já possui inscrição para a prova desta competição")

        enrollment = CompetitionEnrollment(
            competition_id=competition_id,
            student_id=student_id,
            status='inscrito',
        )
        db.session.add(enrollment)
        db.session.flush()

        app_str = competition.application.isoformat() if competition.application else ''
        exp_str = competition.expiration.isoformat() if competition.expiration else ''
        st_o = StudentTestOlimpics(
            student_id=student_id,
            test_id=competition.test_id,
            application=app_str,
            expiration=exp_str,
            timezone=competition.timezone or 'America/Sao_Paulo',
            status='agendada',
        )
        db.session.add(st_o)
        db.session.commit()
        return enrollment

    @staticmethod
    def unenroll_student(competition_id: str, student_id: str):
        """
        Cancela inscrição do aluno: marca enrollment como cancelado e remove StudentTestOlimpics.
        Só permitido antes do período de aplicação.
        """
        competition = Competition.query.get(competition_id)
        if not competition:
            raise ValidationError("Competição não encontrada")

        now = datetime.utcnow()
        if competition.application and now >= competition.application:
            raise ValidationError("Não é possível cancelar inscrição após o início do período de aplicação")

        enrollment = CompetitionEnrollment.query.filter_by(
            competition_id=competition_id,
            student_id=student_id,
            status='inscrito',
        ).first()
        if not enrollment:
            raise ValidationError("Aluno não está inscrito nesta competição")

        enrollment.status = 'cancelado'
        st_o = StudentTestOlimpics.query.filter_by(
            student_id=student_id,
            test_id=competition.test_id,
        ).first()
        if st_o:
            db.session.delete(st_o)
        db.session.commit()

    @staticmethod
    def credit_participation_coins(competition_id: str, student_id: str, test_session_id: str = None) -> int:
        """
        Credita moedas de participação ao aluno conforme reward_config da competição.
        Deve ser chamado quando o aluno finaliza/entrega a prova da competição (uma vez por aluno/competição).
        Retorna a quantidade de moedas creditadas (0 se participation_coins não configurado).
        """
        from app.balance.services.coin_service import CoinService

        competition = Competition.query.get_or_404(competition_id)
        config = competition.reward_config or {}
        amount = config.get(REWARD_CONFIG_PARTICIPATION_KEY)
        if amount is None:
            return 0
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return 0
        if amount <= 0:
            return 0

        CoinService.credit_coins(
            student_id=student_id,
            amount=amount,
            reason='competition_participation',
            competition_id=competition_id,
            test_session_id=test_session_id,
            description=f"Participação na competição: {competition.name}",
        )
        return amount


def validate_reward_config(reward_config):
    """
    Valida reward_config: deve ser dict com participation_coins (int >= 0)
    e opcionalmente ranking_rewards (lista de {position, coins}).
    Levanta ValidationError se inválido.
    """
    _validate_reward_config(reward_config)


def _validate_reward_config(reward_config):
    """
    Valida reward_config: deve ser dict com participation_coins (int >= 0)
    e opcionalmente ranking_rewards (lista de {position, coins}).
    """
    if reward_config is None:
        raise ValidationError("reward_config é obrigatório")
    if not isinstance(reward_config, dict):
        raise ValidationError("reward_config deve ser um objeto JSON")
    part = reward_config.get(REWARD_CONFIG_PARTICIPATION_KEY)
    if part is not None:
        try:
            part = int(part)
            if part < 0:
                raise ValidationError("participation_coins deve ser >= 0")
        except (TypeError, ValueError):
            raise ValidationError("participation_coins deve ser um número inteiro")
    ranking = reward_config.get(REWARD_CONFIG_RANKING_KEY)
    if ranking is not None:
        if not isinstance(ranking, list):
            raise ValidationError("ranking_rewards deve ser uma lista")
        for i, r in enumerate(ranking):
            if not isinstance(r, dict):
                raise ValidationError(f"ranking_rewards[{i}] deve ser um objeto com position e coins")
            pos = r.get("position")
            coins = r.get("coins")
            if pos is None or coins is None:
                raise ValidationError(f"ranking_rewards[{i}] deve ter position e coins")
            try:
                if int(pos) < 1 or int(coins) < 0:
                    raise ValidationError(f"ranking_rewards[{i}]: position >= 1 e coins >= 0")
            except (TypeError, ValueError):
                raise ValidationError(f"ranking_rewards[{i}]: position e coins devem ser números")


def _parse_dt(v):
    """Converte valor para datetime."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        return datetime.fromisoformat(v.replace('Z', '+00:00'))
    return v


def _student_level_matches(student, competition_level):
    """True se a etapa de ensino do aluno corresponde ao nível da competição (1 ou 2)."""
    if student.grade_id is None or student.grade is None:
        return False
    stage = getattr(student.grade, 'education_stage', None)
    if stage is None:
        return False
    name = getattr(stage, 'name', None)
    return student_grade_matches_level(name, competition_level)


def _student_in_scope(student, competition):
    """True se o aluno está no escopo da competição (scope + scope_filter)."""
    scope = (competition.scope or 'individual').strip().lower()
    scope_filter = competition.scope_filter or {}

    if scope == 'individual':
        return True

    def _norm_ids(ids):
        if not ids:
            return set()
        return {str(x).lower() for x in ids}

    class_ids = _norm_ids(scope_filter.get('class_ids'))
    school_ids = _norm_ids(scope_filter.get('school_ids'))
    city_ids = _norm_ids(
        scope_filter.get('city_ids') or scope_filter.get('municipality_ids')
    )
    state_names = scope_filter.get('state_names') or scope_filter.get('state')
    if state_names is not None and not isinstance(state_names, (list, tuple)):
        state_names = [state_names] if state_names else []
    state_set = {str(s).strip().lower() for s in (state_names or [])}

    if scope in ('turma', 'class') and class_ids:
        if student.class_id is None:
            return False
        return str(student.class_id).lower() in class_ids

    if scope in ('escola', 'school') and school_ids:
        if student.school_id is None:
            return False
        return str(student.school_id).lower() in school_ids

    if scope in ('municipio', 'city', 'município') and city_ids:
        if student.school_id is None or student.school is None:
            return False
        city_id = getattr(student.school, 'city_id', None)
        if city_id is None:
            return False
        return str(city_id).lower() in city_ids

    if scope in ('estado', 'state') and state_set:
        if student.school_id is None or student.school is None:
            return False
        city = getattr(student.school, 'city', None)
        if city is None:
            return False
        state = getattr(city, 'state', None)
        if state is None:
            return False
        return str(state).strip().lower() in state_set

    return False
