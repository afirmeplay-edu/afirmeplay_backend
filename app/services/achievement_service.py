# -*- coding: utf-8 -*-
"""
Sistema de conquistas para alunos (sem novas tabelas).
Calcula em tempo real a partir de EvaluationResult, TestSession, CompetitionResult.
Estados: revelada, oculta, desbloqueada. Resgate de moedas uma vez por par (conquista + medalha).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func, cast, distinct
from sqlalchemy.types import Date

from app import db
from app.models.evaluationResult import EvaluationResult
from app.models.student import Student
from app.models.testSession import TestSession

# Competitions: importação condicional para não quebrar se schema multitenant não estiver ativo
try:
    from app.competitions.models import CompetitionResult
    from app.services.competition_student_ranking_service import CompetitionStudentRankingService
    _HAS_COMPETITIONS = True
except Exception:
    _HAS_COMPETITIONS = False
    CompetitionResult = None
    CompetitionStudentRankingService = None

MEDAL_ORDER = ["bronze", "prata", "ouro", "platina"]

# Definição das conquistas: id, nome, descricao, oculta, limiares (bronze, prata, ouro, platina), moedas (idem)
ACHIEVEMENTS_CONFIG = [
    {
        "id": "avaliacoes_concluidas",
        "nome": "Avaliações concluídas",
        "descricao": "Complete avaliações para subir de nível",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 5, "ouro": 10, "platina": 25},
        "moedas": {"bronze": 10, "prata": 20, "ouro": 50, "platina": 100},
        "metric": "avaliacoes_concluidas",
    },
    {
        "id": "media_geral",
        "nome": "Média geral",
        "descricao": "Mantenha uma boa média nas avaliações",
        "oculta": False,
        "limiares": {"bronze": 5.0, "prata": 6.0, "ouro": 7.5, "platina": 9.0},
        "moedas": {"bronze": 10, "prata": 20, "ouro": 50, "platina": 100},
        "metric": "media_grade",
    },
    {
        "id": "proficiencia_media",
        "nome": "Proficiência média",
        "descricao": "Aumente sua proficiência nas avaliações",
        "oculta": False,
        "limiares": {"bronze": 200, "prata": 250, "ouro": 300, "platina": 350},
        "moedas": {"bronze": 10, "prata": 20, "ouro": 50, "platina": 100},
        "metric": "media_proficiencia",
    },
    {
        "id": "podios_competicoes",
        "nome": "Pódios em competições",
        "descricao": "Fique no pódio em competições",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 3, "ouro": 5, "platina": 10},
        "moedas": {"bronze": 15, "prata": 30, "ouro": 75, "platina": 150},
        "metric": "total_podiums",
    },
    {
        "id": "competicoes_realizadas",
        "nome": "Competições realizadas",
        "descricao": "Participe de competições e entregue resultados",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 3, "ouro": 5, "platina": 15},
        "moedas": {"bronze": 10, "prata": 20, "ouro": 50, "platina": 100},
        "metric": "competicoes_count",
    },
    # Conquistas extras (mais opções de bronze)
    {
        "id": "acertos_totais",
        "nome": "Acertos totais",
        "descricao": "Acumule acertos em todas as avaliações",
        "oculta": False,
        "limiares": {"bronze": 5, "prata": 25, "ouro": 50, "platina": 200},
        "moedas": {"bronze": 8, "prata": 18, "ouro": 45, "platina": 90},
        "metric": "total_acertos",
    },
    {
        "id": "questoes_respondidas",
        "nome": "Questões respondidas",
        "descricao": "Responda a muitas questões nas avaliações",
        "oculta": False,
        "limiares": {"bronze": 10, "prata": 50, "ouro": 100, "platina": 500},
        "moedas": {"bronze": 8, "prata": 18, "ouro": 45, "platina": 90},
        "metric": "total_questoes",
    },
    {
        "id": "media_acertos_percent",
        "nome": "Taxa de acertos",
        "descricao": "Mantenha uma boa porcentagem de acertos",
        "oculta": False,
        "limiares": {"bronze": 50.0, "prata": 60.0, "ouro": 70.0, "platina": 85.0},
        "moedas": {"bronze": 8, "prata": 18, "ouro": 45, "platina": 90},
        "metric": "media_score_percent",
    },
    {
        "id": "avaliacoes_nota_alta",
        "nome": "Avaliações com nota alta",
        "descricao": "Conclua avaliações com nota 7 ou mais",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 3, "ouro": 5, "platina": 10},
        "moedas": {"bronze": 10, "prata": 22, "ouro": 55, "platina": 110},
        "metric": "avaliacoes_nota_alta",
    },
    {
        "id": "avaliacoes_avancadas",
        "nome": "Avaliações em nível avançado",
        "descricao": "Atinja proficiência avançada (300+) em avaliações",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 3, "ouro": 5, "platina": 10},
        "moedas": {"bronze": 12, "prata": 25, "ouro": 60, "platina": 120},
        "metric": "avaliacoes_avancadas",
    },
    {
        "id": "dias_estudo",
        "nome": "Dias de estudo",
        "descricao": "Complete avaliações em dias diferentes",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 5, "ouro": 10, "platina": 25},
        "moedas": {"bronze": 8, "prata": 18, "ouro": 45, "platina": 90},
        "metric": "dias_estudo",
    },
    # Conquistas extras (mais opções de prata)
    {
        "id": "primeiro_lugar",
        "nome": "Primeiro lugar",
        "descricao": "Fique em 1º lugar em competições",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 2, "ouro": 4, "platina": 8},
        "moedas": {"bronze": 15, "prata": 30, "ouro": 70, "platina": 150},
        "metric": "first_places",
    },
    {
        "id": "segundo_lugar",
        "nome": "Segundo lugar",
        "descricao": "Fique em 2º lugar em competições",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 2, "ouro": 4, "platina": 8},
        "moedas": {"bronze": 10, "prata": 22, "ouro": 50, "platina": 100},
        "metric": "second_places",
    },
    {
        "id": "terceiro_lugar",
        "nome": "Terceiro lugar",
        "descricao": "Fique em 3º lugar em competições",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 2, "ouro": 4, "platina": 8},
        "moedas": {"bronze": 8, "prata": 18, "ouro": 40, "platina": 80},
        "metric": "third_places",
    },
    {
        "id": "nota_dez",
        "nome": "Nota dez",
        "descricao": "Tire nota 10 em avaliações",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 2, "ouro": 4, "platina": 8},
        "moedas": {"bronze": 12, "prata": 25, "ouro": 55, "platina": 110},
        "metric": "avaliacoes_nota_10",
    },
    {
        "id": "prova_perfeita",
        "nome": "Prova perfeita",
        "descricao": "Acerte 100% das questões em uma avaliação",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 2, "ouro": 4, "platina": 8},
        "moedas": {"bronze": 12, "prata": 25, "ouro": 55, "platina": 110},
        "metric": "avaliacoes_100_percent",
    },
    {
        "id": "recorde_acertos",
        "nome": "Recorde de acertos",
        "descricao": "Faça muitos acertos em uma única prova",
        "oculta": False,
        "limiares": {"bronze": 5, "prata": 10, "ouro": 15, "platina": 25},
        "moedas": {"bronze": 8, "prata": 20, "ouro": 48, "platina": 95},
        "metric": "max_acertos_uma_prova",
    },
    {
        "id": "prova_longa",
        "nome": "Prova longa",
        "descricao": "Complete uma prova com muitas questões",
        "oculta": False,
        "limiares": {"bronze": 10, "prata": 20, "ouro": 30, "platina": 50},
        "moedas": {"bronze": 8, "prata": 20, "ouro": 48, "platina": 95},
        "metric": "max_questoes_uma_prova",
    },
    {
        "id": "avaliacoes_boas",
        "nome": "Boas avaliações",
        "descricao": "Conclua avaliações com nota 6 ou mais",
        "oculta": False,
        "limiares": {"bronze": 2, "prata": 5, "ouro": 8, "platina": 15},
        "moedas": {"bronze": 8, "prata": 20, "ouro": 45, "platina": 90},
        "metric": "avaliacoes_nota_6_ou_mais",
    },
    # Conquistas extras (mais opções de ouro)
    {
        "id": "maratonista",
        "nome": "Maratonista",
        "descricao": "Conclua muitas avaliações",
        "oculta": False,
        "limiares": {"bronze": 5, "prata": 15, "ouro": 25, "platina": 50},
        "moedas": {"bronze": 10, "prata": 25, "ouro": 60, "platina": 120},
        "metric": "avaliacoes_concluidas",
    },
    {
        "id": "dez_notas_altas",
        "nome": "Dez notas altas",
        "descricao": "Conclua 10 avaliações com nota 7 ou mais",
        "oculta": False,
        "limiares": {"bronze": 2, "prata": 5, "ouro": 10, "platina": 20},
        "moedas": {"bronze": 10, "prata": 25, "ouro": 60, "platina": 120},
        "metric": "avaliacoes_nota_alta",
    },
    {
        "id": "quinze_dias_estudo",
        "nome": "Quinze dias de estudo",
        "descricao": "Complete avaliações em 15 dias diferentes",
        "oculta": False,
        "limiares": {"bronze": 3, "prata": 7, "ouro": 15, "platina": 30},
        "moedas": {"bronze": 10, "prata": 22, "ouro": 55, "platina": 110},
        "metric": "dias_estudo",
    },
    {
        "id": "master_acertos",
        "nome": "Master em acertos",
        "descricao": "Faça 35 ou mais acertos em uma única prova",
        "oculta": False,
        "limiares": {"bronze": 15, "prata": 25, "ouro": 35, "platina": 50},
        "moedas": {"bronze": 12, "prata": 28, "ouro": 65, "platina": 130},
        "metric": "max_acertos_uma_prova",
    },
    {
        "id": "prova_gigante",
        "nome": "Prova gigante",
        "descricao": "Complete uma prova com 50 ou mais questões",
        "oculta": False,
        "limiares": {"bronze": 20, "prata": 35, "ouro": 50, "platina": 80},
        "moedas": {"bronze": 12, "prata": 28, "ouro": 65, "platina": 130},
        "metric": "max_questoes_uma_prova",
    },
    {
        "id": "centenario_acertos",
        "nome": "Centenário de acertos",
        "descricao": "Acumule 100 acertos no total",
        "oculta": False,
        "limiares": {"bronze": 25, "prata": 50, "ouro": 100, "platina": 300},
        "moedas": {"bronze": 10, "prata": 25, "ouro": 60, "platina": 120},
        "metric": "total_acertos",
    },
    {
        "id": "centenario_questoes",
        "nome": "Centenário de questões",
        "descricao": "Responda 100 questões no total",
        "oculta": False,
        "limiares": {"bronze": 25, "prata": 50, "ouro": 100, "platina": 300},
        "moedas": {"bronze": 10, "prata": 25, "ouro": 60, "platina": 120},
        "metric": "total_questoes",
    },
    {
        "id": "dez_competicoes",
        "nome": "Dez competições",
        "descricao": "Participe de 10 competições",
        "oculta": False,
        "limiares": {"bronze": 2, "prata": 5, "ouro": 10, "platina": 25},
        "moedas": {"bronze": 12, "prata": 28, "ouro": 65, "platina": 130},
        "metric": "competicoes_count",
    },
    {
        "id": "cinco_provas_perfeitas",
        "nome": "Cinco provas perfeitas",
        "descricao": "Acerte 100% em 5 avaliações",
        "oculta": False,
        "limiares": {"bronze": 1, "prata": 3, "ouro": 5, "platina": 10},
        "moedas": {"bronze": 15, "prata": 35, "ouro": 75, "platina": 150},
        "metric": "avaliacoes_100_percent",
    },
    {
        "id": "consistencia",
        "nome": "Consistência",
        "descricao": "Conclua 15 avaliações com nota 6 ou mais",
        "oculta": False,
        "limiares": {"bronze": 5, "prata": 10, "ouro": 15, "platina": 25},
        "moedas": {"bronze": 10, "prata": 25, "ouro": 58, "platina": 115},
        "metric": "avaliacoes_nota_6_ou_mais",
    },
    # Conquistas extras (mais opções de platina)
    {
        "id": "cinquenta_avaliacoes",
        "nome": "Cinquenta avaliações",
        "descricao": "Conclua 50 avaliações",
        "oculta": False,
        "limiares": {"bronze": 10, "prata": 25, "ouro": 40, "platina": 50},
        "moedas": {"bronze": 15, "prata": 35, "ouro": 70, "platina": 140},
        "metric": "avaliacoes_concluidas",
    },
    {
        "id": "vinte_notas_altas",
        "nome": "Vinte notas altas",
        "descricao": "Conclua 20 avaliações com nota 7 ou mais",
        "oculta": False,
        "limiares": {"bronze": 5, "prata": 10, "ouro": 15, "platina": 20},
        "moedas": {"bronze": 15, "prata": 35, "ouro": 70, "platina": 140},
        "metric": "avaliacoes_nota_alta",
    },
    {
        "id": "trinta_dias_estudo",
        "nome": "Trinta dias de estudo",
        "descricao": "Complete avaliações em 30 dias diferentes",
        "oculta": False,
        "limiares": {"bronze": 10, "prata": 20, "ouro": 25, "platina": 30},
        "moedas": {"bronze": 15, "prata": 35, "ouro": 70, "platina": 140},
        "metric": "dias_estudo",
    },
    {
        "id": "cinquenta_acertos_uma_prova",
        "nome": "Cinquenta acertos em uma prova",
        "descricao": "Faça 50 acertos em uma única avaliação",
        "oculta": False,
        "limiares": {"bronze": 25, "prata": 35, "ouro": 45, "platina": 50},
        "moedas": {"bronze": 18, "prata": 40, "ouro": 80, "platina": 160},
        "metric": "max_acertos_uma_prova",
    },
    {
        "id": "cem_questoes_uma_prova",
        "nome": "Cem questões em uma prova",
        "descricao": "Complete uma prova com 100 ou mais questões",
        "oculta": False,
        "limiares": {"bronze": 50, "prata": 70, "ouro": 85, "platina": 100},
        "moedas": {"bronze": 18, "prata": 40, "ouro": 80, "platina": 160},
        "metric": "max_questoes_uma_prova",
    },
    {
        "id": "quinhentos_acertos",
        "nome": "Quinhentos acertos",
        "descricao": "Acumule 500 acertos no total",
        "oculta": False,
        "limiares": {"bronze": 200, "prata": 350, "ouro": 450, "platina": 500},
        "moedas": {"bronze": 15, "prata": 35, "ouro": 70, "platina": 140},
        "metric": "total_acertos",
    },
    {
        "id": "quinhentas_questoes",
        "nome": "Quinhentas questões",
        "descricao": "Responda 500 questões no total",
        "oculta": False,
        "limiares": {"bronze": 200, "prata": 350, "ouro": 450, "platina": 500},
        "moedas": {"bronze": 15, "prata": 35, "ouro": 70, "platina": 140},
        "metric": "total_questoes",
    },
    {
        "id": "vinte_cinco_competicoes",
        "nome": "Vinte e cinco competições",
        "descricao": "Participe de 25 competições",
        "oculta": False,
        "limiares": {"bronze": 5, "prata": 12, "ouro": 18, "platina": 25},
        "moedas": {"bronze": 18, "prata": 40, "ouro": 80, "platina": 160},
        "metric": "competicoes_count",
    },
    {
        "id": "dez_provas_perfeitas",
        "nome": "Dez provas perfeitas",
        "descricao": "Acerte 100% em 10 avaliações",
        "oculta": False,
        "limiares": {"bronze": 3, "prata": 6, "ouro": 8, "platina": 10},
        "moedas": {"bronze": 20, "prata": 45, "ouro": 90, "platina": 180},
        "metric": "avaliacoes_100_percent",
    },
    {
        "id": "excelencia_media",
        "nome": "Excelência em média",
        "descricao": "Mantenha média geral 9 ou mais",
        "oculta": False,
        "limiares": {"bronze": 7.5, "prata": 8.0, "ouro": 8.5, "platina": 9.0},
        "moedas": {"bronze": 18, "prata": 40, "ouro": 80, "platina": 160},
        "metric": "media_grade",
    },
    {
        "id": "proficiencia_maxima",
        "nome": "Proficiência máxima",
        "descricao": "Atinja média de proficiência 350 ou mais",
        "oculta": False,
        "limiares": {"bronze": 300, "prata": 325, "ouro": 340, "platina": 350},
        "moedas": {"bronze": 18, "prata": 40, "ouro": 80, "platina": 160},
        "metric": "media_proficiencia",
    },
    {
        "id": "mestre_podios",
        "nome": "Mestre dos pódios",
        "descricao": "Conquiste 12 pódios em competições",
        "oculta": False,
        "limiares": {"bronze": 5, "prata": 7, "ouro": 9, "platina": 12},
        "moedas": {"bronze": 20, "prata": 45, "ouro": 90, "platina": 180},
        "metric": "total_podiums",
    },
    {
        "id": "oito_primeiros_lugares",
        "nome": "Oito primeiros lugares",
        "descricao": "Fique em 1º lugar em 8 competições",
        "oculta": False,
        "limiares": {"bronze": 2, "prata": 4, "ouro": 6, "platina": 8},
        "moedas": {"bronze": 22, "prata": 50, "ouro": 100, "platina": 200},
        "metric": "first_places",
    },
]

PERFEccionISTA_CONFIG = {
    "id": "perfeccionista",
    "nome": "Perfeccionista",
    "descricao": "Conquiste platina em todas as outras conquistas",
    "oculta": False,
    "limiares": {"platina": 1},
    "moedas": {"platina": 200},
    "metric": "perfeccionista",
}


def _get_student_metrics(student_id: str) -> Dict[str, Any]:
    """Calcula métricas do aluno a partir das tabelas existentes."""
    metrics = {
        "avaliacoes_concluidas": 0,
        "media_grade": 0.0,
        "media_proficiencia": 0.0,
        "total_podiums": 0,
        "competicoes_count": 0,
        "total_acertos": 0,
        "total_questoes": 0,
        "media_score_percent": 0.0,
        "avaliacoes_nota_alta": 0,
        "avaliacoes_avancadas": 0,
        "dias_estudo": 0,
        "first_places": 0,
        "second_places": 0,
        "third_places": 0,
        "avaliacoes_nota_10": 0,
        "avaliacoes_100_percent": 0,
        "max_acertos_uma_prova": 0,
        "max_questoes_uma_prova": 0,
        "avaliacoes_nota_6_ou_mais": 0,
    }

    # Avaliações concluídas (TestSession com status finalizado)
    completed_statuses = ("finalizada", "expirada", "corrigida", "revisada")
    count_sessions = (
        db.session.query(func.count(TestSession.id))
        .filter(
            TestSession.student_id == student_id,
            TestSession.status.in_(completed_statuses),
        )
        .scalar()
    )
    metrics["avaliacoes_concluidas"] = int(count_sessions or 0)

    # Média de nota, proficiência, acertos totais, questões, média % e contagens (EvaluationResult)
    row = (
        db.session.query(
            func.avg(EvaluationResult.grade).label("avg_grade"),
            func.avg(EvaluationResult.proficiency).label("avg_proficiency"),
            func.avg(EvaluationResult.score_percentage).label("avg_score_pct"),
            func.sum(EvaluationResult.correct_answers).label("sum_correct"),
            func.sum(EvaluationResult.total_questions).label("sum_questions"),
        )
        .filter(EvaluationResult.student_id == student_id)
        .first()
    )
    if row:
        metrics["media_grade"] = float(row.avg_grade or 0)
        metrics["media_proficiencia"] = float(row.avg_proficiency or 0)
        metrics["media_score_percent"] = float(row.avg_score_pct or 0)
        metrics["total_acertos"] = int(row.sum_correct or 0)
        metrics["total_questoes"] = int(row.sum_questions or 0)

    # Avaliações com nota >= 7 e com proficiência avançada (>= 300)
    nota_alta = (
        db.session.query(func.count(EvaluationResult.id))
        .filter(EvaluationResult.student_id == student_id, EvaluationResult.grade >= 7)
        .scalar()
    )
    metrics["avaliacoes_nota_alta"] = int(nota_alta or 0)
    avancadas = (
        db.session.query(func.count(EvaluationResult.id))
        .filter(EvaluationResult.student_id == student_id, EvaluationResult.proficiency >= 300)
        .scalar()
    )
    metrics["avaliacoes_avancadas"] = int(avancadas or 0)

    # Avaliações com nota 10 e com 100% de acertos
    nota_10 = (
        db.session.query(func.count(EvaluationResult.id))
        .filter(EvaluationResult.student_id == student_id, EvaluationResult.grade >= 10)
        .scalar()
    )
    metrics["avaliacoes_nota_10"] = int(nota_10 or 0)
    cem_pct = (
        db.session.query(func.count(EvaluationResult.id))
        .filter(EvaluationResult.student_id == student_id, EvaluationResult.score_percentage >= 100)
        .scalar()
    )
    metrics["avaliacoes_100_percent"] = int(cem_pct or 0)

    # Máximo de acertos e de questões em uma única prova
    max_acertos_row = (
        db.session.query(func.max(EvaluationResult.correct_answers))
        .filter(EvaluationResult.student_id == student_id)
        .scalar()
    )
    metrics["max_acertos_uma_prova"] = int(max_acertos_row or 0)
    max_quest_row = (
        db.session.query(func.max(EvaluationResult.total_questions))
        .filter(EvaluationResult.student_id == student_id)
        .scalar()
    )
    metrics["max_questoes_uma_prova"] = int(max_quest_row or 0)

    # Avaliações com nota >= 6
    nota_6_mais = (
        db.session.query(func.count(EvaluationResult.id))
        .filter(EvaluationResult.student_id == student_id, EvaluationResult.grade >= 6)
        .scalar()
    )
    metrics["avaliacoes_nota_6_ou_mais"] = int(nota_6_mais or 0)

    # Dias de estudo: quantidade de dias distintos com pelo menos uma sessão concluída
    try:
        dias = (
            db.session.query(func.count(distinct(cast(TestSession.submitted_at, Date))))
            .filter(
                TestSession.student_id == student_id,
                TestSession.status.in_(completed_statuses),
                TestSession.submitted_at.isnot(None),
            )
            .scalar()
        )
        metrics["dias_estudo"] = int(dias or 0)
    except Exception:
        pass

    # Pódios e competições realizadas (CompetitionResult)
    if _HAS_COMPETITIONS and CompetitionResult is not None:
        try:
            counts = CompetitionStudentRankingService._count_podiums(student_id)
            metrics["total_podiums"] = counts.get("total_podiums", 0)
            metrics["first_places"] = counts.get("first_places", 0)
            metrics["second_places"] = counts.get("second_places", 0)
            metrics["third_places"] = counts.get("third_places", 0)
        except Exception:
            pass
        try:
            comp_count = (
                db.session.query(func.count(CompetitionResult.id))
                .filter(CompetitionResult.student_id == student_id)
                .scalar()
            )
            metrics["competicoes_count"] = int(comp_count or 0)
        except Exception:
            pass

    return metrics


def _medal_for_value(
    value: float,
    limiares: Dict[str, Any],
    higher_is_better: bool = True,
) -> tuple:
    """
    Dado valor atual e limiares {bronze, prata, ouro, platina}, retorna
    (medalha_atual, limiar_atual, proximo_nivel, limiar_proximo, progresso_percent).
    higher_is_better: True para métricas onde maior é melhor (nota, count); True por padrão.
    """
    for i, medal in enumerate(MEDAL_ORDER):
        if medal not in limiares:
            continue
        threshold = limiares[medal]
        if higher_is_better:
            if value < threshold:
                prev_medal = MEDAL_ORDER[i - 1] if i > 0 else None
                prev_threshold = limiares.get(prev_medal, 0) if prev_medal else 0
                if prev_medal is None:
                    progress = (value / threshold * 100) if threshold else 0
                    return (None, 0, medal, threshold, round(min(100, max(0, progress)), 1))
                delta = threshold - prev_threshold
                progress = ((value - prev_threshold) / delta * 100) if delta else 0
                return (prev_medal, prev_threshold, medal, threshold, round(min(100, max(0, progress)), 1))
        else:
            if value > threshold:
                prev_medal = MEDAL_ORDER[i - 1] if i > 0 else None
                prev_threshold = limiares.get(prev_medal, float("inf")) if prev_medal else float("inf")
                delta = prev_threshold - threshold
                progress = ((prev_threshold - value) / delta * 100) if delta else 0
                return (prev_medal, prev_threshold, medal, threshold, round(min(100, max(0, progress)), 1))
    # Atingiu platina (ou último nível)
    last_medal = MEDAL_ORDER[-1] if MEDAL_ORDER else "platina"
    last_threshold = limiares.get(last_medal, 0)
    return (last_medal, last_threshold, None, None, 100.0)


def _build_achievement_item(
    config: Dict[str, Any],
    valor_atual: float,
    redeemed_keys: List[str],
    is_perfeccionista: bool = False,
) -> Dict[str, Any]:
    """Monta um item de conquista para a resposta."""
    oculta = config.get("oculta", False)
    limiares = config.get("limiares", {})

    if is_perfeccionista:
        if valor_atual >= 1:
            medalha_atual = "platina"
            limiar_atual = 1
            proximo_nivel = None
            limiar_proximo = None
            progresso_percent = 100.0
        else:
            medalha_atual = None
            limiar_atual = 0
            proximo_nivel = "platina"
            limiar_proximo = 1
            progresso_percent = 0.0
    else:
        medalha_atual, limiar_atual, proximo_nivel, limiar_proximo, progresso_percent = _medal_for_value(
            valor_atual, limiares, higher_is_better=True
        )

    # Estado: oculta (e não desbloqueada), desbloqueada (tem pelo menos bronze), revelada
    tem_medalha = medalha_atual is not None
    if oculta and not tem_medalha:
        estado = "oculta"
        nome_exibir = "???"
        descricao_exibir = "???"
    else:
        estado = "desbloqueada" if tem_medalha else "revelada"
        nome_exibir = config.get("nome", "")
        descricao_exibir = config.get("descricao", "")

    moedas_config = config.get("moedas", {})
    moedas_valor = moedas_config.get(medalha_atual or "bronze", 0)
    if medalha_atual is None and not is_perfeccionista:
        moedas_valor = moedas_config.get("bronze", 0)

    chave_resgate = f"{config['id']}_{medalha_atual}" if medalha_atual else None
    resgatado = chave_resgate in redeemed_keys if chave_resgate else False

    return {
        "id": config["id"],
        "nome": nome_exibir,
        "descricao": descricao_exibir,
        "estado": estado,
        "medalha_atual": medalha_atual,
        "valor_atual": valor_atual if not is_perfeccionista else (1 if valor_atual >= 1 else 0),
        "limiar_atual": limiar_atual,
        "proximo_nivel": proximo_nivel,
        "limiar_proximo": limiar_proximo,
        "progresso_percent": progresso_percent,
        "moedas_valor": moedas_valor,
        "resgatado": resgatado,
    }


def get_conquistas(
    student_id: str,
    redeemed_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Retorna conquistas do aluno com estado, medalha, progresso e resgatado.
    redeemed_keys: lista de chaves "achievement_id_medalha" (ex.: avaliacoes_concluidas_ouro) de User.traits["achievements_redeemed"].
    """
    redeemed_keys = redeemed_keys or []
    metrics = _get_student_metrics(student_id)

    conquistas: List[Dict[str, Any]] = []
    medal_counts = {"bronze": 0, "prata": 0, "ouro": 0, "platina": 0}

    for cfg in ACHIEVEMENTS_CONFIG:
        metric_name = cfg.get("metric")
        valor = metrics.get(metric_name, 0)
        item = _build_achievement_item(cfg, valor, redeemed_keys, is_perfeccionista=False)
        conquistas.append(item)
        if item.get("medalha_atual"):
            medal_counts[item["medalha_atual"]] = medal_counts.get(item["medalha_atual"], 0) + 1

    # Perfeccionista: todas as outras 5 em platina?
    all_platina = all(
        c.get("medalha_atual") == "platina"
        for c in conquistas
    )
    valor_perfeccionista = 1.0 if all_platina else 0.0
    item_perf = _build_achievement_item(
        PERFEccionISTA_CONFIG,
        valor_perfeccionista,
        redeemed_keys,
        is_perfeccionista=True,
    )
    conquistas.append(item_perf)
    if item_perf.get("medalha_atual") == "platina":
        medal_counts["platina"] = medal_counts.get("platina", 0) + 1

    return {
        "conquistas": conquistas,
        "resumo_medalhas": medal_counts,
    }


def get_redeemed_keys_from_user(user: Any) -> List[str]:
    """Extrai lista de chaves de conquistas já resgatadas de User.traits."""
    if user is None:
        return []
    traits = getattr(user, "traits", None) or {}
    if not isinstance(traits, dict):
        return []
    return list(traits.get("achievements_redeemed") or [])


def get_coin_value_for_medal(achievement_id: str, medalha: str) -> Optional[int]:
    """Retorna valor em moedas para um par (achievement_id, medalha). None se inválido."""
    if achievement_id == "perfeccionista":
        cfg = PERFEccionISTA_CONFIG
        return cfg.get("moedas", {}).get(medalha)
    for cfg in ACHIEVEMENTS_CONFIG:
        if cfg["id"] == achievement_id:
            return cfg.get("moedas", {}).get(medalha)
    return None


def student_has_medal(
    student_id: str,
    achievement_id: str,
    medalha: str,
) -> bool:
    """Verifica se o aluno atingiu a medalha indicada para a conquista."""
    if medalha not in MEDAL_ORDER:
        return False
    result = get_conquistas(student_id, redeemed_keys=[])
    for c in result.get("conquistas", []):
        if c["id"] == achievement_id:
            return c.get("medalha_atual") == medalha
    return False
