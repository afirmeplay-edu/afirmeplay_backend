# -*- coding: utf-8 -*-
"""
Fábrica de sessões SQLAlchemy com `schema_translate_map` para o schema lógico `tenant`.

No PostgreSQL, dados por município vivem **sempre** em schemas `city_<uuid>` (hífens do
UUID viram underscore). **Não** existem schemas físicos `tenant_*` nem um schema real
chamado `tenant`; esse nome é só o placeholder lógico nos models (`schema="tenant"`),
traduzido em runtime para `city_...`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# Schema lógico usado nos models tenant (deve coincidir com __table_args__["schema"])
LOGICAL_TENANT_SCHEMA = "tenant"


class DatabaseSessionFactory:
    """
    Cria sessões independentes do `db.session` global (compatível com migração gradual).

    - `get_public_session`: sem tradução; use apenas models com `schema="public"`.
    - `get_tenant_session`: traduz o schema lógico `tenant` para o schema físico do município.
    """

    _makers: dict[int, sessionmaker] = {}

    @classmethod
    def _sessionmaker(cls, bind: "Engine") -> sessionmaker:
        key = id(bind)
        if key not in cls._makers:
            cls._makers[key] = sessionmaker(
                bind=bind,
                autoflush=True,
                autocommit=False,
                expire_on_commit=False,
            )
        return cls._makers[key]

    @classmethod
    def get_public_session(cls, engine: "Engine") -> Session:
        """Sessão para tabelas globais (`public.*`)."""
        return cls._sessionmaker(engine)()

    @classmethod
    def get_tenant_session(cls, engine: "Engine", tenant_schema: str) -> Session:
        """
        Sessão para dados do município: traduz `tenant` → `tenant_schema` (ex.: city_...).

        Tabelas com `schema="public"` permanecem em `public` na SQL gerada.

        O `schema_translate_map` é aplicado no **Engine** (`engine.execution_options`),
        não na `Session`: em alguns stacks o objeto retornado por `sessionmaker()()` não
        expõe `execution_options` como esperado, o que gerava
        `'Session' object has no attribute 'execution_options'`.
        """
        if not tenant_schema or tenant_schema == "public":
            return cls.get_public_session(engine)
        bound = engine.execution_options(
            schema_translate_map={LOGICAL_TENANT_SCHEMA: tenant_schema}
        )
        return sessionmaker(
            bind=bound,
            autoflush=True,
            autocommit=False,
            expire_on_commit=False,
        )()
