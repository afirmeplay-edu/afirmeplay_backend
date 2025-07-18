"""
Utilitários para gerenciamento de fuso horário do Brasil
"""

from datetime import datetime, timezone, timedelta
import pytz

# Fuso horário do Brasil (UTC-3)
BRAZIL_TIMEZONE = pytz.timezone('America/Sao_Paulo')

def get_brazil_time():
    """
    Retorna o tempo atual no fuso horário do Brasil
    """
    return datetime.now(BRAZIL_TIMEZONE)

def get_brazil_utcnow():
    """
    Retorna o tempo atual no fuso horário do Brasil (compatível com utcnow)
    """
    return datetime.now(BRAZIL_TIMEZONE)

def convert_to_brazil_time(dt):
    """
    Converte uma data/hora para o fuso horário do Brasil
    
    Args:
        dt: datetime object (com ou sem timezone)
    
    Returns:
        datetime no fuso horário do Brasil
    """
    if dt is None:
        return None
    
    # Se não tem timezone, assumir que é UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Converter para fuso horário do Brasil
    return dt.astimezone(BRAZIL_TIMEZONE)

def convert_from_brazil_time(dt):
    """
    Converte uma data/hora do fuso horário do Brasil para UTC
    
    Args:
        dt: datetime object no fuso horário do Brasil
    
    Returns:
        datetime em UTC
    """
    if dt is None:
        return None
    
    # Se não tem timezone, assumir que é do Brasil
    if dt.tzinfo is None:
        dt = BRAZIL_TIMEZONE.localize(dt)
    
    # Converter para UTC
    return dt.astimezone(timezone.utc)

def is_brazil_timezone(dt):
    """
    Verifica se uma data/hora está no fuso horário do Brasil
    """
    if dt is None or dt.tzinfo is None:
        return False
    
    return dt.tzinfo == BRAZIL_TIMEZONE

def format_brazil_time(dt, format_str="%Y-%m-%d %H:%M:%S"):
    """
    Formata uma data/hora no fuso horário do Brasil
    """
    if dt is None:
        return None
    
    brazil_time = convert_to_brazil_time(dt)
    return brazil_time.strftime(format_str)

def get_brazil_timezone_info():
    """
    Retorna informações sobre o fuso horário do Brasil
    """
    now = datetime.now(BRAZIL_TIMEZONE)
    return {
        'timezone': 'America/Sao_Paulo',
        'utc_offset': now.utcoffset(),
        'current_time': now.isoformat(),
        'is_dst': now.dst() != timedelta(0)
    } 