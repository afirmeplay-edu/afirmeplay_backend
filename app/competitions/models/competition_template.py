# -*- coding: utf-8 -*-
"""Modelo de template de competições recorrentes (Etapa 6)."""

import uuid
from datetime import datetime

from app import db
from app.competitions.exceptions import ValidationError


class CompetitionTemplate(db.Model):
    """
    Template para criação automática de competições.

    Os campos aqui seguem o plano da Etapa 6 (PLANO_IMPLEMENTACAO_COMPETICOES.md)
    e são usados pelo job diário que gera competições recorrentes.
    """

    __tablename__ = "competition_templates"

    # Identificador do template
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Dados básicos
    name = db.Column(db.String, nullable=False)
    subject_id = db.Column(db.String, db.ForeignKey("subject.id"), nullable=True)
    level = db.Column(db.Integer, nullable=True)

    # Escopo da competição gerada (ex.: 'global', 'individual', 'escola', etc.)
    scope = db.Column(db.String, nullable=False, server_default="individual")
    scope_filter = db.Column(db.JSON, nullable=True)

    # periodicidade: 'weekly', 'biweekly', 'monthly'
    recurrence = db.Column(db.String, nullable=False)

    # Como as questões serão escolhidas
    question_mode = db.Column(db.String, nullable=False, server_default="auto_random")
    question_rules = db.Column(db.JSON, nullable=True)

    # Configuração de recompensas e ranking
    reward_config = db.Column(db.JSON, nullable=True)
    ranking_criteria = db.Column(db.String, nullable=False, server_default="nota")
    ranking_tiebreaker = db.Column(
        db.String, nullable=False, server_default="tempo_entrega"
    )
    ranking_visibility = db.Column(db.String, nullable=False, server_default="final")

    # Limite de participantes para competições geradas (None = ilimitado)
    max_participants = db.Column(db.Integer, nullable=True)

    # Controle de atividade: se False, não cria novas competições a partir do template
    active = db.Column(db.Boolean, nullable=False, server_default=db.text("TRUE"))

    # Auditoria
    created_by = db.Column(db.String, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(
        db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"), nullable=True
    )
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
        nullable=True,
    )

    # Relacionamentos
    subject = db.relationship("Subject", backref="competition_templates")
    creator = db.relationship(
        "User", foreign_keys=[created_by], backref="competition_templates"
    )

    # A relação com Competition é definida em Competition.template (backref='competitions')

    # -------------------------
    # Métodos de geração
    # -------------------------

    def generate_competition_for_period(
        self,
        start_date: datetime,
        level_override: int | None = None,
    ):
        """
        Gera uma Competition baseada neste template para um período específico.

        - Calcula datas de inscrição/aplicação/expiração conforme recorrência.
        - Seleciona questões aleatórias (até 20) respeitando disciplina/nível.
        - Define reward_config (template ou padrão da recorrência).
        - Atribui numeração e nome da edição (série automática).

        Retorna:
            Competition (não commitada) pronta para ser adicionada à sessão.

        Levanta:
            ValidationError se não houver questões disponíveis para o template.
        """
        # Imports tardios para evitar ciclos entre models ⇄ services
        from app.competitions.models import Competition
        from app.competitions.services import (
            CompetitionService,
            compute_next_edition,
            compute_period_for_recurrence,
            get_default_reward_config_for_recurrence,
            select_questions_for_template,
            validate_reward_config,
        )

        if not self.subject_id:
            raise ValidationError("Template de competição sem subject_id definido")

        # Determinar nível efetivo (pode ser sobrescrito no job para gerar 2 níveis)
        level = level_override if level_override is not None else self.level

        # 1) Datas por recorrência
        period = compute_period_for_recurrence(self.recurrence, start_date)

        # 2) Seleção de questões (até 20, usando máximo disponível)
        questions = select_questions_for_template(
            subject_id=self.subject_id,
            level=level,
            max_questions=20,
        )
        if not questions:
            raise ValidationError(
                "Nenhuma questão disponível para gerar competição automática "
                f"(subject_id={self.subject_id}, level={level})"
            )

        # 3) reward_config: usa a do template se existir, senão padrão da recorrência
        reward_config = self.reward_config or get_default_reward_config_for_recurrence(
            self.recurrence
        )
        # Garante formato válido para os serviços atuais
        validate_reward_config(reward_config)

        # 4) Série / edição e nome
        edition_number, edition_series, base_name = compute_next_edition(
            subject_id=self.subject_id,
            recurrence=self.recurrence,
        )
        # Diferenciar por nível no nome para facilitar entendimento
        suffix = f" - Nível {level}" if level is not None else ""
        competition_name = (base_name or self.name or "Competição Automática") + suffix

        # 5) Criar Competition (sem commit)
        competition = Competition(
            name=competition_name,
            description=self.name,
            subject_id=self.subject_id,
            level=level,
            scope=self.scope or "global",
            scope_filter=self.scope_filter,
            enrollment_start=period["enrollment_start"],
            enrollment_end=period["enrollment_end"],
            application=period["application"],
            expiration=period["expiration"],
            timezone="America/Sao_Paulo",
            question_mode=self.question_mode or "auto_random",
            question_rules=self.question_rules,
            reward_config=reward_config,
            ranking_criteria=self.ranking_criteria or "nota",
            ranking_tiebreaker=self.ranking_tiebreaker or "tempo_entrega",
            ranking_visibility=self.ranking_visibility or "final",
            max_participants=self.max_participants,
            recurrence=self.recurrence,
            template_id=self.id,
            created_by=self.created_by,
            status="rascunho",
            edition_number=edition_number,
            edition_series=edition_series,
        )

        db.session.add(competition)
        db.session.flush()

        # 6) Criar Test com as questões pré-selecionadas
        CompetitionService._create_test_with_random_questions(
            competition, selected_questions=questions
        )

        return competition


