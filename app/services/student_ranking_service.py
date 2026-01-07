from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func

from app import db
from app.models.evaluationResult import EvaluationResult
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

        Args:
            student_id: ID do aluno na tabela Student.
            evaluation_id: ID da avaliação. Quando informado, calcula ranking específico
                daquela avaliação; caso contrário, utiliza a média geral.
            limit: Limite opcional de entradas no ranking (top N). Se None, retorna todos.

        Returns:
            Dicionário com rankings por escopo. Cada ranking contém posição do aluno,
            total de estudantes, dados do aluno atual e lista completa (ou limitada) de posições.
        """
        student = Student.query.get(student_id)
        if not student:
            return {}

        rankings: Dict[str, Any] = {}

        # Ranking por escola
        if student.school_id:
            school_student_ids = [
                s.id for s in Student.query.filter_by(school_id=student.school_id).all()
            ]
            rankings["school"] = cls._build_ranking_for_scope(
                student_id=student_id,
                scope_student_ids=school_student_ids,
                evaluation_id=evaluation_id,
                limit=limit
            )

        # Ranking por turma
        if student.class_id:
            class_student_ids = [
                s.id for s in Student.query.filter_by(class_id=student.class_id).all()
            ]
            rankings["class"] = cls._build_ranking_for_scope(
                student_id=student_id,
                scope_student_ids=class_student_ids,
                evaluation_id=evaluation_id,
                limit=limit
            )

        # Ranking por município
        school = School.query.get(student.school_id) if student.school_id else None
        if school and school.city_id:
            municipality_school_ids = [
                s.id for s in School.query.filter_by(city_id=school.city_id).all()
            ]
            municipality_student_ids = [
                s.id for s in Student.query.filter(
                    Student.school_id.in_(municipality_school_ids)
                ).all()
            ]
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

