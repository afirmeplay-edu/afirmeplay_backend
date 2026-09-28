from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid as uuid_lib

from app import db
from app.models.student import Student
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app.models.mobile_models import MobileSyncSubmission, MobileSyncBundleGeneration

from app.services.mobile.bundle_service import collect_school_scope, build_tests_questions_payload

# Paliativo temporário (Limoeiro / 9º): Q20 editada após download do pacote offline.
# Remover após a aplicação (ou quando UNTIL passar o bypass deixa de valer sozinho).
_TEST_VERSION_MISMATCH_BYPASS_IDS = frozenset(
    {
        "e99fa9a5-5f89-48f2-847d-35ab9b35838d",  # 9º ANO - 2º AVALIA LIMOEIRO
        "9bcc0486-38b4-462a-9eb1-8c63ad5a0170",  # ADAP I - 9º ANO - 2º AVALIA LIMOEIRO
    }
)
_TEST_VERSION_MISMATCH_BYPASS_UNTIL = datetime(2026, 10, 2, 3, 3, 0)  # UTC, fim do pacote T8GN

# Paliativo temporário: tablet aplica 1º regular em aluno ADAP I (mesmas 22 questões).
# Remap só se o aluno já tiver vínculo com a ADAP I correspondente. Expira no mesmo prazo.
_REGULAR_1ANO_TO_ADAP_I = {
    "a5764cc4-3464-448f-9c63-c07d68c614b9": "797664a9-7f20-4b23-9319-d4daebbdff10",  # LP
    "a7bdf340-1796-4f93-a1f2-5825394bd946": "0bef89ea-6329-42c7-9f83-7f4c0c00979e",  # MAT
}


def _test_version_mismatch_bypassed(test_id: str) -> bool:
    return (
        str(test_id) in _TEST_VERSION_MISMATCH_BYPASS_IDS
        and datetime.utcnow() < _TEST_VERSION_MISMATCH_BYPASS_UNTIL
    )


def _remap_regular_1ano_to_adap_i(
    student_id: str, test_id: str, school_id: str
) -> Optional[str]:
    if datetime.utcnow() >= _TEST_VERSION_MISMATCH_BYPASS_UNTIL:
        return None
    target = _REGULAR_1ANO_TO_ADAP_I.get(str(test_id))
    if not target:
        return None
    if validate_student_test_link(student_id, target, school_id):
        return target
    return None


def get_bundle_generation(
    school_id: str, sync_bundle_version: int
) -> Optional[MobileSyncBundleGeneration]:
    return MobileSyncBundleGeneration.query.filter_by(
        school_id=school_id,
        sync_bundle_version=sync_bundle_version,
    ).first()


def validate_student_test_link(student_id: str, test_id: str, school_id: str) -> bool:
    _, _, links, *_ = collect_school_scope(school_id)
    return (student_id, test_id) in links


def process_one_submission(
    *,
    item: Dict[str, Any],
    user_id: str,
    school_id: str,
) -> Dict[str, Any]:
    submission_id_raw = item.get("submission_id")
    try:
        submission_uuid = uuid_lib.UUID(str(submission_id_raw))
    except (ValueError, TypeError):
        return {
            "submission_id": submission_id_raw,
            "status": "error",
            "message": "submission_id UUID inválido",
        }

    device_id = item.get("device_id") or ""
    student_id = item.get("student_id")
    test_id = item.get("test_id")
    test_content_version = item.get("test_content_version")
    sync_bundle_version = item.get("sync_bundle_version")
    answers = item.get("answers") or []
    metadata = item.get("metadata") or {}

    if not student_id or not test_id:
        return {
            "submission_id": str(submission_uuid),
            "status": "error",
            "message": "student_id e test_id obrigatórios",
        }

    if sync_bundle_version is None:
        return {
            "submission_id": str(submission_uuid),
            "status": "error",
            "message": "sync_bundle_version obrigatório",
        }

    try:
        sbv = int(sync_bundle_version)
    except (TypeError, ValueError):
        return {
            "submission_id": str(submission_uuid),
            "status": "error",
            "message": "sync_bundle_version inválido",
        }

    existing = MobileSyncSubmission.query.filter_by(
        submission_id=submission_uuid
    ).first()
    if existing:
        return {
            "submission_id": str(submission_uuid),
            "status": "duplicate_ignored",
            "already_processed": True,
            "message": "submission_id já processado",
        }

    gen = get_bundle_generation(school_id, sbv)
    if not gen:
        known_versions = [
            row.sync_bundle_version
            for row in MobileSyncBundleGeneration.query.filter_by(school_id=school_id)
            .order_by(MobileSyncBundleGeneration.sync_bundle_version.asc())
            .all()
        ]
        print(
            f"[mobile/v1/sync/upload] bundle não encontrado — school_id={school_id} "
            f"sync_bundle_version={sbv!r} versões_no_banco={known_versions} "
            f"submission_id={submission_uuid} student_id={student_id} test_id={test_id}"
        )
        return {
            "submission_id": str(submission_uuid),
            "status": "error",
            "message": "sync_bundle_version não encontrado para esta escola",
        }
    if datetime.utcnow() > gen.bundle_valid_until:
        return {
            "submission_id": str(submission_uuid),
            "status": "error",
            "message": "BUNDLE_EXPIRED",
            "code": "BUNDLE_EXPIRED",
        }

    stu = Student.query.filter_by(id=student_id, school_id=school_id).first()
    if not stu:
        return {
            "submission_id": str(submission_uuid),
            "status": "error",
            "message": "aluno não encontrado nesta escola",
        }

    incoming_test_id = str(test_id)
    remapped_from: Optional[str] = None
    if not validate_student_test_link(student_id, test_id, school_id):
        remapped = _remap_regular_1ano_to_adap_i(student_id, test_id, school_id)
        if remapped:
            remapped_from = incoming_test_id
            test_id = remapped
            print(
                f"[mobile/v1/sync/upload] remap regular→ADAP I — "
                f"from={remapped_from} to={test_id} "
                f"submission_id={submission_uuid} school_id={school_id} "
                f"student_id={student_id}"
            )
        else:
            return {
                "submission_id": str(submission_uuid),
                "status": "error",
                "message": "vínculo aluno-prova inválido para esta escola",
            }

    test = Test.query.get(test_id)
    if not test:
        return {
            "submission_id": str(submission_uuid),
            "status": "error",
            "message": "prova não encontrada",
        }

    # Hash do tablet é da prova regular; após remap validar contra o test_id original.
    version_test_id = remapped_from or test_id
    version_test = Test.query.get(version_test_id) if remapped_from else test
    if remapped_from and not version_test:
        return {
            "submission_id": str(submission_uuid),
            "status": "error",
            "message": "prova não encontrada",
        }
    _, versions, _ = build_tests_questions_payload({version_test_id: version_test})
    expected = versions.get(version_test_id)
    if not expected or expected != test_content_version:
        if _test_version_mismatch_bypassed(test_id) or _test_version_mismatch_bypassed(
            version_test_id
        ):
            print(
                f"[mobile/v1/sync/upload] TEST_VERSION_MISMATCH bypass — "
                f"test_id={test_id} version_test_id={version_test_id} "
                f"submission_id={submission_uuid} "
                f"school_id={school_id} student_id={student_id} "
                f"until={_TEST_VERSION_MISMATCH_BYPASS_UNTIL.isoformat()}"
            )
        else:
            return {
                "submission_id": str(submission_uuid),
                "status": "error",
                "message": "test_content_version inválido ou desatualizado",
                "code": "TEST_VERSION_MISMATCH",
            }

    tq_ids = {tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).all()}
    for ans in answers:
        qid = ans.get("question_id")
        if not qid or qid not in tq_ids:
            return {
                "submission_id": str(submission_uuid),
                "status": "error",
                "message": f"question_id inválida ou fora da prova: {qid}",
            }

    session_id_created: Optional[str] = None
    try:
        with db.session.begin_nested():
            session_row = TestSession(
                student_id=student_id,
                test_id=test_id,
                ip_address=None,
                user_agent="mobile-sync",
            )
            session_row.status = "finalizada"
            session_row.submitted_at = datetime.utcnow()
            st_attr = _parse_ts(metadata.get("client_started_at"))
            if st_attr:
                session_row.started_at = st_attr
            db.session.add(session_row)
            db.session.flush()
            session_id_created = session_row.id

            for ans in answers:
                qid = ans.get("question_id")
                existing_answer = StudentAnswer.query.filter_by(
                    student_id=student_id,
                    test_id=test_id,
                    question_id=qid,
                ).first()

                if existing_answer:
                    sa = existing_answer
                    sa.answer = str(ans.get("answer", ""))
                else:
                    sa = StudentAnswer(
                        student_id=student_id,
                        test_id=test_id,
                        question_id=qid,
                        answer=str(ans.get("answer", "")),
                    )
                    db.session.add(sa)
                if ans.get("answered_at"):
                    parsed = _parse_ts(ans.get("answered_at"))
                    if parsed:
                        sa.answered_at = parsed
                else:
                    sa.answered_at = datetime.utcnow()

            sub_row = MobileSyncSubmission(
                submission_id=submission_uuid,
                device_id=device_id,
                user_id=user_id,
                status="processed",
            )
            db.session.add(sub_row)
    except Exception as ex:
        return {
            "submission_id": str(submission_uuid),
            "status": "error",
            "message": f"erro ao persistir: {ex}",
        }

    # Gravar sync antes do cálculo: calculate_and_save_result faz commit e, em erro, rollback
    # da sessão atual — sem este commit, o rollback apagaria sessão/respostas/sync.
    db.session.commit()

    try:
        from app.services.evaluation_result_service import EvaluationResultService

        eval_out = EvaluationResultService.calculate_and_save_result(
            str(test_id),
            str(student_id),
            str(session_id_created),
        )
        if not eval_out:
            logging.warning(
                "mobile sync: evaluation_result não gerado (test_id=%s student_id=%s session_id=%s)",
                test_id,
                student_id,
                session_id_created,
            )
    except Exception:
        logging.exception(
            "mobile sync: exceção ao calcular evaluation_result (test_id=%s student_id=%s)",
            test_id,
            student_id,
        )

    return {
        "submission_id": str(submission_uuid),
        "status": "applied",
        "session_id": session_id_created,
        "already_processed": False,
    }


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        from dateutil import parser

        return parser.isoparse(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def process_batch(
    submissions: List[Dict[str, Any]], user_id: str, school_id: str
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for item in submissions:
        try:
            results.append(process_one_submission(item=item, user_id=user_id, school_id=school_id))
        except Exception as ex:
            results.append(
                {
                    "submission_id": item.get("submission_id"),
                    "status": "error",
                    "message": str(ex),
                }
            )
    return results
