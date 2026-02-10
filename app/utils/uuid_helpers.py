# -*- coding: utf-8 -*-
"""
Funções auxiliares para conversão e manipulação de UUIDs
"""

import uuid
from typing import Any, List, Union, Optional


def ensure_uuid(value: Any) -> Optional[uuid.UUID]:
    """
    Garante que o valor seja UUID, converte string se necessário.
    
    Args:
        value: Valor a converter (pode ser string, UUID ou None)
        
    Returns:
        UUID ou None se value for None
        
    Examples:
        >>> ensure_uuid("123e4567-e89b-12d3-a456-426614174000")
        UUID('123e4567-e89b-12d3-a456-426614174000')
        >>> ensure_uuid(None)
        None
    """
    if value is None:
        return None
    
    if isinstance(value, uuid.UUID):
        return value
    
    if isinstance(value, str):
        if not value:  # String vazia
            return None
        try:
            return uuid.UUID(value)
        except (ValueError, AttributeError):
            # Se não for UUID válido, retornar None ou lançar exceção
            # Por enquanto, retornar None para valores inválidos
            return None
    
    # Se for outro tipo, tentar converter para string primeiro
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def ensure_uuid_list(values: Union[List[Any], None]) -> List[uuid.UUID]:
    """
    Garante que lista de valores seja UUIDs, converte strings se necessário.
    
    Args:
        values: Lista de valores a converter (pode conter strings, UUIDs ou None)
        
    Returns:
        Lista de UUIDs (valores None são filtrados)
        
    Examples:
        >>> ensure_uuid_list(["123e4567-e89b-12d3-a456-426614174000"])
        [UUID('123e4567-e89b-12d3-a456-426614174000')]
        >>> ensure_uuid_list([])
        []
    """
    if not values:
        return []
    
    result = []
    for v in values:
        uuid_val = ensure_uuid(v)
        if uuid_val is not None:
            result.append(uuid_val)
    
    return result


def uuid_to_str(value: Any) -> Optional[str]:
    """
    Converte UUID para string, útil para serialização JSON.
    
    Args:
        value: UUID, string ou None
        
    Returns:
        String ou None
        
    Examples:
        >>> uuid_to_str(uuid.UUID("123e4567-e89b-12d3-a456-426614174000"))
        '123e4567-e89b-12d3-a456-426614174000'
        >>> uuid_to_str(None)
        None
    """
    if value is None:
        return None
    
    if isinstance(value, str):
        return value
    
    if isinstance(value, uuid.UUID):
        return str(value)
    
    return str(value) if value else None


def uuid_list_to_str(values: Union[List[Any], None]) -> List[str]:
    """
    Converte lista de UUIDs para lista de strings, útil para serialização JSON.
    
    Args:
        values: Lista de UUIDs, strings ou None
        
    Returns:
        Lista de strings
        
    Examples:
        >>> uuid_list_to_str([uuid.UUID("123e4567-e89b-12d3-a456-426614174000")])
        ['123e4567-e89b-12d3-a456-426614174000']
        >>> uuid_list_to_str([])
        []
    """
    if not values:
        return []
    
    return [uuid_to_str(v) for v in values if v is not None]

