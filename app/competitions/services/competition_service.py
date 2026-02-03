# -*- coding: utf-8 -*-
"""Serviço de Competições (Etapa 2)."""
from sqlalchemy import func
from app import db
from app.competitions.models import Competition
from app.competitions.constants import is_valid_level, STAGE_NAMES_BY_LEVEL
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.educationStage import EducationStage
from datetime import datetime
import random

# Formato esperado de reward_config: {"participation_coins": int, "ranking_rewards": [{"position": int, "coins": int}, ...]}
REWARD_CONFIG_PARTICIPATION_KEY = "participation_coins"
REWARD_CONFIG_RANKING_KEY = "ranking_rewards"


class ValidationError(Exception):
    """Erro de validação."""
    pass


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
        Sorteia questões aleatórias baseado em question_rules e no nível da competição.
        Filtra questões por: disciplina (subject_id), etapa de ensino (nível 1 ou 2),
        e opcionalmente grade_ids, difficulty_level.
        """
        rules = competition.question_rules or {}
        num_questions = rules.get('num_questions', 10)

        query = Question.query.filter_by(subject_id=competition.subject_id)

        # Filtrar por nível da competição: questões da etapa de ensino correspondente
        stage_names = STAGE_NAMES_BY_LEVEL.get(competition.level)
        if stage_names:
            stage_ids = (
                db.session.query(EducationStage.id)
                .filter(EducationStage.name.in_(stage_names))
                .all()
            )
            stage_ids = [s[0] for s in stage_ids]
            if stage_ids:
                query = query.filter(Question.education_stage_id.in_(stage_ids))

        if rules.get('grade_ids'):
            query = query.filter(Question.grade_level.in_(rules['grade_ids']))
        if rules.get('difficulty_level'):
            query = query.filter_by(difficulty_level=rules['difficulty_level'])

        available_questions = query.all()
        if len(available_questions) < num_questions:
            raise ValidationError(
                f"Questões insuficientes para o nível e disciplina. Disponíveis: {len(available_questions)}, Necessárias: {num_questions}"
            )

        selected_questions = random.sample(available_questions, num_questions)
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
