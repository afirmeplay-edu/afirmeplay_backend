from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func

from app import db
from app.evaluations.models.evaluationResult import EvaluationResult
from app.models.school import School
from app.models.student import Student


class StudentRankingService:
    """Serviço para cálculo de rankings de alunos em diferentes escopos."""

    @classmethod
    def get_rankings(
        cls,
        student_id: str,
        evaluation_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calcula ranking do aluno por turma, escola e município.

        Com ``evaluation_id``, o universo de comparação usa ``school_id_snapshot`` /
        ``class_id_snapshot`` / ``grade_id_snapshot`` do resultado daquela avaliação,
        para não mudar após transferência de escola.
        """
        student = Student.query.get(student_id)
        if not student:
            return {}

        rankings: Dict[str, Any] = {}

        focal_er = None
        if evaluation_id:
            focal_er = EvaluationResult.query.filter_by(
                test_id=evaluation_id, student_id=student_id
            ).first()

        # Ranking por escola (mesma escola e mesma série)
        if evaluation_id and focal_er and focal_er.school_id_snapshot:
            q = db.session.query(EvaluationResult.student_id).filter(
                EvaluationResult.test_id == evaluation_id,
                EvaluationResult.school_id_snapshot == str(focal_er.school_id_snapshot),
            )
            if focal_er.grade_id_snapshot is not None:
                q = q.filter(EvaluationResult.grade_id_snapshot == focal_er.grade_id_snapshot)
            school_student_ids = [str(r[0]) for r in q.distinct().all() if r[0]]
            rankings["school"] = cls._build_ranking_for_scope(
                student_id=student_id,
                scope_student_ids=school_student_ids,
                evaluation_id=evaluation_id,
                limit=limit
            )
        elif student.school_id:
            school_query = Student.query.filter_by(school_id=student.school_id)
            if student.grade_id is not None:
                school_query = school_query.filter(Student.grade_id == student.grade_id)
            school_student_ids = [s.id for s in school_query.all()]
            rankings["school"] = cls._build_ranking_for_scope(
                student_id=student_id,
                scope_student_ids=school_student_ids,
                evaluation_id=evaluation_id,
                limit=limit
            )

        # Ranking por turma
        if evaluation_id and focal_er and focal_er.class_id_snapshot:
            peer_ids = (
                db.session.query(EvaluationResult.student_id)
                .filter(
                    EvaluationResult.test_id == evaluation_id,
                    EvaluationResult.class_id_snapshot == focal_er.class_id_snapshot,
                )
                .distinct()
                .all()
            )
            class_student_ids = [str(r[0]) for r in peer_ids if r[0]]
            rankings["class"] = cls._build_ranking_for_scope(
                student_id=student_id,
                scope_student_ids=class_student_ids,
                evaluation_id=evaluation_id,
                limit=limit
            )
        elif student.class_id:
            class_query = Student.query.filter_by(class_id=student.class_id)
            if student.grade_id is not None:
                class_query = class_query.filter(Student.grade_id == student.grade_id)
            class_student_ids = [s.id for s in class_query.all()]
            rankings["class"] = cls._build_ranking_for_scope(
                student_id=student_id,
                scope_student_ids=class_student_ids,
                evaluation_id=evaluation_id,
                limit=limit
            )

        # Ranking por município
        city_id = None
        if evaluation_id and focal_er and focal_er.school_id_snapshot:
            snap_school = School.query.get(str(focal_er.school_id_snapshot))
            if snap_school:
                city_id = snap_school.city_id
        elif student.school_id:
            school = School.query.get(student.school_id)
            if school:
                city_id = school.city_id

        if city_id:
            if evaluation_id:
                from app.evaluations.services.evaluation_result_snapshot import municipal_evaluation_results_query

                muni_rows = municipal_evaluation_results_query(str(city_id), str(evaluation_id)).all()
                if focal_er and focal_er.grade_id_snapshot is not None:
                    municipality_student_ids = list(
                        {r.student_id for r in muni_rows if r.grade_id_snapshot == focal_er.grade_id_snapshot}
                    )
                else:
                    municipality_student_ids = list({r.student_id for r in muni_rows})
            else:
                municipality_school_ids = [
                    s.id for s in School.query.filter_by(city_id=city_id).all()
                ]
                municipality_query = Student.query.filter(
                    Student.school_id.in_(municipality_school_ids)
                )
                if student.grade_id is not None:
                    municipality_query = municipality_query.filter(Student.grade_id == student.grade_id)
                municipality_student_ids = [s.id for s in municipality_query.all()]

            rankings["municipality"] = cls._build_ranking_for_scope(
                student_id=student_id,
                scope_student_ids=municipality_student_ids,
                evaluation_id=evaluation_id,
                limit=limit
            )

        return rankings

    @classmethod
    def _build_ranking_for_scope(
        cls,
        student_id: str,
        scope_student_ids: List[str],
        evaluation_id: Optional[str],
        limit: Optional[int]
    ) -> Dict[str, Any]:
        if not scope_student_ids:
            return {
                "position": None,
                "total_students": 0,
                "current_student": None,
                "ranking": []
            }

        results = cls._query_results(scope_student_ids, evaluation_id)
        ranking_list: List[Dict[str, Any]] = []
        current_student_entry: Optional[Dict[str, Any]] = None

        for position, result in enumerate(results, start=1):
            entry = {
                "position": position,
                "student_id": result.student_id,
                "student_name": result.student_name,
                "proficiency": float(result.score) if result.score is not None else None
            }
            ranking_list.append(entry)
            if result.student_id == student_id:
                current_student_entry = entry

        truncated_ranking = ranking_list if limit is None else ranking_list[:limit]

        return {
            "position": current_student_entry["position"] if current_student_entry else None,
            "total_students": len(ranking_list),
            "current_student": current_student_entry,
            "ranking": truncated_ranking
        }

    @staticmethod
    def _query_results(
        scope_student_ids: List[str],
        evaluation_id: Optional[str]
    ):
        query = db.session.query(
            EvaluationResult.student_id.label("student_id"),
            Student.name.label("student_name")
        ).join(
            Student, EvaluationResult.student_id == Student.id
        ).filter(
            EvaluationResult.student_id.in_(scope_student_ids)
        )

        if evaluation_id:
            query = query.filter(
                EvaluationResult.test_id == evaluation_id
            ).add_columns(
                EvaluationResult.proficiency.label("score")
            )
        else:
            query = query.add_columns(
                func.avg(EvaluationResult.proficiency).label("score")
            ).group_by(
                EvaluationResult.student_id,
                Student.name
            )

        return query.order_by(desc("score")).all()
