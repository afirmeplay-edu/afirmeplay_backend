"""
Serviço de cálculos de avaliações - Proficiência, Nota e Classificação
Implementa as fórmulas específicas conforme os requisitos do sistema
"""

import logging
from typing import Dict, Optional, Tuple
from enum import Enum


class CourseLevel(Enum):
    """Níveis de curso para diferenciação de cálculos"""
    EDUCACAO_INFANTIL = "educacao_infantil"
    ANOS_INICIAIS = "anos_iniciais" 
    EDUCACAO_ESPECIAL = "educacao_especial"
    EJA = "eja"
    ANOS_FINAIS = "anos_finais"
    ENSINO_MEDIO = "ensino_medio"


class Subject(Enum):
    """Disciplinas com tratamento diferenciado"""
    MATEMATICA = "matematica"
    OUTRAS = "outras"


class Classification(Enum):
    """Classificações possíveis"""
    ABAIXO_BASICO = "Abaixo do Básico"
    BASICO = "Básico"
    ADEQUADO = "Adequado"
    AVANCADO = "Avançado"


class EvaluationCalculator:
    """
    Calculadora central para avaliações educacionais.
    Implementa todas as fórmulas de proficiência, nota e classificação.
    """
    
    # Configurações de proficiência máxima
    MAX_PROFICIENCY_CONFIG = {
        # Educação Infantil, Anos Iniciais, Educação Especial, EJA - Outras matérias
        (CourseLevel.EDUCACAO_INFANTIL, Subject.OUTRAS): 350,
        (CourseLevel.ANOS_INICIAIS, Subject.OUTRAS): 350,
        (CourseLevel.EDUCACAO_ESPECIAL, Subject.OUTRAS): 350,
        (CourseLevel.EJA, Subject.OUTRAS): 350,
        
        # Educação Infantil, Anos Iniciais, Educação Especial, EJA - Matemática
        (CourseLevel.EDUCACAO_INFANTIL, Subject.MATEMATICA): 375,
        (CourseLevel.ANOS_INICIAIS, Subject.MATEMATICA): 375,
        (CourseLevel.EDUCACAO_ESPECIAL, Subject.MATEMATICA): 375,
        (CourseLevel.EJA, Subject.MATEMATICA): 375,
        
        # Anos Finais e Ensino Médio - Outras matérias
        (CourseLevel.ANOS_FINAIS, Subject.OUTRAS): 400,
        (CourseLevel.ENSINO_MEDIO, Subject.OUTRAS): 400,
        
        # Anos Finais e Ensino Médio - Matemática
        (CourseLevel.ANOS_FINAIS, Subject.MATEMATICA): 425,
        (CourseLevel.ENSINO_MEDIO, Subject.MATEMATICA): 425,
    }
    
    # Configurações para cálculo de nota
    GRADE_CALCULATION_CONFIG = {
        # Educação Infantil, Anos Iniciais, Educação Especial, EJA - Outras matérias
        (CourseLevel.EDUCACAO_INFANTIL, Subject.OUTRAS): {"base": 49, "divisor": 275},
        (CourseLevel.ANOS_INICIAIS, Subject.OUTRAS): {"base": 49, "divisor": 275},
        (CourseLevel.EDUCACAO_ESPECIAL, Subject.OUTRAS): {"base": 49, "divisor": 275},
        (CourseLevel.EJA, Subject.OUTRAS): {"base": 49, "divisor": 275},
        
        # Educação Infantil, Anos Iniciais, Educação Especial, EJA - Matemática
        (CourseLevel.EDUCACAO_INFANTIL, Subject.MATEMATICA): {"base": 60, "divisor": 262},
        (CourseLevel.ANOS_INICIAIS, Subject.MATEMATICA): {"base": 60, "divisor": 262},
        (CourseLevel.EDUCACAO_ESPECIAL, Subject.MATEMATICA): {"base": 60, "divisor": 262},
        (CourseLevel.EJA, Subject.MATEMATICA): {"base": 60, "divisor": 262},
        
        # Anos Finais e Ensino Médio - Todas as matérias
        (CourseLevel.ANOS_FINAIS, Subject.OUTRAS): {"base": 100, "divisor": 300},
        (CourseLevel.ENSINO_MEDIO, Subject.OUTRAS): {"base": 100, "divisor": 300},
        (CourseLevel.ANOS_FINAIS, Subject.MATEMATICA): {"base": 100, "divisor": 300},
        (CourseLevel.ENSINO_MEDIO, Subject.MATEMATICA): {"base": 100, "divisor": 300},
    }
    
    # Configurações de classificação por faixas de proficiência
    CLASSIFICATION_CONFIG = {
        # Educação Infantil, Anos Iniciais, Educação Especial, EJA - Outras matérias
        (CourseLevel.EDUCACAO_INFANTIL, Subject.OUTRAS): [
            (0, 149, Classification.ABAIXO_BASICO),
            (150, 199, Classification.BASICO),
            (200, 249, Classification.ADEQUADO),
            (250, 350, Classification.AVANCADO)
        ],
        (CourseLevel.ANOS_INICIAIS, Subject.OUTRAS): [
            (0, 149, Classification.ABAIXO_BASICO),
            (150, 199, Classification.BASICO),
            (200, 249, Classification.ADEQUADO),
            (250, 350, Classification.AVANCADO)
        ],
        (CourseLevel.EDUCACAO_ESPECIAL, Subject.OUTRAS): [
            (0, 149, Classification.ABAIXO_BASICO),
            (150, 199, Classification.BASICO),
            (200, 249, Classification.ADEQUADO),
            (250, 350, Classification.AVANCADO)
        ],
        (CourseLevel.EJA, Subject.OUTRAS): [
            (0, 149, Classification.ABAIXO_BASICO),
            (150, 199, Classification.BASICO),
            (200, 249, Classification.ADEQUADO),
            (250, 350, Classification.AVANCADO)
        ],
        
        # Educação Infantil, Anos Iniciais, Educação Especial, EJA - Matemática
        (CourseLevel.EDUCACAO_INFANTIL, Subject.MATEMATICA): [
            (0, 174, Classification.ABAIXO_BASICO),
            (175, 224, Classification.BASICO),
            (225, 274, Classification.ADEQUADO),
            (275, 375, Classification.AVANCADO)
        ],
        (CourseLevel.ANOS_INICIAIS, Subject.MATEMATICA): [
            (0, 174, Classification.ABAIXO_BASICO),
            (175, 224, Classification.BASICO),
            (225, 274, Classification.ADEQUADO),
            (275, 375, Classification.AVANCADO)
        ],
        (CourseLevel.EDUCACAO_ESPECIAL, Subject.MATEMATICA): [
            (0, 174, Classification.ABAIXO_BASICO),
            (175, 224, Classification.BASICO),
            (225, 274, Classification.ADEQUADO),
            (275, 375, Classification.AVANCADO)
        ],
        (CourseLevel.EJA, Subject.MATEMATICA): [
            (0, 174, Classification.ABAIXO_BASICO),
            (175, 224, Classification.BASICO),
            (225, 274, Classification.ADEQUADO),
            (275, 375, Classification.AVANCADO)
        ],
        
        # Anos Finais e Ensino Médio - Outras matérias
        (CourseLevel.ANOS_FINAIS, Subject.OUTRAS): [
            (0, 199, Classification.ABAIXO_BASICO),
            (200, 274.99, Classification.BASICO),
            (275, 324.99, Classification.ADEQUADO),
            (325, 400, Classification.AVANCADO)
        ],
        (CourseLevel.ENSINO_MEDIO, Subject.OUTRAS): [
            (0, 199, Classification.ABAIXO_BASICO),
            (200, 274.99, Classification.BASICO),
            (275, 324.99, Classification.ADEQUADO),
            (325, 400, Classification.AVANCADO)
        ],
        
        # Anos Finais e Ensino Médio - Matemática
        (CourseLevel.ANOS_FINAIS, Subject.MATEMATICA): [
            (0, 224.99, Classification.ABAIXO_BASICO),
            (225, 299.99, Classification.BASICO),
            (300, 349.99, Classification.ADEQUADO),
            (350, 425, Classification.AVANCADO)
        ],
        (CourseLevel.ENSINO_MEDIO, Subject.MATEMATICA): [
            (0, 224.99, Classification.ABAIXO_BASICO),
            (225, 299.99, Classification.BASICO),
            (300, 349.99, Classification.ADEQUADO),
            (350, 425, Classification.AVANCADO)
        ],
    }

    @classmethod
    def _determine_course_level(cls, course_name: str) -> CourseLevel:
        """Determina o nível do curso baseado no nome"""
        course_lower = course_name.lower()
        
        if "infantil" in course_lower:
            return CourseLevel.EDUCACAO_INFANTIL
        elif "iniciais" in course_lower or "fundamental" in course_lower and "i" in course_lower:
            return CourseLevel.ANOS_INICIAIS
        elif "especial" in course_lower:
            return CourseLevel.EDUCACAO_ESPECIAL
        elif "eja" in course_lower:
            return CourseLevel.EJA
        elif "finais" in course_lower or "fundamental" in course_lower and "ii" in course_lower:
            return CourseLevel.ANOS_FINAIS
        elif "médio" in course_lower or "medio" in course_lower:
            return CourseLevel.ENSINO_MEDIO
        else:
            # Padrão para casos não identificados
            logging.warning(f"Curso não identificado: {course_name}. Usando Anos Iniciais como padrão.")
            return CourseLevel.ANOS_INICIAIS

    @classmethod
    def _determine_subject_type(cls, subject_name: str) -> Subject:
        """Determina se a disciplina é Matemática ou outras"""
        subject_lower = subject_name.lower()
        
        if "matemática" in subject_lower or "matematica" in subject_lower:
            return Subject.MATEMATICA
        else:
            return Subject.OUTRAS

    @classmethod
    def calculate_proficiency(cls, correct_answers: int, total_questions: int, 
                            course_name: str, subject_name: str) -> float:
        """
        Calcula a proficiência baseada na fórmula:
        Proficiência = (Acertos / Total de Questões) × Proficiência Máxima
        
        Args:
            correct_answers: Número de acertos
            total_questions: Total de questões
            course_name: Nome do curso
            subject_name: Nome da disciplina
            
        Returns:
            Proficiência calculada
        """
        if total_questions == 0:
            return 0.0
            
        course_level = cls._determine_course_level(course_name)
        subject_type = cls._determine_subject_type(subject_name)
        
        max_proficiency = cls.MAX_PROFICIENCY_CONFIG.get(
            (course_level, subject_type), 350  # Valor padrão
        )
        
        accuracy_rate = correct_answers / total_questions
        proficiency = accuracy_rate * max_proficiency
        
        return round(proficiency, 2)

    @classmethod
    def calculate_grade(cls, proficiency: float, course_name: str, subject_name: str) -> float:
        """
        Calcula a nota baseada na proficiência usando fórmulas específicas
        
        Args:
            proficiency: Proficiência calculada
            course_name: Nome do curso
            subject_name: Nome da disciplina
            
        Returns:
            Nota calculada (0-10)
        """
        course_level = cls._determine_course_level(course_name)
        subject_type = cls._determine_subject_type(subject_name)
        
        config = cls.GRADE_CALCULATION_CONFIG.get(
            (course_level, subject_type),
            {"base": 49, "divisor": 275}  # Valor padrão
        )
        
        # Fórmula: (Proficiência - base) / divisor × 10
        grade = ((proficiency - config["base"]) / config["divisor"]) * 10
        
        # Limitar entre 0 e 10
        grade = max(0.0, min(10.0, grade))
        
        return round(grade, 2)

    @classmethod
    def determine_classification(cls, proficiency: float, course_name: str, subject_name: str) -> str:
        """
        Determina a classificação baseada na proficiência
        
        Args:
            proficiency: Proficiência calculada
            course_name: Nome do curso
            subject_name: Nome da disciplina
            
        Returns:
            Classificação (Abaixo do Básico, Básico, Adequado, Avançado)
        """
        course_level = cls._determine_course_level(course_name)
        subject_type = cls._determine_subject_type(subject_name)
        
        ranges = cls.CLASSIFICATION_CONFIG.get(
            (course_level, subject_type),
            # Padrão para casos não identificados
            [
                (0, 149, Classification.ABAIXO_BASICO),
                (150, 199, Classification.BASICO),
                (200, 249, Classification.ADEQUADO),
                (250, 350, Classification.AVANCADO)
            ]
        )
        
        for min_val, max_val, classification in ranges:
            if min_val <= proficiency <= max_val:
                return classification.value
                
        # Se não encontrar classificação, retorna o menor nível
        return Classification.ABAIXO_BASICO.value

    @classmethod
    def calculate_complete_evaluation(cls, correct_answers: int, total_questions: int,
                                    course_name: str, subject_name: str) -> Dict:
        """
        Calcula proficiência, nota e classificação de uma vez
        
        Args:
            correct_answers: Número de acertos
            total_questions: Total de questões
            course_name: Nome do curso
            subject_name: Nome da disciplina
            
        Returns:
            Dicionário com proficiência, nota e classificação
        """
        proficiency = cls.calculate_proficiency(correct_answers, total_questions, course_name, subject_name)
        grade = cls.calculate_grade(proficiency, course_name, subject_name)
        classification = cls.determine_classification(proficiency, course_name, subject_name)
        
        return {
            "proficiency": proficiency,
            "grade": grade,
            "classification": classification,
            "correct_answers": correct_answers,
            "total_questions": total_questions,
            "accuracy_rate": round((correct_answers / total_questions) * 100, 2) if total_questions > 0 else 0.0
        } 