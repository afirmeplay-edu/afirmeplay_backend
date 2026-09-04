# -*- coding: utf-8 -*-
"""
Remove dados do aluno no tenant (respostas, resultados, sessões, etc.)
sem apagar turmas, ClassTest ou avaliações.

Ordem respeita FKs (ex.: evaluation_results.session_id -> test_sessions).
"""
from __future__ import annotations

import logging
from typing import Iterable, List, Union

logger = logging.getLogger(__name__)


def delete_student_tenant_dependencies(student_ids: Union[str, Iterable[str]]) -> None:
    """
    Apaga registros ligados ao(s) aluno(s). Não remove Student nem Class/Test/ClassTest.

    Args:
        student_ids: um id ou iterável de ids (string).
    """
    if isinstance(student_ids, str):
        ids: List[str] = [student_ids]
    else:
        ids = [str(x) for x in student_ids if x]
    if not ids:
        return

    from app.physical_tests.models.physicalTestForm import PhysicalTestForm
    from app.physical_tests.models.physicalTestAnswer import PhysicalTestAnswer
    from app.exams.models.studentAnswer import StudentAnswer
    from app.exams.models.testSession import TestSession
    from app.evaluations.models.evaluationResult import EvaluationResult
    from app.answer_sheets.models.answerSheetResult import AnswerSheetResult
    from app.models.studentTestOlimpics import StudentTestOlimpics
    from app.answer_sheets.models.formCoordinates import FormCoordinates
    from app.models.studentPasswordLog import StudentPasswordLog

    physical_forms_subq = (
        PhysicalTestForm.query.with_entities(PhysicalTestForm.id)
        .filter(PhysicalTestForm.student_id.in_(ids))
        .subquery()
    )
    PhysicalTestAnswer.query.filter(
        PhysicalTestAnswer.physical_form_id.in_(physical_forms_subq)
    ).delete(synchronize_session=False)
    PhysicalTestForm.query.filter(PhysicalTestForm.student_id.in_(ids)).delete(
        synchronize_session=False
    )

    StudentAnswer.query.filter(StudentAnswer.student_id.in_(ids)).delete(
        synchronize_session=False
    )

    try:
        from app.competitions.models.competition_enrollment import CompetitionEnrollment
        from app.competitions.models.competition_result import CompetitionResult
        from app.competitions.models.competition_reward import CompetitionReward
        from app.competitions.models.competition_ranking_payout import CompetitionRankingPayout

        CompetitionEnrollment.query.filter(
            CompetitionEnrollment.student_id.in_(ids)
        ).delete(synchronize_session=False)
        CompetitionReward.query.filter(CompetitionReward.student_id.in_(ids)).delete(
            synchronize_session=False
        )
        CompetitionRankingPayout.query.filter(
            CompetitionRankingPayout.student_id.in_(ids)
        ).delete(synchronize_session=False)
        CompetitionResult.query.filter(CompetitionResult.student_id.in_(ids)).delete(
            synchronize_session=False
        )
    except Exception as e:
        logger.warning("Competition cleanup skipped or partial: %s", e)

    try:
        from app.balance.models.coin_transaction import CoinTransaction
        from app.balance.models.student_coins import StudentCoins

        CoinTransaction.query.filter(CoinTransaction.student_id.in_(ids)).delete(
            synchronize_session=False
        )
        StudentCoins.query.filter(StudentCoins.student_id.in_(ids)).delete(
            synchronize_session=False
        )
    except Exception as e:
        logger.warning("Balance cleanup skipped or partial: %s", e)

    try:
        from app.certification.models.certificate import Certificate

        Certificate.query.filter(Certificate.student_id.in_(ids)).delete(
            synchronize_session=False
        )
    except Exception as e:
        logger.warning("Certificate cleanup skipped or partial: %s", e)

    # evaluation_results referencia test_sessions: apagar resultados antes das sessões
    EvaluationResult.query.filter(EvaluationResult.student_id.in_(ids)).delete(
        synchronize_session=False
    )
    TestSession.query.filter(TestSession.student_id.in_(ids)).delete(
        synchronize_session=False
    )

    AnswerSheetResult.query.filter(AnswerSheetResult.student_id.in_(ids)).delete(
        synchronize_session=False
    )
    StudentTestOlimpics.query.filter(StudentTestOlimpics.student_id.in_(ids)).delete(
        synchronize_session=False
    )
    FormCoordinates.query.filter(FormCoordinates.student_id.in_(ids)).delete(
        synchronize_session=False
    )
    StudentPasswordLog.query.filter(StudentPasswordLog.student_id.in_(ids)).delete(
        synchronize_session=False
    )

    try:
        from app.store.models.student_purchase import StudentPurchase

        StudentPurchase.query.filter(StudentPurchase.student_id.in_(ids)).delete(
            synchronize_session=False
        )
    except Exception as e:
        logger.warning("StudentPurchase cleanup skipped or partial: %s", e)
