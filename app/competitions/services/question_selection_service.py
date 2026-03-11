# -*- coding: utf-8 -*-
"""
Serviço de seleção/aleatorização de questões para competições.

Responsabilidades:
- Converter question_rules em filtros de banco de questões.
- Montar a query SQLAlchemy para Question.
- Selecionar (sortear) as questões de acordo com a estratégia (uniforme nesta etapa).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import random

from sqlalchemy.orm import Query

from app import db
from app.competitions.constants import STAGE_NAMES_BY_LEVEL
from app.models.educationStage import EducationStage
from app.models.question import Question

from app.competitions.exceptions import ValidationError
from .question_rules_validator import validate_question_rules


class QuestionSelectionService:
    """Service responsável por selecionar questões para uma Competition."""

    @staticmethod
    def build_query(subject_id: str, level: Optional[int], rules: Optional[Dict[str, Any]]) -> Query:
        """
        Monta a query base para buscar questões elegíveis.

        Filtros considerados:
        - subject_id (obrigatório)
        - etapa de ensino derivada de level (STAGE_NAMES_BY_LEVEL)
        - grade_filter (grade_ids / min_grade_level / max_grade_level)
        - difficulty_filter.levels
        - tags_filter (se existir campo correspondente no modelo Question)
        - campos legados: grade_ids, difficulty_level
        """
        rules = rules or {}
        query = Question.query.filter_by(subject_id=subject_id)

        # Filtro por etapa de ensino (a partir do level da competição)
        if level is not None:
            stage_names = STAGE_NAMES_BY_LEVEL.get(level)
            if stage_names:
                stage_ids = (
                    db.session.query(EducationStage.id)
                    .filter(EducationStage.name.in_(stage_names))
                    .all()
                )
                stage_ids = [s[0] for s in stage_ids]
                if stage_ids:
                    query = query.filter(Question.education_stage_id.in_(stage_ids))

        # ---- Filtros de série/ano ----
        grade_filter = rules.get("grade_filter") or {}
        grade_ids = None
        min_grade = None
        max_grade = None

        if isinstance(grade_filter, dict):
            grade_ids = grade_filter.get("grade_ids")
            min_grade = grade_filter.get("min_grade_level")
            max_grade = grade_filter.get("max_grade_level")

        # Compatibilidade: grade_ids no nível raiz
        if grade_ids is None and "grade_ids" in rules:
            grade_ids = rules.get("grade_ids")

        if grade_ids:
            query = query.filter(Question.grade_level.in_(grade_ids))
        else:
            # Range de níveis (se grade_ids não fornecido)
            conditions = []
            if min_grade is not None:
                conditions.append(Question.grade_level >= int(min_grade))
            if max_grade is not None:
                conditions.append(Question.grade_level <= int(max_grade))
            for cond in conditions:
                query = query.filter(cond)

        # ---- Filtros de dificuldade ----
        difficulty_filter = rules.get("difficulty_filter") or {}
        levels = None
        if isinstance(difficulty_filter, dict):
            levels = difficulty_filter.get("levels")

        # Compatibilidade: difficulty_level no nível raiz
        if not levels and rules.get("difficulty_level"):
            levels = [rules["difficulty_level"]]

        if levels:
            query = query.filter(Question.difficulty_level.in_(levels))

        # ---- Filtro por tags (opcional, se existir no modelo) ----
        tags = rules.get("tags_filter")
        # Aqui assumimos que, se existir, o campo em Question se chama "tags"
        # e é do tipo ARRAY ou JSON contendo strings. Caso contrário, este bloco
        # pode ser ajustado futuramente.
        if tags:
            # Filtro simplificado: pelo menos uma tag em comum (dependendo do tipo no modelo real)
            try:
                query = query.filter(Question.tags.overlap(tags))  # type: ignore[attr-defined]
            except AttributeError:
                # Campo tags não existe; ignorar silenciosamente
                pass

        return query

    @staticmethod
    def select_questions(
        subject_id: str,
        level: Optional[int],
        rules: Optional[Dict[str, Any]],
    ) -> List[Question]:
        """
        Retorna lista de Question selecionadas de forma aleatória segundo as regras.

        - Valida question_rules antes de usar.
        - Aplica estratégia 'uniform' (amostragem simples sem reposição).
        """
        rules = rules or {}
        validate_question_rules(rules)

        num_questions = rules.get("num_questions", 10)
        try:
            num_questions = int(num_questions)
        except (TypeError, ValueError):
            raise ValidationError("question_rules.num_questions deve ser um inteiro") from None
        if num_questions < 1:
            raise ValidationError("question_rules.num_questions deve ser >= 1")

        query = QuestionSelectionService.build_query(subject_id, level, rules)
        available_questions: List[Question] = query.all()

        # Fallback: outras disciplinas podem usar valores de dificuldade diferentes; tentar sem filtro de dificuldade
        if len(available_questions) < num_questions and (rules.get("difficulty_filter") or rules.get("difficulty_level")):
            rules_without_difficulty = {k: v for k, v in rules.items() if k not in ("difficulty_filter", "difficulty_level")}
            query_fallback = QuestionSelectionService.build_query(subject_id, level, rules_without_difficulty)
            fallback_questions = query_fallback.all()
            if len(fallback_questions) >= num_questions:
                available_questions = fallback_questions
            del rules_without_difficulty, query_fallback, fallback_questions

        if len(available_questions) < num_questions:
            raise ValidationError(
                f"Questões insuficientes para o nível e disciplina. "
                f"Disponíveis: {len(available_questions)}, Necessárias: {num_questions}"
            )

        # Estratégia: uniform
        random_seed = rules.get("random_seed")
        rng = random.Random(random_seed) if random_seed is not None else random

        # allow_repeated_questions = False => sample sem repetição (padrão). Aceita alias allow_repeat.
        allow_repeated = bool(
            rules.get("allow_repeated_questions", rules.get("allow_repeat", False))
        )
        if allow_repeated:
            # Amostragem com reposição
            return [rng.choice(available_questions) for _ in range(num_questions)]
        else:
            return rng.sample(available_questions, num_questions)

