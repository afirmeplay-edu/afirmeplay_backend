"""
Serviço de agregações para estatísticas de avaliações
Gera dados consolidados para gráficos e relatórios
"""

from typing import Dict, List, Optional, Any
from sqlalchemy import func, case, and_, text
from collections import defaultdict
import logging

from app.models.test import Test
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.subject import Subject
from app.models.grades import Grade
from app.models.school import School
from app.models.studentClass import Class
from app.services.evaluation_calculator import EvaluationCalculator
from app import db


class EvaluationAggregator:
    """
    Serviço especializado em agregações e estatísticas de avaliações.
    Gera dados consolidados para dashboards e relatórios.
    """

    @classmethod
    def calculate_evaluation_statistics(cls, test_id: str) -> Dict[str, Any]:
        """
        Calcula estatísticas completas de uma avaliação
        
        Args:
            test_id: ID da avaliação
            
        Returns:
            Estatísticas da avaliação
        """
        
        # Buscar avaliação
        test = Test.query.get(test_id)
        if not test:
            return {}
            
        # Buscar respostas dos alunos com join na tabela Question
        from app.models.question import Question
        
        student_answers = db.session.query(
            StudentAnswer.student_id,
            func.count(StudentAnswer.id).label('total_answered'),
            func.sum(
                case(
                    (StudentAnswer.answer == Question.correct_answer, 1),
                    else_=0
                )
            ).label('correct_answers')
        ).join(
            Question, StudentAnswer.question_id == Question.id
        ).filter(
            StudentAnswer.test_id == test_id
        ).group_by(StudentAnswer.student_id).all()
        
        if not student_answers:
            return {
                'total_students': 0,
                'average_proficiency': 0.0,
                'average_grade': 0.0,
                'approval_rate': 0.0,
                'classification_distribution': {
                    'Abaixo do Básico': 0,
                    'Básico': 0,
                    'Adequado': 0,
                    'Avançado': 0
                }
            }
        
        # Calcular estatísticas para cada aluno
        student_results = []
        classification_counts = defaultdict(int)
        
        total_questions = len(test.questions) if test.questions else 0
        
        for student_answer in student_answers:
            if total_questions == 0:
                continue
                
            # Obter informações do curso e disciplina
            course_name = test.course or "Anos Iniciais"
            subject_name = test.subject_rel.name if test.subject_rel else "Outras"
            
            # Calcular resultados usando o EvaluationCalculator
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=int(student_answer.correct_answers or 0),
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name
            )
            
            student_results.append(result)
            classification_counts[result['classification']] += 1
        
        # Calcular médias
        if student_results:
            avg_proficiency = sum(r['proficiency'] for r in student_results) / len(student_results)
            avg_grade = sum(r['grade'] for r in student_results) / len(student_results)
            
            # Taxa de aprovação (considerando nota >= 6.0 como aprovação)
            approved_count = sum(1 for r in student_results if r['grade'] >= 6.0)
            approval_rate = (approved_count / len(student_results)) * 100
        else:
            avg_proficiency = 0.0
            avg_grade = 0.0
            approval_rate = 0.0
        
        return {
            'total_students': len(student_results),
            'average_proficiency': round(avg_proficiency, 2),
            'average_grade': round(avg_grade, 2),
            'approval_rate': round(approval_rate, 2),
            'classification_distribution': dict(classification_counts)
        }

    @classmethod
    def get_evaluations_overview(cls, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Retorna visão geral de todas as avaliações com estatísticas
        
        Args:
            filters: Filtros opcionais
            
        Returns:
            Lista de avaliações com estatísticas
        """
        
        # Query base para avaliações
        query = Test.query.filter(Test.status == 'concluida')
        
        # Aplicar filtros se fornecidos
        if filters:
            if 'course' in filters:
                query = query.filter(Test.course.ilike(f"%{filters['course']}%"))
            if 'subject' in filters:
                query = query.join(Subject, Test.subject == Subject.id)\
                            .filter(Subject.name.ilike(f"%{filters['subject']}%"))
        
        evaluations = query.all()
        results = []
        
        for evaluation in evaluations:
            stats = cls.calculate_evaluation_statistics(evaluation.id)
            
            results.append({
                'id': evaluation.id,
                'name': evaluation.title,
                'subject': evaluation.subject_rel.name if evaluation.subject_rel else 'N/A',
                'course': evaluation.course or 'N/A',
                'date': evaluation.created_at.isoformat() if evaluation.created_at else None,
                'status': evaluation.status,
                'total_students': stats.get('total_students', 0),
                'average_proficiency': stats.get('average_proficiency', 0.0),
                'average_grade': stats.get('average_grade', 0.0),
                'approval_rate': stats.get('approval_rate', 0.0),
                'classification_distribution': stats.get('classification_distribution', {})
            })
        
        return results

    @classmethod
    def get_student_results(cls, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Retorna resultados detalhados dos alunos
        
        Args:
            filters: Filtros opcionais
            
        Returns:
            Lista de resultados de alunos
        """
        
        # Query base para alunos com respostas
        from app.models.question import Question
        
        query = db.session.query(
            Student.id,
            Student.name,
            Student.class_id,
            StudentAnswer.test_id,
            func.count(StudentAnswer.id).label('total_answered'),
            func.sum(
                case(
                    (StudentAnswer.answer == Question.correct_answer, 1),
                    else_=0
                )
            ).label('correct_answers')
        ).join(
            StudentAnswer, Student.id == StudentAnswer.student_id
        ).join(
            Question, StudentAnswer.question_id == Question.id
        ).join(
            Test, StudentAnswer.test_id == Test.id
        ).filter(
            Test.status == 'concluida'
        )
        
        # Aplicar filtros
        if filters:
            if 'class_id' in filters:
                query = query.filter(Student.class_id == filters['class_id'])
            if 'school' in filters:
                query = query.filter(Student.school_id == filters['school'])
            if 'evaluation_id' in filters:
                query = query.filter(StudentAnswer.test_id == filters['evaluation_id'])
        
        query = query.group_by(
            Student.id, Student.name, Student.class_id, StudentAnswer.test_id
        )
        
        student_data = query.all()
        results = []
        
        for student in student_data:
            # Buscar informações da avaliação
            test = Test.query.get(student.test_id)
            if not test:
                continue
                
            # Buscar informações da turma
            class_obj = Class.query.get(student.class_id)
            class_name = class_obj.name if class_obj else 'N/A'
            
            total_questions = len(test.questions) if test.questions else 0
            if total_questions == 0:
                continue
            
            # Calcular resultados
            course_name = test.course or "Anos Iniciais"
            subject_name = test.subject_rel.name if test.subject_rel else "Outras"
            
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=int(student.correct_answers or 0),
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name
            )
            
            # Aplicar filtros pós-cálculo
            if filters:
                if 'proficiency_min' in filters and result['proficiency'] < filters['proficiency_min']:
                    continue
                if 'proficiency_max' in filters and result['proficiency'] > filters['proficiency_max']:
                    continue
                if 'grade_min' in filters and result['grade'] < filters['grade_min']:
                    continue
                if 'grade_max' in filters and result['grade'] > filters['grade_max']:
                    continue
                if 'classification' in filters and result['classification'] != filters['classification']:
                    continue
            
            results.append({
                'student_id': student.id,
                'name': student.name,
                'class': class_name,
                'evaluation': test.title,
                'evaluation_id': test.id,
                'proficiency': result['proficiency'],
                'grade': result['grade'],
                'classification': result['classification'],
                'accuracy_rate': result['accuracy_rate']
            })
        
        return results

    @classmethod
    def get_classification_distribution_chart_data(cls, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Gera dados para gráfico de distribuição de classificações
        
        Args:
            filters: Filtros opcionais
            
        Returns:
            Dados formatados para gráfico
        """
        
        results = cls.get_student_results(filters)
        
        # Contar classificações
        classification_counts = defaultdict(int)
        for result in results:
            classification_counts[result['classification']] += 1
        
        # Preparar dados para gráfico
        labels = ['Abaixo do Básico', 'Básico', 'Adequado', 'Avançado']
        data = [classification_counts.get(label, 0) for label in labels]
        
        return {
            'labels': labels,
            'data': data,
            'total_students': len(results)
        }

    @classmethod
    def get_proficiency_distribution_chart_data(cls, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Gera dados para gráfico de distribuição de proficiência
        
        Args:
            filters: Filtros opcionais
            
        Returns:
            Dados formatados para gráfico de histograma
        """
        
        results = cls.get_student_results(filters)
        
        if not results:
            return {'ranges': [], 'counts': [], 'total_students': 0}
        
        # Definir faixas de proficiência
        ranges = [
            (0, 100), (100, 150), (150, 200), (200, 250),
            (250, 300), (300, 350), (350, 400), (400, 425)
        ]
        
        range_counts = [0] * len(ranges)
        range_labels = []
        
        for i, (min_val, max_val) in enumerate(ranges):
            count = sum(1 for r in results if min_val <= r['proficiency'] < max_val)
            range_counts[i] = count
            range_labels.append(f"{min_val}-{max_val}")
        
        return {
            'labels': range_labels,
            'data': range_counts,
            'total_students': len(results)
        }

    @classmethod
    def get_school_comparison_data(cls, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Gera dados para comparação entre escolas
        
        Args:
            filters: Filtros opcionais
            
        Returns:
            Dados de comparação entre escolas
        """
        
        # Query para agrupar por escola
        query = db.session.query(
            School.id,
            School.name,
            func.count(Student.id).label('total_students')
        ).join(
            Student, School.id == Student.school_id
        ).join(
            StudentAnswer, Student.id == StudentAnswer.student_id
        ).join(
            Test, StudentAnswer.test_id == Test.id
        ).filter(
            Test.status == 'concluida'
        ).group_by(School.id, School.name)
        
        schools = query.all()
        school_data = []
        
        for school in schools:
            # Calcular estatísticas para esta escola
            school_filters = dict(filters or {})
            school_filters['school'] = school.id
            
            results = cls.get_student_results(school_filters)
            
            if results:
                avg_proficiency = sum(r['proficiency'] for r in results) / len(results)
                avg_grade = sum(r['grade'] for r in results) / len(results)
                approval_rate = sum(1 for r in results if r['grade'] >= 6.0) / len(results) * 100
            else:
                avg_proficiency = 0.0
                avg_grade = 0.0
                approval_rate = 0.0
            
            school_data.append({
                'school_id': school.id,
                'school_name': school.name,
                'total_students': len(results),
                'average_proficiency': round(avg_proficiency, 2),
                'average_grade': round(avg_grade, 2),
                'approval_rate': round(approval_rate, 2)
            })
        
        return {
            'schools': school_data,
            'total_schools': len(school_data)
        }

    @classmethod
    def calculate_historical_trends(cls, evaluation_id: str, months: int = 12) -> Dict[str, Any]:
        """
        Calcula tendências históricas de uma avaliação
        
        Args:
            evaluation_id: ID da avaliação
            months: Número de meses para análise
            
        Returns:
            Dados de tendência histórica
        """
        
        # Esta funcionalidade seria expandida para comparar
        # aplicações da mesma avaliação ao longo do tempo
        # Por enquanto, retorna dados básicos
        
        stats = cls.calculate_evaluation_statistics(evaluation_id)
        
        return {
            'current_period': stats,
            'trend': 'stable',  # Seria calculado com dados históricos
            'improvement_areas': [
                'Matemática' if stats.get('average_grade', 0) < 6.0 else None
            ]
        } 