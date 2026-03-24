# -*- coding: utf-8 -*-
"""
Resolução de schema para competições: public vs city_xxx.

Regra:
- individual, estado, global -> public
- municipio (1 city_id) -> schema do município; múltiplos -> public
- escola (escolas de 1 cidade) -> schema da cidade; várias cidades -> public
- turma (turmas de 1 cidade) -> schema da cidade; várias cidades -> public
"""
import logging
from sqlalchemy import text
from app import db

logger = logging.getLogger(__name__)


def _city_id_to_schema_name(city_id):
    """Import tardio para evitar ciclo: tenant_middleware -> models -> competitions -> tenant_middleware."""
    from app.utils.tenant_middleware import city_id_to_schema_name
    return city_id_to_schema_name(city_id)


def _schema_for_school_id(school_id):
    """
    Retorna o nome do schema (city_xxx) que contém a escola com o id dado, ou None.
    """
    if not school_id:
        return None
    try:
        rp = db.session.execute(
            text("""
                SELECT n.nspname
                FROM pg_namespace n
                JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = 'school'
                WHERE n.nspname LIKE 'city_%'
                ORDER BY n.nspname
            """)
        )
        for row in rp.fetchall():
            schema = row[0]
            try:
                r = db.session.execute(
                    text('SELECT city_id FROM "{}".school WHERE id = :sid'.format(schema)),
                    {"sid": str(school_id)},
                )
                row2 = r.fetchone()
                if row2 and row2[0]:
                    return _city_id_to_schema_name(str(row2[0]))
            except Exception:
                continue
        return None
    except Exception:
        return None


def _schema_for_class_id(class_id):
    """
    Retorna o nome do schema (city_xxx) que contém a turma (class) com o id dado, ou None.
    Resolve via class -> school -> city_id no schema.
    """
    if not class_id:
        return None
    try:
        rp = db.session.execute(
            text("""
                SELECT n.nspname
                FROM pg_namespace n
                JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = 'class'
                WHERE n.nspname LIKE 'city_%'
                ORDER BY n.nspname
            """)
        )
        for row in rp.fetchall():
            schema = row[0]
            try:
                # class tem school_id; school tem city_id
                r = db.session.execute(
                    text('''
                        SELECT s.city_id FROM "{}".class cl
                        JOIN "{}".school s ON s.id = cl.school_id
                        WHERE cl.id = :cid
                    '''.format(schema, schema)),
                    {"cid": str(class_id)},
                )
                row2 = r.fetchone()
                if row2 and row2[0]:
                    return _city_id_to_schema_name(str(row2[0]))
            except Exception:
                continue
        return None
    except Exception:
        return None


def get_competition_target_schema(scope, scope_filter, tenant_schema=None, tenant_city_id=None):
    """
    Determina em qual schema (public ou city_xxx) a competição deve ser criada.

    Args:
        scope: individual, estado, global, municipio, escola, turma
        scope_filter: dict com city_ids, school_ids, class_ids conforme o escopo
        tenant_schema: schema do tenant atual (opcional)
        tenant_city_id: city_id do tenant atual (opcional)

    Returns:
        'public' ou 'city_9a2f95ed_9f70_4863_a5f1_1b6c6c262b0d'
    """
    scope = (scope or 'individual').strip().lower()
    sf = scope_filter or {}

    if scope in ('individual', 'estado', 'global'):
        return 'public'

    if scope == 'municipio':
        city_ids = sf.get('municipality_ids') or sf.get('city_ids')
        if not city_ids:
            return 'public'
        if isinstance(city_ids, (list, tuple)):
            ids = [str(x) for x in city_ids if x]
        else:
            ids = [str(city_ids)]
        if len(ids) == 0:
            return 'public'
        if len(ids) == 1:
            return _city_id_to_schema_name(ids[0])
        return 'public'

    if scope == 'escola':
        school_ids = sf.get('school_ids')
        if not school_ids:
            return 'public'
        ids = list(school_ids) if isinstance(school_ids, (list, tuple)) else [school_ids]
        ids = [str(x) for x in ids if x]
        if not ids:
            return 'public'
        schemas = set()
        for sid in ids:
            sch = _schema_for_school_id(sid)
            if sch:
                schemas.add(sch)
        if len(schemas) == 1:
            return list(schemas)[0]
        return 'public'

    if scope == 'turma':
        class_ids = sf.get('class_ids')
        if not class_ids:
            return 'public'
        ids = list(class_ids) if isinstance(class_ids, (list, tuple)) else [class_ids]
        ids = [str(x) for x in ids if x]
        if not ids:
            return 'public'
        schemas = set()
        for cid in ids:
            sch = _schema_for_class_id(cid)
            if sch:
                schemas.add(sch)
        if len(schemas) == 1:
            return list(schemas)[0]
        return 'public'

    return 'public'


def _safe_schema_name(schema_name):
    """Escapa nome de schema para uso em SQL (evita quebra com aspas)."""
    if not schema_name:
        return ""
    return (str(schema_name)).replace('"', '""')


def get_competition_schema(competition_id, tenant_schema=None):
    """
    Localiza em qual schema a competição está (public ou city_xxx).
    Usa apenas SELECT para evitar conflito de identity map; o chamador deve
    fazer set_search_path(schema) e então Competition.query.get_or_404(competition_id).

    Args:
        competition_id: id da competição
        tenant_schema: se fornecido, busca também no schema do tenant

    Returns:
        str: 'public', nome do schema city_xxx, ou None se não encontrada.
    """
    cid = str(competition_id).strip() if competition_id else ""
    if not cid:
        return None

    # Garantir transação limpa (evitar "current transaction is aborted" em conexão do pool)
    try:
        db.session.rollback()
    except Exception:
        pass

    def _exists_in_schema(schema_name):
        try:
            if schema_name == "public":
                r = db.session.execute(
                    text("SELECT 1 FROM public.competitions WHERE id = :id"),
                    {"id": cid},
                )
            else:
                safe = _safe_schema_name(schema_name)
                r = db.session.execute(
                    text('SELECT 1 FROM "{}".competitions WHERE id = :id'.format(safe)),
                    {"id": cid},
                )
            return r.fetchone() is not None
        except Exception as e:
            logger.debug("get_competition_schema: lookup %s failed: %s", schema_name, e)
            return False

    # 1) Buscar em public (competições com scope individual/global ficam aqui)
    if _exists_in_schema("public"):
        return "public"

    # 2) Schema do tenant (request com X-City-ID)
    if tenant_schema and tenant_schema != "public":
        if _exists_in_schema(tenant_schema):
            return tenant_schema

    # 3) Todos os schemas city_* (admin sem cidade ainda deve encontrar)
    try:
        rp = db.session.execute(
            text("""
                SELECT n.nspname
                FROM pg_namespace n
                JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = 'competitions'
                WHERE n.nspname LIKE 'city_%'
                ORDER BY n.nspname
            """)
        )
        for row in rp.fetchall():
            schema = row[0]
            if schema and _exists_in_schema(schema):
                return schema
    except Exception as e:
        logger.debug("get_competition_schema: city_* fallback failed: %s", e)

    # 4) Fallback: information_schema (qualquer schema com tabela competitions)
    try:
        rp = db.session.execute(
            text("""
                SELECT table_schema FROM information_schema.tables
                WHERE table_schema NOT LIKE 'pg_%' AND table_schema != 'information_schema'
                AND table_name = 'competitions'
                ORDER BY CASE WHEN table_schema = 'public' THEN 0 ELSE 1 END, table_schema
            """)
        )
        for row in rp.fetchall():
            schema = row[0]
            if schema and _exists_in_schema(schema):
                return schema
    except Exception as e:
        logger.debug("get_competition_schema: information_schema fallback failed: %s", e)

    logger.warning("get_competition_schema: competition %s not found in public nor in any schema", cid[:8])
    return None
