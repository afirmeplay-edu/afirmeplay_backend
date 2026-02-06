# -*- coding: utf-8 -*-
"""Modelo de Competição (Etapa 2)."""
from app import db
import uuid
from datetime import datetime, timezone
from app.utils.timezone_utils import get_local_time


def _normalize_datetime_for_comparison(dt):
    """
    Normaliza datetime para comparação: se for naive, mantém naive;
    se for timezone-aware, converte para UTC e depois remove timezone.
    Garante que todas as comparações sejam feitas com datetimes naive.
    """
    if dt is None:
        return None
    if isinstance(dt, datetime):
        # Se for timezone-aware, converter para UTC primeiro, depois remover timezone
        if dt.tzinfo is not None:
            # Converter para UTC e depois remover timezone
            dt_utc = dt.astimezone(timezone.utc)
            return dt_utc.replace(tzinfo=None)
        # Se já é naive, retornar como está (assumindo que está em UTC ou timezone local)
        return dt
    return dt


class Competition(db.Model):
    __tablename__ = 'competitions'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=True)
    test_id = db.Column(db.String, db.ForeignKey('test.id'), nullable=True)
    subject_id = db.Column(db.String, db.ForeignKey('subject.id'), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    scope = db.Column(db.String, default='individual')
    scope_filter = db.Column(db.JSON, nullable=True)
    enrollment_start = db.Column(db.TIMESTAMP, nullable=False)
    enrollment_end = db.Column(db.TIMESTAMP, nullable=False)
    application = db.Column(db.TIMESTAMP, nullable=False)
    expiration = db.Column(db.TIMESTAMP, nullable=False)
    timezone = db.Column(db.String, default='America/Sao_Paulo')
    question_mode = db.Column(db.String, default='auto_random')
    question_rules = db.Column(db.JSON, nullable=True)
    reward_config = db.Column(db.JSON, nullable=False)
    ranking_criteria = db.Column(db.String, default='nota')
    ranking_tiebreaker = db.Column(db.String, default='tempo_entrega')
    ranking_visibility = db.Column(db.String, default='final')
    max_participants = db.Column(db.Integer, nullable=True)
    recurrence = db.Column(db.String, default='manual')
    template_id = db.Column(db.String, db.ForeignKey('competition_templates.id'), nullable=True)
    status = db.Column(db.String, default='rascunho')
    created_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text('CURRENT_TIMESTAMP'),
        onupdate=db.text('CURRENT_TIMESTAMP'),
    )

    # Relacionamentos
    test = db.relationship('Test', backref='competitions')
    subject = db.relationship('Subject', backref='competitions')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_competitions')
    template = db.relationship('CompetitionTemplate', backref='competitions')

    @property
    def is_enrollment_open(self) -> bool:
        """Verifica se está no período de inscrição."""
        # Alinha com lógica de avaliações: usar horário local do servidor
        # (get_local_time) em vez de UTC puro para comparações.
        now = get_local_time()
        now_naive = _normalize_datetime_for_comparison(now)
        start = _normalize_datetime_for_comparison(self.enrollment_start)
        end = _normalize_datetime_for_comparison(self.enrollment_end)
        if start is None or end is None:
            return False
        return start <= now_naive <= end

    @property
    def is_application_open(self) -> bool:
        """Verifica se está no período de aplicação."""
        now = get_local_time()
        now_naive = _normalize_datetime_for_comparison(now)
        app_start = _normalize_datetime_for_comparison(self.application)
        exp = _normalize_datetime_for_comparison(self.expiration)
        if app_start is None or exp is None:
            return False
        return app_start <= now_naive <= exp

    @property
    def is_finished(self) -> bool:
        """Verifica se já expirou."""
        now = get_local_time()
        now_naive = _normalize_datetime_for_comparison(now)
        exp = _normalize_datetime_for_comparison(self.expiration)
        if exp is None:
            return False
        return now_naive > exp

    @property
    def enrolled_count(self) -> int:
        """Conta quantos alunos inscritos (via competition_enrollments; fallback em StudentTestOlimpics)."""
        try:
            return self.enrollments.filter_by(status='inscrito').count()
        except Exception:
            pass
        if not self.test_id:
            return 0
        try:
            from app.models.studentTestOlimpics import StudentTestOlimpics
            return StudentTestOlimpics.query.filter_by(test_id=self.test_id).count()
        except Exception:
            return 0

    @property
    def available_slots(self):
        """Vagas disponíveis (None se ilimitado)."""
        if self.max_participants is None:
            return None
        return max(0, self.max_participants - self.enrolled_count)
