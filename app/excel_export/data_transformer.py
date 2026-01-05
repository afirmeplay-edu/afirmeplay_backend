# -*- coding: utf-8 -*-
"""
Transformação de dados de comparação de avaliações para formato tabular Excel
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class DataTransformer:
    """Transforma dados de comparação sequencial em estrutura tabular para Excel"""
    
    @staticmethod
    def transform_comparison_data(comparison_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transforma dados de comparação em estrutura tabular
        
        Args:
            comparison_data: Dados retornados por EvaluationComparisonService.compare_evaluations()
            
        Returns:
            Dicionário com dados transformados em formato tabular
        """
        try:
            evaluations = comparison_data.get('evaluations', [])
            comparisons = comparison_data.get('comparisons', [])
            
            if not evaluations or not comparisons:
                return {}
            
            # Extrair valores de cada avaliação
            general_data = DataTransformer._extract_general_data(evaluations, comparisons)
            subject_data = DataTransformer._extract_subject_data(evaluations, comparisons)
            classification_data = DataTransformer._extract_classification_data(evaluations, comparisons)
            
            # Extrair dados de participação
            participation_data = comparison_data.get('participation', {})
            participation_transformed = DataTransformer._extract_participation_data(evaluations, participation_data)
            
            return {
                'evaluations': evaluations,
                'general': general_data,
                'subjects': subject_data,
                'classification': classification_data,
                'participation': participation_transformed
            }
        except Exception as e:
            logger.error(f"Erro ao transformar dados: {str(e)}", exc_info=True)
            return {}
    
    @staticmethod
    def _extract_general_data(evaluations: List[Dict], comparisons: List[Dict]) -> Dict[str, Any]:
        """Extrai dados gerais (nota e proficiência) - sempre garante 3 avaliações"""
        num_evaluations = max(len(evaluations), 3)  # Sempre pelo menos 3
        
        # Inicializar estruturas (sempre 3 avaliações)
        average_grades = [None] * 3
        average_proficiencies = [None] * 3
        grade_variations = [None] * 2  # 2 variações para 3 avaliações
        proficiency_variations = [None] * 2
        grade_directions = [None] * 2
        proficiency_directions = [None] * 2
        
        # Preencher valores da primeira avaliação
        if comparisons:
            first_comp = comparisons[0]
            general = first_comp.get('general_comparison', {})
            
            avg_grade = general.get('average_grade', {})
            avg_prof = general.get('average_proficiency', {})
            
            average_grades[0] = avg_grade.get('evaluation_1')
            average_proficiencies[0] = avg_prof.get('evaluation_1')
        
        # Preencher valores das avaliações seguintes e variações
        for i, comp in enumerate(comparisons):
            if i >= 2:  # Limitar a 2 comparações (para ter 3 avaliações)
                break
                
            general = comp.get('general_comparison', {})
            
            avg_grade = general.get('average_grade', {})
            avg_prof = general.get('average_proficiency', {})
            
            # Valor da avaliação seguinte
            evaluation_2_grade = avg_grade.get('evaluation_2')
            evaluation_2_prof = avg_prof.get('evaluation_2')
            
            if evaluation_2_grade is not None:
                average_grades[i + 1] = evaluation_2_grade
            if evaluation_2_prof is not None:
                average_proficiencies[i + 1] = evaluation_2_prof
            
            # Variações
            evolution_grade = avg_grade.get('evolution', {})
            evolution_prof = avg_prof.get('evolution', {})
            
            if evolution_grade:
                grade_variations[i] = evolution_grade.get('percentage')
                grade_directions[i] = evolution_grade.get('direction', 'stable')
            
            if evolution_prof:
                proficiency_variations[i] = evolution_prof.get('percentage')
                proficiency_directions[i] = evolution_prof.get('direction', 'stable')
        
        return {
            'average_grades': average_grades,
            'average_proficiencies': average_proficiencies,
            'grade_variations': grade_variations,
            'proficiency_variations': proficiency_variations,
            'grade_directions': grade_directions,
            'proficiency_directions': proficiency_directions
        }
    
    @staticmethod
    def _extract_subject_data(evaluations: List[Dict], comparisons: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Extrai dados por disciplina"""
        subjects_data = {}
        
        # Coletar todas as disciplinas de todas as comparações
        all_subjects = set()
        for comp in comparisons:
            subject_comp = comp.get('subject_comparison', {})
            all_subjects.update(subject_comp.keys())
        
        # Sempre garantir 3 avaliações
        num_evaluations = 3
        
        for subject_name in all_subjects:
            # Inicializar estruturas para esta disciplina (sempre 3 avaliações)
            average_grades = [None] * 3
            average_proficiencies = [None] * 3
            grade_variations = [None] * 2
            proficiency_variations = [None] * 2
            grade_directions = [None] * 2
            proficiency_directions = [None] * 2
            
            # Preencher dados da primeira comparação
            if comparisons:
                first_comp = comparisons[0]
                subject_comp = first_comp.get('subject_comparison', {})
                subject_data = subject_comp.get(subject_name, {})
                
                if subject_data:
                    avg_grade = subject_data.get('average_grade', {})
                    avg_prof = subject_data.get('average_proficiency', {})
                    
                    average_grades[0] = avg_grade.get('evaluation_1')
                    average_proficiencies[0] = avg_prof.get('evaluation_1')
            
            # Preencher dados das comparações seguintes (máximo 2 comparações)
            for i, comp in enumerate(comparisons):
                if i >= 2:  # Limitar a 2 comparações
                    break
                    
                subject_comp = comp.get('subject_comparison', {})
                subject_data = subject_comp.get(subject_name, {})
                
                if subject_data:
                    avg_grade = subject_data.get('average_grade', {})
                    avg_prof = subject_data.get('average_proficiency', {})
                    
                    evaluation_2_grade = avg_grade.get('evaluation_2')
                    evaluation_2_prof = avg_prof.get('evaluation_2')
                    
                    if evaluation_2_grade is not None:
                        average_grades[i + 1] = evaluation_2_grade
                    if evaluation_2_prof is not None:
                        average_proficiencies[i + 1] = evaluation_2_prof
                    
                    evolution_grade = avg_grade.get('evolution', {})
                    evolution_prof = avg_prof.get('evolution', {})
                    
                    if evolution_grade:
                        grade_variations[i] = evolution_grade.get('percentage')
                        grade_directions[i] = evolution_grade.get('direction', 'stable')
                    
                    if evolution_prof:
                        proficiency_variations[i] = evolution_prof.get('percentage')
                        proficiency_directions[i] = evolution_prof.get('direction', 'stable')
            
            subjects_data[subject_name] = {
                'average_grades': average_grades,
                'average_proficiencies': average_proficiencies,
                'grade_variations': grade_variations,
                'proficiency_variations': proficiency_variations,
                'grade_directions': grade_directions,
                'proficiency_directions': proficiency_directions
            }
        
        return subjects_data
    
    @staticmethod
    def _extract_classification_data(evaluations: List[Dict], comparisons: List[Dict]) -> Dict[str, Any]:
        """Extrai dados de distribuição de classificação - sempre garante 3 avaliações"""
        num_evaluations = 3  # Sempre 3 avaliações
        levels = ['Abaixo do Básico', 'Básico', 'Adequado', 'Avançado']
        
        # Inicializar estrutura: {level: [valores por avaliação]} - sempre 3
        classification_data = {level: [None] * 3 for level in levels}
        variations = {level: [None] * 2 for level in levels}  # 2 variações
        directions = {level: [None] * 2 for level in levels}
        
        # Preencher primeira avaliação
        if comparisons:
            first_comp = comparisons[0]
            general = first_comp.get('general_comparison', {})
            dist_1 = general.get('classification_distribution', {}).get('evaluation_1', {})
            
            for level in levels:
                classification_data[level][0] = dist_1.get(level, 0)
        
        # Preencher avaliações seguintes e variações (máximo 2 comparações)
        for i, comp in enumerate(comparisons):
            if i >= 2:  # Limitar a 2 comparações
                break
                
            general = comp.get('general_comparison', {})
            dist_1 = general.get('classification_distribution', {}).get('evaluation_1', {})
            dist_2 = general.get('classification_distribution', {}).get('evaluation_2', {})
            
            for level in levels:
                value_1 = dist_1.get(level, 0)
                value_2 = dist_2.get(level, 0)
                
                classification_data[level][i + 1] = value_2
                
                # Calcular variação percentual
                if value_1 > 0:
                    variation = ((value_2 - value_1) / value_1) * 100
                elif value_2 > 0:
                    variation = 100.0
                else:
                    variation = 0.0
                
                variations[level][i] = round(variation, 2)
                
                if variation > 0:
                    directions[level][i] = 'increase'
                elif variation < 0:
                    directions[level][i] = 'decrease'
                else:
                    directions[level][i] = 'stable'
        
        return {
            'classification_data': classification_data,
            'variations': variations,
            'directions': directions
        }
    
    @staticmethod
    def _extract_participation_data(evaluations: List[Dict], participation_data: Dict) -> Dict[str, Any]:
        """
        Extrai dados de participação em formato tabular
        
        Args:
            evaluations: Lista de avaliações
            participation_data: Dados de participação do serviço
            
        Returns:
            {
                'general': {
                    'participation_rates': [95.0, 98.0, 97.0],
                    'total_students': [100, 100, 100],
                    'participating_students': [95, 98, 97],
                    'variations': [None, 3.2, -1.0],
                    'directions': [None, 'increase', 'decrease']
                },
                'by_school': {
                    'evaluation_1': {
                        'school_id_1': {...},
                        'school_id_2': {...}
                    },
                    ...
                }
            }
        """
        try:
            general_participation = participation_data.get('general', {})
            by_school_participation = participation_data.get('by_school', {})
            
            # Sempre garantir 3 avaliações
            num_evaluations = max(len(evaluations), 3)
            
            # Inicializar estruturas
            participation_rates = [None] * 3
            total_students = [None] * 3
            participating_students = [None] * 3
            variations = [None] * 2
            directions = [None] * 2
            
            # Preencher dados da primeira avaliação
            if 'evaluation_1' in general_participation:
                eval1_data = general_participation['evaluation_1']
                participation_rates[0] = eval1_data.get('participation_rate')
                total_students[0] = eval1_data.get('total_students')
                participating_students[0] = eval1_data.get('participating_students')
            
            # Preencher dados das avaliações seguintes e variações
            for i in range(min(2, len(evaluations) - 1)):  # Máximo 2 variações (para 3 avaliações)
                eval_key_1 = f'evaluation_{i+1}'
                eval_key_2 = f'evaluation_{i+2}'
                
                if eval_key_1 in general_participation and eval_key_2 in general_participation:
                    eval1_data = general_participation[eval_key_1]
                    eval2_data = general_participation[eval_key_2]
                    
                    # Valores da segunda avaliação
                    participation_rates[i + 1] = eval2_data.get('participation_rate')
                    total_students[i + 1] = eval2_data.get('total_students')
                    participating_students[i + 1] = eval2_data.get('participating_students')
                    
                    # Calcular variação
                    rate1 = eval1_data.get('participation_rate')
                    rate2 = eval2_data.get('participation_rate')
                    
                    if rate1 is not None and rate2 is not None and rate1 > 0:
                        variation = ((rate2 - rate1) / rate1) * 100
                        variations[i] = round(variation, 2)
                        
                        if variation > 0:
                            directions[i] = 'increase'
                        elif variation < 0:
                            directions[i] = 'decrease'
                        else:
                            directions[i] = 'stable'
            
            return {
                'general': {
                    'participation_rates': participation_rates,
                    'total_students': total_students,
                    'participating_students': participating_students,
                    'variations': variations,
                    'directions': directions
                },
                'by_school': by_school_participation
            }
        except Exception as e:
            logger.error(f"Erro ao extrair dados de participação: {str(e)}", exc_info=True)
            return {
                'general': {
                    'participation_rates': [None] * 3,
                    'total_students': [None] * 3,
                    'participating_students': [None] * 3,
                    'variations': [None] * 2,
                    'directions': [None] * 2
                },
                'by_school': {}
            }


