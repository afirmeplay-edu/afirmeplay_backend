from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.models.user import User
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.manager import Manager
from app.models.city import City
from app.models.user_settings import UserSettings
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

from app.services.deletion.base_deletion_service import BaseDeletionService
from app.services.deletion.deletion_exceptions import EntityNotFoundError, PermissionDeniedError
from app.services.deletion.deletion_result import DeletionResult


class UserDeletionService(BaseDeletionService):
    entity = "user"

    def __init__(self, session, logger: logging.Logger | None = None):
        super().__init__(session=session, logger=logger)

    def execute(self, *, user_id: str, current_user: dict | None = None) -> DeletionResult:
        """
        Remove um usuário em fases:
        - Fase tenant: remover Student + dependências no schema da cidade e tabelas tenant que referenciam public.users
        - Commit tenant
        - Fase public: remover settings + user + dados public (manager/quick_links)
        - Commit final

        Importante:
        - bulk delete sempre que possível
        - se fase public falhar, não desfazer fase tenant
        """
        self.log("step 1 validating user", user_id=user_id)

        if not current_user:
            raise EntityNotFoundError("Usuário atual não encontrado")
        if current_user.get("id") == user_id:
            raise PermissionDeniedError("Não é possível deletar o próprio usuário")

        user_to_delete = User.query.get(user_id)
        if not user_to_delete:
            raise EntityNotFoundError("Usuário não encontrado")

        user_city_id = getattr(user_to_delete, "city_id", None)

        # Restrições para tecadm (deve apagar apenas da própria cidade)
        if current_user.get("role") == "tecadm":
            current_city_id = current_user.get("tenant_id") or current_user.get("city_id")
            if user_city_id != current_city_id:
                raise PermissionDeniedError("Sem permissão para deletar usuário de outra cidade")

        deleted: dict[str, object] = {}
        warnings: list[str] = []

        def _set_search_path_for_user():
            if user_city_id:
                set_search_path(city_id_to_schema_name(user_city_id))
            else:
                set_search_path("public")

        # ----------------------------
        # Fase tenant (schema da cidade)
        # ----------------------------
        self.log("step 2 resolving tenant schema", city_id=user_city_id or "public")
        _set_search_path_for_user()

        # Mesmo sendo aluno, garantimos que não existe Teacher (segurança)
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        teacher_id = teacher.id if teacher else None
        all_cities = City.query.all() if teacher_id else []

        if teacher_id:
            self.log("step 3 deleting teacher relations across schemas", teacher_id=teacher_id)
            from app.models.teacherClass import TeacherClass
            from app.models.schoolTeacher import SchoolTeacher

            total_teacher_class = 0
            total_school_teacher = 0

            for city in all_cities:
                set_search_path(city_id_to_schema_name(city.id))
                total_teacher_class += TeacherClass.query.filter_by(teacher_id=teacher_id).delete(
                    synchronize_session=False
                )
                total_school_teacher += SchoolTeacher.query.filter_by(teacher_id=teacher_id).delete(
                    synchronize_session=False
                )

            deleted["teacher_class_links"] = total_teacher_class
            deleted["school_teacher_links"] = total_school_teacher
            _set_search_path_for_user()

        self.log("step 4 deleting student and tenant dependencies")

        from app.models.physicalTestForm import PhysicalTestForm
        from app.models.physicalTestAnswer import PhysicalTestAnswer

        student_ids_to_delete = [
            row[0] for row in self.session.query(Student.id).filter(Student.user_id == user_id).all()
        ]
        deleted["student_ids"] = list(student_ids_to_delete)

        if student_ids_to_delete:
            physical_forms_subq = (
                PhysicalTestForm.query.with_entities(PhysicalTestForm.id)
                .filter(PhysicalTestForm.student_id.in_(student_ids_to_delete))
                .subquery()
            )

            PhysicalTestAnswer.query.filter(
                PhysicalTestAnswer.physical_form_id.in_(physical_forms_subq)
            ).delete(synchronize_session=False)
            PhysicalTestForm.query.filter(
                PhysicalTestForm.student_id.in_(student_ids_to_delete)
            ).delete(synchronize_session=False)

            from app.models.studentAnswer import StudentAnswer
            from app.models.testSession import TestSession
            from app.models.evaluationResult import EvaluationResult
            from app.models.answerSheetResult import AnswerSheetResult
            from app.models.studentTestOlimpics import StudentTestOlimpics
            from app.models.formCoordinates import FormCoordinates
            from app.models.studentPasswordLog import StudentPasswordLog

            StudentAnswer.query.filter(StudentAnswer.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )

            from app.balance.models.student_coins import StudentCoins
            from app.balance.models.coin_transaction import CoinTransaction
            from app.competitions.models.competition_enrollment import CompetitionEnrollment
            from app.competitions.models.competition_result import CompetitionResult
            from app.competitions.models.competition_reward import CompetitionReward
            from app.competitions.models.competition_ranking_payout import CompetitionRankingPayout
            from app.certification.models.certificate import Certificate

            CompetitionEnrollment.query.filter(
                CompetitionEnrollment.student_id.in_(student_ids_to_delete)
            ).delete(synchronize_session=False)
            CompetitionReward.query.filter(
                CompetitionReward.student_id.in_(student_ids_to_delete)
            ).delete(synchronize_session=False)
            CompetitionRankingPayout.query.filter(
                CompetitionRankingPayout.student_id.in_(student_ids_to_delete)
            ).delete(synchronize_session=False)
            CompetitionResult.query.filter(
                CompetitionResult.student_id.in_(student_ids_to_delete)
            ).delete(synchronize_session=False)

            CoinTransaction.query.filter(CoinTransaction.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )
            StudentCoins.query.filter(StudentCoins.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )
            Certificate.query.filter(Certificate.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )

            TestSession.query.filter(TestSession.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )
            EvaluationResult.query.filter(EvaluationResult.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )
            AnswerSheetResult.query.filter(AnswerSheetResult.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )
            StudentTestOlimpics.query.filter(StudentTestOlimpics.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )
            FormCoordinates.query.filter(FormCoordinates.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )

            # FK: student_password_log.student_id -> student.id
            StudentPasswordLog.query.filter(StudentPasswordLog.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )

            from app.store.models.student_purchase import StudentPurchase

            StudentPurchase.query.filter(StudentPurchase.student_id.in_(student_ids_to_delete)).delete(
                synchronize_session=False
            )

            # Apagar Student por último
            Student.query.filter(Student.id.in_(student_ids_to_delete)).delete(synchronize_session=False)
            deleted["student"] = True
        else:
            deleted["student"] = False

        # Tabelas tenant com FK NOT NULL para public.users.id
        if user_city_id:
            self.log("step 5 deleting tenant rows referencing public.users", user_id=user_id)
            _set_search_path_for_user()
            from app.models.game import Game, GameClass
            from app.models.calendar_event_user import CalendarEventUser
            from app.models.mobile_models import MobileDevice, MobileSyncSubmission

            game_ids_subq = self.session.query(Game.id).filter(Game.userId == user_id).subquery()
            deleted_game_classes = GameClass.query.filter(GameClass.game_id.in_(game_ids_subq)).delete(
                synchronize_session=False
            )
            deleted_games = Game.query.filter(Game.userId == user_id).delete(synchronize_session=False)
            deleted_calendar = CalendarEventUser.query.filter(CalendarEventUser.user_id == user_id).delete(
                synchronize_session=False
            )
            deleted_sync = MobileSyncSubmission.query.filter(MobileSyncSubmission.user_id == user_id).delete(
                synchronize_session=False
            )
            deleted_devices = MobileDevice.query.filter(MobileDevice.user_id == user_id).delete(
                synchronize_session=False
            )

            deleted["game_classes"] = deleted_game_classes
            deleted["games"] = deleted_games
            deleted["calendar_event_users"] = deleted_calendar
            deleted["mobile_sync_submission"] = deleted_sync
            deleted["mobile_device"] = deleted_devices

        self.log("step 6 commit tenant phase")
        self.commit("tenant")

        # ----------------------------
        # Fase public (não desfaz tenant)
        # ----------------------------
        try:
            self.log("step 7 deleting public dependencies (manager/quick_links/settings)")

            deleted_manager = Manager.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            deleted_quick_links = 0
            from app.models.userQuickLinks import UserQuickLinks

            deleted_quick_links = UserQuickLinks.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            deleted_settings = UserSettings.query.filter_by(user_id=user_id).delete(synchronize_session=False)

            deleted["manager"] = deleted_manager
            deleted["user_quick_links"] = deleted_quick_links
            deleted["user_settings"] = deleted_settings

            self.log("step 8 deleting public.users")
            User.query.filter_by(id=user_id).delete(synchronize_session=False)
            deleted["user"] = True

            self.log("step 9 commit final phase")
            self.commit("final")
        except SQLAlchemyError as e:
            # Não desfazer fase tenant
            self.session.rollback()
            self.log_error("public phase failed after tenant commit", error=str(e))
            raise

        # Best-effort: logs antigos por user_id (pode existir student_id NULL)
        try:
            if user_city_id:
                _set_search_path_for_user()
                from app.models.studentPasswordLog import StudentPasswordLog

                cleaned = (
                    StudentPasswordLog.query.filter(StudentPasswordLog.user_id == user_id).delete(
                        synchronize_session=False
                    )
                )
                self.session.commit()
                if cleaned:
                    deleted["student_password_log_by_user"] = cleaned
        except Exception as cleanup_err:
            try:
                self.session.rollback()
            except Exception:
                pass
            warnings.append(f"cleanup student_password_log por user_id falhou: {cleanup_err}")

        return DeletionResult(
            success=True,
            entity=self.entity,
            id=user_id,
            deleted=deleted,
            warnings=warnings,
        )

