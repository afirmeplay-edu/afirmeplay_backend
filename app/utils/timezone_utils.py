"""
Utilitários para gerenciamento de fuso horário local do servidor
"""

from datetime import datetime, timezone, timedelta
import pytz
import os

# Detectar o fuso horário local do servidor
def get_local_timezone():
    """
    Detecta o fuso horário local do servidor
    Prioriza variável de ambiente TZ, depois timezone do sistema
    """
    # Verificar variável de ambiente TZ primeiro
    tz_env = os.environ.get('TZ')
    if tz_env:
        try:
            return pytz.timezone(tz_env)
        except pytz.exceptions.UnknownTimeZoneError:
            pass
    
    # Se não houver TZ ou for inválido, usar timezone local do sistema
    try:
        # Usar timezone local do sistema
        local_tz = datetime.now().astimezone().tzinfo
        if local_tz:
            return local_tz
    except:
        pass
    
    # Fallback para UTC se não conseguir detectar
    return timezone.utc

# Fuso horário local do servidor
LOCAL_TIMEZONE = get_local_timezone()

def get_local_time():
    """
    Retorna o tempo atual no fuso horário local do servidor
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    return utc_now.astimezone(LOCAL_TIMEZONE)

def get_local_utcnow():
    """
    Retorna o tempo atual no fuso horário local do servidor (compatível com utcnow)
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    return utc_now.astimezone(LOCAL_TIMEZONE)

def convert_to_local_time(dt):
    """
    Converte um datetime para o timezone local do servidor.
    Se o datetime for naive (sem timezone), mantém como naive.
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
    
    # Se for naive datetime, mantém como naive
    if dt.tzinfo is None:
        return dt
    
    # Se já tem timezone, converte para timezone local
    return dt.astimezone(LOCAL_TIMEZONE)

def convert_from_local_time(dt):
    """
    Converte uma data/hora do timezone local para UTC
    """
    if dt is None:
        return None
    
    # Se não tem timezone, assumir que é do timezone local
    if dt.tzinfo is None:
        dt = LOCAL_TIMEZONE.localize(dt)
    
    # Converter para UTC
    return dt.astimezone(timezone.utc)

def is_local_timezone(dt):
    """
    Verifica se uma data/hora está no timezone local
    """
    if dt is None or dt.tzinfo is None:
        return False
    
    return dt.tzinfo == LOCAL_TIMEZONE

def format_local_time(dt, format_str="%Y-%m-%d %H:%M:%S"):
    """
    Formata uma data/hora no timezone local
    """
    if dt is None:
        return None
    
    local_time = convert_to_local_time(dt)
    return local_time.strftime(format_str)

def get_timezone_info():
    """
    Retorna informações sobre o timezone local do servidor
    """
    now = get_local_time()
    return {
        'timezone': str(LOCAL_TIMEZONE),
        'utc_offset': now.utcoffset(),
        'current_time': now.isoformat(),
        'is_dst': now.dst() != timedelta(0) if now.dst() else False
    }

# Funções de compatibilidade para manter código existente funcionando
# Estas funções agora usam o timezone local em vez do Brasil

def get_brazil_time():
    """
    DEPRECATED: Use get_local_time() em vez desta função
    Mantida para compatibilidade - agora retorna tempo local
    """
    return get_local_time()

def get_brazil_utcnow():
    """
    DEPRECATED: Use get_local_utcnow() em vez desta função
    Mantida para compatibilidade - agora retorna tempo local
    """
    return get_local_utcnow()

def convert_to_brazil_time(dt):
    """
    DEPRECATED: Use convert_to_local_time() em vez desta função
    Mantida para compatibilidade - agora converte para timezone local
    """
    return convert_to_local_time(dt)

def convert_from_brazil_time(dt):
    """
    DEPRECATED: Use convert_from_local_time() em vez desta função
    Mantida para compatibilidade - agora converte do timezone local
    """
    return convert_from_local_time(dt)

def is_brazil_timezone(dt):
    """
    DEPRECATED: Use is_local_timezone() em vez desta função
    Mantida para compatibilidade - agora verifica timezone local
    """
    return is_local_timezone(dt)

def format_brazil_time(dt, format_str="%Y-%m-%d %H:%M:%S"):
    """
    DEPRECATED: Use format_local_time() em vez desta função
    Mantida para compatibilidade - agora formata no timezone local
    """
    return format_local_time(dt, format_str)

def get_brazil_timezone_info():
    """
    DEPRECATED: Use get_timezone_info() em vez desta função
    Mantida para compatibilidade - agora retorna info do timezone local
    """
    return get_timezone_info() 