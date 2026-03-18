# -*- coding: utf-8 -*-
"""
Utilitários para padronizar arredondamento de valores decimais
Garante consistência em todo o sistema
"""


def round_to_two_decimals(value: float) -> float:
    """
    Arredonda um valor para exatamente 2 casas decimais
    
    Esta é a ÚNICA função que deve ser usada para arredondamento
    em todo o sistema de avaliações para garantir consistência.
    
    Args:
        value: Valor a ser arredondado
        
    Returns:
        Valor arredondado para 2 casas decimais
        
    Examples:
        >>> round_to_two_decimals(2.5)
        2.5
        >>> round_to_two_decimals(2.567)
        2.57
        >>> round_to_two_decimals(2.564)
        2.56
    """
    if value is None:
        return 0.0
    return round(float(value), 2)


def format_percentage(value: float) -> float:
    """
    Formata um percentual para 2 casas decimais
    
    Args:
        value: Valor do percentual (0-100)
        
    Returns:
        Percentual arredondado para 2 casas decimais
    """
    return round_to_two_decimals(value)


def format_grade(value: float) -> float:
    """
    Formata uma nota para 2 casas decimais
    Garante que está entre 0 e 10
    
    Args:
        value: Valor da nota
        
    Returns:
        Nota arredondada para 2 casas decimais, limitada entre 0 e 10
    """
    value = round_to_two_decimals(value)
    return max(0.0, min(10.0, value))


def format_proficiency(value: float) -> float:
    """
    Formata uma proficiência para 2 casas decimais
    
    Args:
        value: Valor da proficiência
        
    Returns:
        Proficiência arredondada para 2 casas decimais
    """
    return round_to_two_decimals(value)
