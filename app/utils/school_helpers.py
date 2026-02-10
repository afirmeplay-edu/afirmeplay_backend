"""
Helper para queries de School que evita problemas de tipo UUID vs VARCHAR
"""
from app.models.school import School
from app import db
from app.utils.uuid_helpers import uuid_to_str


def get_school_safe(school_id):
    """
    Busca escola de forma segura, convertendo UUID para string se necessário.
    
    ✅ CORRETO: School.query.filter(School.id == str(school_id)).first()
    ❌ ERRADO: School.query.get(school_id)  # Não faz cast e quebra
    
    Args:
        school_id: ID da escola (pode ser UUID ou string)
        
    Returns:
        School object ou None
    """
    if school_id is None:
        return None
    
    school_id_str = uuid_to_str(school_id)
    if not school_id_str:
        return None
    
    return School.query.filter(School.id == school_id_str).first()

