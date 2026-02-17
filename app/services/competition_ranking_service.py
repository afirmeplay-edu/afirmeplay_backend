# -*- coding: utf-8 -*-
"""
Serviço de ranking de competições (Etapa 5).
- Durante a competição: ranking em tempo real a partir dos resultados da avaliação.
- Ao encerrar: snapshot em competition_results, pagamento de moedas de ranking.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional

from app import db
from app.competitions.models import Competition, CompetitionResult, CompetitionRankingPayout
from app.models.testSession import TestSession
from app.models.evaluationResult import EvaluationResult
from app.models.student import Student
from app.models.school import School
from app.models.city import City
import logging

logger = logging.getLogger(__name__)

# Critérios de ordenação suportados
CRITERIA_NOTA = 'nota'
CRITERIA_TEMPO = 'tempo'
TIEBREAKER_TEMPO_ENTREGA = 'tempo_entrega'
TIEBREAKER_NOTA = 'nota'


class CompetitionRankingService:
    @staticmethod
    def _enrich_session_with_evaluation(session: TestSession) -> Dict[str, Any]:
        """
        Enriquece uma TestSession com dados de EvaluationResult (proficiência, classificação).
        """
        ev = EvaluationResult.query.filter_by(session_id=session.id).first()
        if not ev:
            ev = EvaluationResult.query.filter_by(
                test_id=session.test_id,
                student_id=session.student_id,
            ).first()
        grade = session.grade if session.grade is not None else (ev.grade if ev else 0.0)
        correct = session.correct_answers if session.correct_answers is not None else (ev.correct_answers if ev else 0)
        total = session.total_questions if session.total_questions is not None else (ev.total_questions if ev else 0)
        score_pct = (correct / total * 100) if total and total > 0 else 0.0
        proficiency = ev.proficiency if ev else None
        classification = ev.classification if ev else None
        duration = session.duration_minutes if session.duration_minutes is not None else (getattr(session, 'duration_minutes', None))
        if duration is None and session.started_at and session.submitted_at:
            duration = int((session.submitted_at - session.started_at).total_seconds() / 60)
        return {
            'student_id': session.student_id,
            'session_id': session.id,
            'grade': float(grade) if grade is not None else 0.0,
            'correct_answers': correct,
            'total_questions': total,
            'score_percentage': round(score_pct, 2),
            'proficiency': float(proficiency) if proficiency is not None else None,
            'classification': classification,
            'duration_minutes': duration if duration is not None else 999999,
            'submitted_at': session.submitted_at,
            'acertos': correct,
            'erros': (total - correct) if total else 0,
            'em_branco': 0,
        }

    @staticmethod
    def calculate_ranking(competition_id: str) -> List[Dict[str, Any]]:
        """
        Calcula ranking a partir dos resultados da avaliação (test_sessions + evaluation_results).
        Usado para exibir ranking ao vivo e no passo de finalização.
        Retorna lista ordenada de {student_id, session_id, position, grade, proficiency, ...}.
        Filtra por escopo da competição (turma/escola/município).
        """
        competition = Competition.query.get(competition_id)
        if not competition or not competition.test_id:
            return []

        sessions = TestSession.query.filter(
            TestSession.test_id == competition.test_id,
            TestSession.status.in_(['finalizada', 'expirada', 'corrigida', 'revisada']),
        ).all()

        # Filtrar sessões por escopo da competição
        from app.competitions.services.competition_service import _student_in_scope
        filtered_sessions = []
        for session in sessions:
            student = Student.query.get(session.student_id)
            if student and _student_in_scope(student, competition):
                filtered_sessions.append(session)

        rows = [CompetitionRankingService._enrich_session_with_evaluation(s) for s in filtered_sessions]
        if not rows:
            return []

        criteria = (competition.ranking_criteria or CRITERIA_NOTA).strip().lower()
        tiebreaker = (competition.ranking_tiebreaker or TIEBREAKER_TEMPO_ENTREGA).strip().lower()

        def sort_key(r):
            if criteria == CRITERIA_TEMPO:
                primary = (r['duration_minutes'], -(r['grade'] or 0))
                if tiebreaker == TIEBREAKER_NOTA:
                    return (r['duration_minutes'], -(r['grade'] or 0), r['submitted_at'] or datetime.max)
                return (r['duration_minutes'], r['submitted_at'] or datetime.max, -(r['grade'] or 0))
            else:
                # nota (maior melhor)
                primary = (-(r['grade'] or 0), r['duration_minutes'])
                if tiebreaker == TIEBREAKER_TEMPO_ENTREGA:
                    return (-(r['grade'] or 0), r['submitted_at'] or datetime.max, r['duration_minutes'])
                return (-(r['grade'] or 0), r['duration_minutes'], r['submitted_at'] or datetime.max)

        rows.sort(key=sort_key)

        # Atribuir posições considerando EMPATE:
        # - value = nota (quando criteria='nota') ou tempo (quando criteria='tempo')
        # - todos com o mesmo value compartilham a mesma posição (ex.: empate triplo em 1º lugar)
        ranking = []
        last_value = None
        current_position = 0
        for idx, r in enumerate(rows, start=1):
            value = r['grade'] if criteria == CRITERIA_NOTA else r['duration_minutes']
            if last_value is None or value != last_value:
                # Novo valor → posição passa a ser o índice atual (1‑based)
                current_position = idx
                last_value = value
            r['position'] = current_position
            r['value'] = value
            ranking.append(r)
        return ranking

    @staticmethod
    def finalize_competition_and_save_results(competition_id: str) -> None:
        """
        Chamado uma vez quando a competição é encerrada.
        1) Calcula ranking a partir dos resultados da avaliação.
        2) Grava snapshot em competition_results.
        3) Paga moedas de ranking e registra em competition_ranking_payouts.
        4) Atualiza moedas_ganhas em competition_results.
        """
        competition = Competition.query.get_or_404(competition_id)
        ranking = CompetitionRankingService.calculate_ranking(competition_id)
        now = datetime.utcnow()

        # Evitar dupla finalização
        existing = CompetitionResult.query.filter_by(competition_id=competition_id).first()
        if existing:
            logger.warning(f"Competição {competition_id} já possui competition_results; ignorando finalize.")
            return

        coins_by_student = CompetitionRankingService.pay_ranking_rewards(competition_id, ranking)

        from app.services.competition_student_ranking_service import (
            CompetitionStudentRankingService,
        )

        for item in ranking:
            correct = item.get('correct_answers', 0) or 0
            total = item.get('total_questions', 0) or 0
            score_pct = (correct / total * 100) if total > 0 else 0.0
            grade = item.get('grade') or 0.0
            moedas = coins_by_student.get(item['student_id'], 0)

            result = CompetitionResult(
                competition_id=competition_id,
                student_id=item['student_id'],
                session_id=item['session_id'],
                posicao=item['position'],
                correct_answers=correct,
                total_questions=total,
                score_percentage=round(score_pct, 2),
                grade=round(float(grade), 2),
                proficiency=item.get('proficiency'),
                classification=item.get('classification'),
                moedas_ganhas=moedas,
                tempo_gasto=item.get('duration_minutes'),
                acertos=item.get('acertos', correct),
                erros=item.get('erros', max(0, total - correct)),
                em_branco=item.get('em_branco', 0),
                calculated_at=now,
            )
            db.session.add(result)

            # Se novo 1º lugar, aciona serviço de classificação para possível certificado
            if item.get("position") == 1:
                try:
                    CompetitionStudentRankingService.handle_new_first_place(
                        student_id=item["student_id"],
                        competition_id=competition_id,
                    )
                except Exception:
                    logger.exception(
                        "Falha ao processar classificação/certificado para student_id=%s em competition_id=%s",
                        item["student_id"],
                        competition_id,
                    )

        db.session.commit()
        logger.info(f"Competição {competition_id}: snapshot competition_results gravado e ranking pago.")

    @staticmethod
    def finalize_all_expired_competitions() -> Dict[str, Any]:
        """
        Processa todas as competições expiradas que ainda não foram finalizadas.
        Grava snapshot em competition_results, paga moedas de ranking e define status='encerrada'.
        Pode ser chamado por um job em background (thread) ou pela task Celery.
        Retorna: { "processed": int, "total_candidates": int, "errors": list }.
        """
        # Buscar todas as competições abertas ou em andamento
        # e filtrar usando a property is_finished que já considera o timezone corretamente
        candidate_competitions = Competition.query.filter(
            Competition.status.in_(['aberta', 'em_andamento']),
        ).all()
        
        # Filtrar apenas as que realmente estão expiradas usando is_finished property
        # que já interpreta os horários corretamente no timezone da competição
        competitions = [c for c in candidate_competitions if c.is_finished]
        
        processed = 0
        errors = []
        for competition in competitions:
            try:
                if CompetitionResult.query.filter_by(competition_id=competition.id).count() > 0:
                    continue
                CompetitionRankingService.finalize_competition_and_save_results(competition.id)
                competition.status = 'encerrada'
                db.session.commit()
                processed += 1
                logger.info("Competição %s encerrada; results e ranking pagos.", competition.id)
            except Exception as e:
                logger.exception("Erro ao finalizar competição %s: %s", competition.id, str(e))
                db.session.rollback()
                errors.append({"competition_id": competition.id, "error": str(e)})
        return {
            "processed": processed,
            "total_candidates": len(competitions),
            "errors": errors,
        }

    @staticmethod
    def pay_ranking_rewards(
        competition_id: str, ranking: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, int]:
        """
        Credita moedas para posições premiadas (CoinService).
        Registra em competition_ranking_payouts.
        Retorna dict student_id -> quantidade de moedas creditadas.
        """
        from app.balance.services.coin_service import CoinService

        competition = Competition.query.get(competition_id)
        if ranking is None:
            ranking = CompetitionRankingService.calculate_ranking(competition_id)

        config = competition.reward_config or {}
        ranking_rewards = config.get('ranking_rewards') or []
        coins_by_student = {}

        for reward_cfg in ranking_rewards:
            pos = reward_cfg.get('position')
            coins = reward_cfg.get('coins')
            if pos is None or coins is None or pos < 1 or coins < 1:
                continue
            # Em caso de empate de posição (ex.: vários com position=1),
            # todos os alunos com aquela posição recebem as moedas configuradas.
            for item in ranking:
                if item.get('position') != pos:
                    continue
                student_id = item['student_id']
                try:
                    CoinService.credit_coins(
                        student_id=student_id,
                        amount=coins,
                        reason='competition_ranking',
                        competition_id=competition_id,
                        test_session_id=item.get('session_id'),
                        description=f"Ranking posição {pos} (empate) - {competition.name}",
                    )
                    coins_by_student[student_id] = coins_by_student.get(student_id, 0) + coins
                    payout = CompetitionRankingPayout(
                        competition_id=competition_id,
                        student_id=student_id,
                        position=pos,
                        amount=coins,
                        paid_at=datetime.utcnow(),
                    )
                    db.session.add(payout)
                except Exception as e:
                    logger.error(f"Erro ao creditar moedas de ranking para student_id={student_id}: {e}", exc_info=True)

        db.session.commit()
        return coins_by_student

    @staticmethod
    def get_ranking(
        competition_id: str, limit: int = 100, enriquecer: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Se competição encerrada: lê de competition_results (ranking oficial).
        Se competição em andamento: calcula em tempo real (calculate_ranking).
        Se enriquecer=True, adiciona student_name, student_class, etc.
        """
        competition = Competition.query.get(competition_id)
        if not competition:
            return []

        if competition.status == 'encerrada':
            # Para competições encerradas, preferimos ler o snapshot oficial em competition_results.
            results = (
                CompetitionResult.query.filter_by(competition_id=competition_id)
                .order_by(CompetitionResult.posicao)
                .limit(limit)
                .all()
            )
            if results:
                out = []
                for r in results:
                    row = {
                        'position': r.posicao,
                        'student_id': r.student_id,
                        'session_id': r.session_id,
                        'value': r.grade,
                        'grade': r.grade,
                        'proficiency': r.proficiency,
                        'classification': r.classification,
                        'correct_answers': r.correct_answers,
                        'total_questions': r.total_questions,
                        'score_percentage': r.score_percentage,
                        'tempo_gasto': r.tempo_gasto,
                        'moedas_ganhas': r.moedas_ganhas,
                    }
                    if enriquecer:
                        CompetitionRankingService._enrich_result_row(row)
                    out.append(row)
                return out

            # Fallback defensivo: se status estiver 'encerrada' mas ainda não existir snapshot
            # (ex.: bug anterior ou finalização não executada), calcular ranking em tempo real.
            ranking = CompetitionRankingService.calculate_ranking(competition_id)[:limit]
            if not enriquecer:
                return ranking
            for row in ranking:
                CompetitionRankingService._enrich_result_row(row)
            return ranking
        else:
            ranking = CompetitionRankingService.calculate_ranking(competition_id)[:limit]
            if not enriquecer:
                return ranking
            for row in ranking:
                CompetitionRankingService._enrich_result_row(row)
            return ranking

    @staticmethod
    def _enrich_result_row(row: Dict[str, Any]) -> None:
        """Adiciona student_name, class_name, school_id, school_name e state/city ao item do ranking."""
        student = Student.query.get(row.get('student_id'))
        if not student:
            row['student_name'] = None
            row['student_class'] = None
            row['school_name'] = None
            return
        row['student_name'] = student.name
        row['student_class'] = getattr(student, 'class_id', None)
        if student.class_id:
            try:
                from app.models.studentClass import Class
                c = Class.query.get(student.class_id)
                row['class_name'] = c.name if c else None
            except Exception:
                row['class_name'] = None
        else:
            row['class_name'] = None
        # IDs brutos de escola e cidade (úteis para filtros por escopo)
        row["school_id"] = getattr(student, "school_id", None)

        if getattr(student, "school_id", None):
            try:
                s = School.query.get(student.school_id)
                row["school_name"] = s.name if s else None
                if s and getattr(s, "city_id", None):
                    city = City.query.get(s.city_id)
                    if city:
                        row["city_id"] = city.id
                        row["city_name"] = city.name
                        row["state_name"] = city.state
            except Exception:
                row["school_name"] = None
        else:
            row["school_name"] = None

    @staticmethod
    def get_my_ranking(competition_id: str, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Retorna a posição do aluno no ranking e dados resumidos.
        Retorna None se o aluno não tiver resultado na competição.
        """
        competition = Competition.query.get(competition_id)
        if not competition:
            return None

        if competition.status == 'encerrada':
            result = CompetitionResult.query.filter_by(
                competition_id=competition_id,
                student_id=student_id,
            ).first()
            if not result:
                return None
            total = CompetitionResult.query.filter_by(competition_id=competition_id).count()
            return {
                'position': result.posicao,
                'total_participants': total,
                'value': result.grade,
                'grade': result.grade,
                'proficiency': result.proficiency,
                'correct_answers': result.correct_answers,
                'total_questions': result.total_questions,
                'coins_earned': result.moedas_ganhas,
            }
        else:
            ranking = CompetitionRankingService.calculate_ranking(competition_id)
            total = len(ranking)
            for item in ranking:
                if item.get('student_id') == student_id:
                    coins = 0
                    config = competition.reward_config or {}
                    for rc in (config.get('ranking_rewards') or []):
                        if rc.get('position') == item.get('position') and rc.get('coins'):
                            coins = rc.get('coins', 0)
                            break
                    return {
                        'position': item['position'],
                        'total_participants': total,
                        'value': item.get('grade'),
                        'grade': item.get('grade'),
                        'proficiency': item.get('proficiency'),
                        'correct_answers': item.get('correct_answers'),
                        'total_questions': item.get('total_questions'),
                        'coins_earned': coins,
                    }
            return None
