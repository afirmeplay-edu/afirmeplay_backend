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
    Usa UTC como referência para garantir precisão independente do fuso do servidor
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    return utc_now.astimezone(BRAZIL_TIMEZONE)

def get_brazil_utcnow():
    """
    Retorna o tempo atual no fuso horário do Brasil (compatível com utcnow)
    Usa UTC como referência para garantir precisão independente do fuso do servidor
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    return utc_now.astimezone(BRAZIL_TIMEZONE)

def convert_to_brazil_time(dt):
    """
    Converte um datetime para o timezone do Brasil.
    Se o datetime for naive (sem timezone), mantém como naive para ser tratado como horário local.
    """
    if dt is None:
        return None
    
    # Se for string, converte para datetime
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            # Se falhar, tenta sem timezone
            dt = datetime.fromisoformat(dt)
    
    # Se for naive datetime, mantém como naive (será tratado como horário local pelo PostgreSQL)
    if dt.tzinfo is None:
        return dt
    
    # Se já tem timezone, converte para Brasil
    brazil_tz = pytz.timezone('America/Sao_Paulo')
    return dt.astimezone(brazil_tz)

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
    now = get_brazil_time()  # Usar a função corrigida
    return {
        'timezone': 'America/Sao_Paulo',
        'utc_offset': now.utcoffset(),
        'current_time': now.isoformat(),
        'is_dst': now.dst() != timedelta(0)
    } 