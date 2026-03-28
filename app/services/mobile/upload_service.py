from datetime import datetime
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
from app.services.mobile.device_service import register_or_touch_device


def get_bundle_generation(
    school_id: str, sync_bundle_version: int
) -> Optional[MobileSyncBundleGeneration]:
    return MobileSyncBundleGeneration.query.filter_by(
        school_id=school_id,
        sync_bundle_version=sync_bundle_version,
    ).first()


def validate_student_test_link(student_id: str, test_id: str, school_id: str) -> bool:
    _, _, links = collect_school_scope(school_id)
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

    if not validate_student_test_link(student_id, test_id, school_id):
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

    _, versions, _ = build_tests_questions_payload({test_id: test})
    expected = versions.get(test_id)
    if not expected or expected != test_content_version:
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
                sa = StudentAnswer(
                    student_id=student_id,
                    test_id=test_id,
                    question_id=ans.get("question_id"),
                    answer=str(ans.get("answer", "")),
                )
                if ans.get("answered_at"):
                    parsed = _parse_ts(ans.get("answered_at"))
                    if parsed:
                        sa.answered_at = parsed
                db.session.add(sa)

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

    register_or_touch_device(user_id, device_id)

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
