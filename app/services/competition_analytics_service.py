# -*- coding: utf-8 -*-
"""
Serviço de Analytics de Competições (Etapa 7).
Calcula métricas estatísticas para relatórios administrativos.
"""
from typing import Dict, Any, List
from sqlalchemy import func

from app import db
from app.competitions.models import Competition, CompetitionEnrollment, CompetitionResult
from app.models.testSession import TestSession
from app.models.student import Student
from app.services.competition_ranking_service import CompetitionRankingService
import logging

logger = logging.getLogger(__name__)


class CompetitionAnalyticsService:
    @staticmethod
    def get_analytics(competition_id: str) -> Dict[str, Any]:
        """
        Retorna analytics completos da competição:
        - Taxa de inscrição (inscritos / alunos elegíveis)
        - Taxa de participação (entregaram prova / inscritos)
        - Médias (nota, tempo, acertos)
        - Distribuição de notas (buckets)
        - Top 10 alunos
        - Comparação com competições anteriores (opcional)
        """
        competition = Competition.query.get(competition_id)
        if not competition:
            raise ValueError(f"Competição {competition_id} não encontrada")

        eligible_count = CompetitionAnalyticsService._get_eligible_students_count(competition)
        enrolled_count = CompetitionAnalyticsService._get_enrolled_count(competition_id)
        participated_count = CompetitionAnalyticsService._get_participated_count(competition_id)

        # Estruturas detalhadas usadas internamente
        enrollment_summary = {
            "eligible_students": eligible_count,
            "enrolled_students": enrolled_count,
            "rate": round((enrolled_count / eligible_count * 100) if eligible_count > 0 else 0.0, 2),
        }

        participation_summary = {
            "enrolled_students": enrolled_count,
            "participated_students": participated_count,
            "rate": round((participated_count / enrolled_count * 100) if enrolled_count > 0 else 0.0, 2),
        }

        averages = CompetitionAnalyticsService._calculate_averages(competition_id)
        grade_distribution = CompetitionAnalyticsService._get_grade_distribution(competition_id)
        top_10 = CompetitionAnalyticsService._get_top_10(competition_id)

        result = {
            "competition_id": competition_id,
            "competition_name": competition.name,
            # Campos numéricos simples para o frontend (para uso direto com toFixed, gráficos, etc.)
            "enrollment_rate": enrollment_summary["rate"],
            "participation_rate": participation_summary["rate"],
            # Campos detalhados com contagens brutas
            "enrollment": enrollment_summary,
            "participation": participation_summary,
            "averages": averages,
            "grade_distribution": grade_distribution,
            "top_10": top_10,
        }

        # Comparação com competições anteriores (opcional)
        try:
            comparison = CompetitionAnalyticsService._compare_with_previous(competition)
            if comparison:
                result["comparison_with_previous"] = comparison
        except Exception as e:
            logger.warning(f"Erro ao calcular comparação com competições anteriores: {e}")

        return result

    @staticmethod
    def _get_eligible_students_count(competition: Competition) -> int:
        """
        Conta alunos elegíveis baseado em nível e escopo.
        Reutiliza lógica de get_available_competitions_for_student.
        """
        from app.competitions.services.competition_service import _student_level_matches, _student_in_scope
        from app.competitions.constants import student_grade_matches_level

        # Buscar todos os alunos do sistema
        all_students = Student.query.all()

        eligible_count = 0
        for student in all_students:
            # Verificar nível
            if not _student_level_matches(student, competition.level):
                continue
            # Verificar escopo
            if not _student_in_scope(student, competition):
                continue
            eligible_count += 1

        return eligible_count

    @staticmethod
    def _get_enrolled_count(competition_id: str) -> int:
        """Conta alunos inscritos na competição."""
        return CompetitionEnrollment.query.filter_by(
            competition_id=competition_id,
            status='inscrito',
        ).count()

    @staticmethod
    def _get_participated_count(competition_id: str) -> int:
        """
        Conta alunos que entregaram a prova (TestSession finalizadas).
        Filtra por escopo da competição.
        """
        competition = Competition.query.get(competition_id)
        if not competition or not competition.test_id:
            return 0

        sessions = TestSession.query.filter(
            TestSession.test_id == competition.test_id,
            TestSession.status.in_(['finalizada', 'expirada', 'corrigida', 'revisada']),
        ).all()

        # Filtrar por escopo
        from app.competitions.services.competition_service import _student_in_scope
        participated_student_ids = set()
        for session in sessions:
            student = Student.query.get(session.student_id)
            if student and _student_in_scope(student, competition):
                participated_student_ids.add(session.student_id)

        return len(participated_student_ids)

    @staticmethod
    def _calculate_averages(competition_id: str) -> Dict[str, float]:
        """
        Calcula médias de:
        - nota
        - tempo (minutos)
        - acertos
        - proficiência

        Para competições encerradas usa CompetitionResult (snapshot final),
        que já contém os mesmos valores calculados nas avaliações.
        Para competições em andamento usa CompetitionRankingService.calculate_ranking
        (que reutiliza os cálculos da avaliação).
        """
        competition = Competition.query.get(competition_id)
        if not competition or not competition.test_id:
            return {
                "grade": 0.0,
                "duration_minutes": 0.0,
                "correct_answers": 0.0,
                "proficiency": 0.0,
            }

        if competition.status == 'encerrada':
            # Usar competition_results
            results = CompetitionResult.query.filter_by(competition_id=competition_id).all()
            if not results:
                return {
                    "grade": 0.0,
                    "duration_minutes": 0.0,
                    "correct_answers": 0.0,
                    "proficiency": 0.0,
                }

            grades = [r.grade for r in results if r.grade is not None]
            durations = [r.tempo_gasto for r in results if r.tempo_gasto is not None]
            corrects = [r.correct_answers for r in results if r.correct_answers is not None]
            profs = [r.proficiency for r in results if r.proficiency is not None]

            return {
                "grade": round(sum(grades) / len(grades), 2) if grades else 0.0,
                "duration_minutes": round(sum(durations) / len(durations), 2) if durations else 0.0,
                "correct_answers": round(sum(corrects) / len(corrects), 2) if corrects else 0.0,
                "proficiency": round(sum(profs) / len(profs), 2) if profs else 0.0,
            }
        else:
            # Para competições em andamento, reutilizar o mesmo cálculo do ranking,
            # que já enriquece cada sessão com proficiência e demais métricas.
            ranking = CompetitionRankingService.calculate_ranking(competition_id)
            if not ranking:
                return {
                    "grade": 0.0,
                    "duration_minutes": 0.0,
                    "correct_answers": 0.0,
                    "proficiency": 0.0,
                }

            grades = [item.get("grade") for item in ranking if item.get("grade") is not None]
            durations = [item.get("duration_minutes") for item in ranking if item.get("duration_minutes") is not None]
            corrects = [item.get("correct_answers") for item in ranking if item.get("correct_answers") is not None]
            profs = [item.get("proficiency") for item in ranking if item.get("proficiency") is not None]

            return {
                "grade": round(sum(grades) / len(grades), 2) if grades else 0.0,
                "duration_minutes": round(sum(durations) / len(durations), 2) if durations else 0.0,
                "correct_answers": round(sum(corrects) / len(corrects), 2) if corrects else 0.0,
                "proficiency": round(sum(profs) / len(profs), 2) if profs else 0.0,
            }

    @staticmethod
    def _get_grade_distribution(competition_id: str) -> List[Dict[str, Any]]:
        """
        Cria buckets de distribuição de notas (0-20, 21-40, 41-60, 61-80, 81-100).
        Retorna lista com range e count.
        """
        competition = Competition.query.get(competition_id)
        if not competition or not competition.test_id:
            return [
                {"range": "0-20", "count": 0},
                {"range": "21-40", "count": 0},
                {"range": "41-60", "count": 0},
                {"range": "61-80", "count": 0},
                {"range": "81-100", "count": 0},
            ]

        # Buscar notas
        if competition.status == 'encerrada':
            results = CompetitionResult.query.filter_by(competition_id=competition_id).all()
            grades = [r.grade for r in results if r.grade is not None]
        else:
            sessions = TestSession.query.filter(
                TestSession.test_id == competition.test_id,
                TestSession.status.in_(['finalizada', 'expirada', 'corrigida', 'revisada']),
            ).all()

            from app.competitions.services.competition_service import _student_in_scope
            filtered_sessions = []
            for session in sessions:
                student = Student.query.get(session.student_id)
                if student and _student_in_scope(student, competition):
                    filtered_sessions.append(session)

            grades = [s.grade for s in filtered_sessions if s.grade is not None]

        # Contar por bucket
        buckets = {
            "0-20": 0,
            "21-40": 0,
            "41-60": 0,
            "61-80": 0,
            "81-100": 0,
        }

        for grade in grades:
            if 0 <= grade <= 20:
                buckets["0-20"] += 1
            elif 21 <= grade <= 40:
                buckets["21-40"] += 1
            elif 41 <= grade <= 60:
                buckets["41-60"] += 1
            elif 61 <= grade <= 80:
                buckets["61-80"] += 1
            elif 81 <= grade <= 100:
                buckets["81-100"] += 1

        return [
            {"range": "0-20", "count": buckets["0-20"]},
            {"range": "21-40", "count": buckets["21-40"]},
            {"range": "41-60", "count": buckets["41-60"]},
            {"range": "61-80", "count": buckets["61-80"]},
            {"range": "81-100", "count": buckets["81-100"]},
        ]

    @staticmethod
    def _get_top_10(competition_id: str) -> List[Dict[str, Any]]:
        """
        Retorna top 10 alunos do ranking.
        Usa CompetitionRankingService.get_ranking com limit=10.
        """
        ranking = CompetitionRankingService.get_ranking(competition_id, limit=10, enriquecer=True)
        return ranking

    @staticmethod
    def _compare_with_previous(competition: Competition) -> Dict[str, Any]:
        """
        Compara métricas com competições anteriores do mesmo template ou mesma disciplina/nível.
        Retorna dict com comparações ou None se não houver competições anteriores.
        """
        # Buscar competições anteriores (mesmo template ou mesma disciplina/nível)
        previous_competitions = Competition.query.filter(
            Competition.id != competition.id,
            Competition.status == 'encerrada',
            Competition.subject_id == competition.subject_id,
            Competition.level == competition.level,
        ).order_by(Competition.created_at.desc()).limit(5).all()

        if not previous_competitions:
            return None

        # Calcular médias das competições anteriores
        previous_averages = []
        previous_enrollment_rates = []

        for prev_comp in previous_competitions:
            try:
                enrolled = CompetitionAnalyticsService._get_enrolled_count(prev_comp.id)
                participated = CompetitionAnalyticsService._get_participated_count(prev_comp.id)
                eligible = CompetitionAnalyticsService._get_eligible_students_count(prev_comp)

                enrollment_rate = (enrolled / eligible * 100) if eligible > 0 else 0.0
                previous_enrollment_rates.append(enrollment_rate)

                averages = CompetitionAnalyticsService._calculate_averages(prev_comp.id)
                previous_averages.append(averages)
            except Exception as e:
                logger.warning(f"Erro ao calcular métricas de competição anterior {prev_comp.id}: {e}")
                continue

        if not previous_averages:
            return None

        # Calcular médias das competições anteriores
        avg_grade_prev = sum(a.get("grade", 0) for a in previous_averages) / len(previous_averages) if previous_averages else 0.0
        avg_enrollment_prev = sum(previous_enrollment_rates) / len(previous_enrollment_rates) if previous_enrollment_rates else 0.0

        # Calcular métricas atuais
        current_enrolled = CompetitionAnalyticsService._get_enrolled_count(competition.id)
        current_eligible = CompetitionAnalyticsService._get_eligible_students_count(competition)
        current_enrollment_rate = (current_enrolled / current_eligible * 100) if current_eligible > 0 else 0.0

        current_averages = CompetitionAnalyticsService._calculate_averages(competition.id)
        current_avg_grade = current_averages.get("grade", 0.0)

        return {
            "previous_competitions_count": len(previous_competitions),
            "average_grade_previous": round(avg_grade_prev, 2),
            "average_grade_current": round(current_avg_grade, 2),
            "grade_difference": round(current_avg_grade - avg_grade_prev, 2),
            "average_enrollment_rate_previous": round(avg_enrollment_prev, 2),
            "enrollment_rate_current": round(current_enrollment_rate, 2),
            "enrollment_rate_difference": round(current_enrollment_rate - avg_enrollment_prev, 2),
        }
