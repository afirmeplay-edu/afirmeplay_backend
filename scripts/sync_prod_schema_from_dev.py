"""
Espelha o esquema do PostgreSQL de DEV no PROD (public + city_*).

Fonte de verdade: DEV. Gera DDL a partir do catálogo pg_catalog do DEV e aplica
no PROD na mesma ordem lógica (schema -> tabelas novas por dependência de FK ->
ALTER ADD COLUMN -> constraints FK -> DROP COLUMN extra -> índices em tabelas novas).

Uso (raiz do repositório):
    # Padrão: gera SQL + simula no PROD (ROLLBACK; SAVEPOINT por comando).
    python scripts/sync_prod_schema_from_dev.py \\
        --dev-url "$DATABASE_URL_DEV" --prod-url "$DATABASE_URL_PROD"

    python scripts/sync_prod_schema_from_dev.py --execute \\
        --dev-url "postgresql://..." --prod-url "postgresql://..."

Variáveis de ambiente (se omitir flags): DATABASE_URL_DEV, DATABASE_URL_PROD

Requer: pip install psycopg2-binary

Modo padrão (sem --execute): imprime o plano SQL, avisos heurísticos e
    executa cada comando no PROD dentro de SAVEPOINTs, com ROLLBACK ao final,
    para surface erros reais (permissão, sintaxe, dependências, NOT NULL, etc.).

Não cobre: triggers, regras, policies RLS, publication, owners opcionais,
    comentários, tablespace. Revise manualmente se precisar paridade total.

Idempotência parcial: ADD COLUMN IF NOT EXISTS não existe em todas as versões
    antigas do PG; o script usa ADD COLUMN simples — segunda execução pode falhar
    em objetos já criados; o dry-run ajuda a ver isso.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

try:
    import psycopg2
    from psycopg2.extensions import quote_ident as pg_quote_ident
except ImportError:
    print("Instale psycopg2-binary: pip install psycopg2-binary", file=sys.stderr)
    raise SystemExit(1)


SCHEMA_FILTER_SQL = """
SELECT nspname
FROM pg_namespace
WHERE nspname = 'public'
   OR nspname ~ '^city_'
ORDER BY nspname
"""

LIST_TABLES_SQL = """
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s
  AND c.relkind = 'r'
  AND NOT c.relispartition
ORDER BY c.relname
"""

COLUMNS_SQL = """
SELECT
    a.attname AS name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS fmt_type,
    a.attnotnull AS not_null,
    a.attidentity::text AS identity,
    a.attgenerated::text AS generated,
    pg_catalog.pg_get_expr(ad.adbin, ad.adrelid) AS default_expr,
    CASE WHEN a.attcollation <> t.typcollation THEN coll.collname ELSE NULL END AS collname
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
LEFT JOIN pg_catalog.pg_attrdef ad ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
LEFT JOIN pg_catalog.pg_collation coll ON coll.oid = a.attcollation
WHERE n.nspname = %s
  AND c.relname = %s
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY a.attnum
"""

INLINE_CONSTRAINTS_SQL = """
SELECT con.conname, pg_catalog.pg_get_constraintdef(con.oid, true) AS def, con.contype
FROM pg_catalog.pg_constraint con
JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relname = %s
  AND con.contype IN ('p','u','c')
ORDER BY con.contype, con.conname
"""

FK_CONSTRAINTS_SQL = """
SELECT con.conname, pg_catalog.pg_get_constraintdef(con.oid, true) AS def
FROM pg_catalog.pg_constraint con
JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relname = %s AND con.contype = 'f'
ORDER BY con.conname
"""

FK_DEPS_SQL = """
SELECT
    ref_namespace.nspname AS ref_schema,
    ref_class.relname AS ref_table
FROM pg_catalog.pg_constraint con
JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_class ref_class ON ref_class.oid = con.confrelid
JOIN pg_catalog.pg_namespace ref_namespace ON ref_namespace.oid = ref_class.relnamespace
WHERE n.nspname = %s AND c.relname = %s AND con.contype = 'f'
"""

INDEXES_SQL = """
SELECT indexrelid::regclass::text AS idx_name,
       pg_catalog.pg_get_indexdef(i.indexrelid, 0, true) AS indexdef
FROM pg_catalog.pg_index i
JOIN pg_catalog.pg_class c ON c.oid = i.indrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s
  AND c.relname = %s
  AND NOT i.indisprimary
  AND NOT EXISTS (
      SELECT 1 FROM pg_catalog.pg_constraint con
      WHERE con.conindid = i.indexrelid
  )
ORDER BY indexrelid::regclass::text
"""


@dataclass
class Statement:
    kind: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)


def get_conn(url: str):
    return psycopg2.connect(url)


def qi(conn, name: str) -> str:
    """Identificador citado para o PostgreSQL (evita palavras reservadas)."""
    return pg_quote_ident(name, conn)


def fetch_schemas(cur) -> list[str]:
    cur.execute(SCHEMA_FILTER_SQL)
    return [r[0] for r in cur.fetchall()]


def fetch_tables(cur, schema: str) -> set[str]:
    cur.execute(LIST_TABLES_SQL, (schema,))
    return {r[0] for r in cur.fetchall()}


def fetch_columns(cur, schema: str, table: str) -> list[dict[str, Any]]:
    cur.execute(COLUMNS_SQL, (schema, table))
    cols: list[dict[str, Any]] = []
    for row in cur.fetchall():
        cols.append(
            {
                "name": row[0],
                "fmt_type": row[1],
                "not_null": row[2],
                "identity": row[3] or "",
                "generated": row[4] or "",
                "default_expr": row[5],
                "collname": row[6],
            }
        )
    return cols


def col_sql_fragment(conn, col: dict[str, Any]) -> str:
    """Monta fragmento de coluna para CREATE/ADD (sem vírgula inicial)."""
    qn = qi(conn, col["name"])
    ident = col["identity"]
    gen = col["generated"]
    if gen == "s":
        expr = col["default_expr"] or ""
        tail = ""
        if col["not_null"]:
            tail += " NOT NULL"
        return f"{qn} {col['fmt_type']} GENERATED ALWAYS AS ({expr}) STORED{tail}"
    if ident in ("d", "a"):
        id_clause = "GENERATED ALWAYS AS IDENTITY" if ident == "a" else "GENERATED BY DEFAULT AS IDENTITY"
        tail = ""
        if col["not_null"]:
            tail += " NOT NULL"
        return f"{qn} {col['fmt_type']} {id_clause}{tail}"
    t = col["fmt_type"]
    if col["collname"]:
        t += f' COLLATE "{col["collname"]}"'
    frag = f"{qn} {t}"
    if col["default_expr"]:
        frag += f" DEFAULT {col['default_expr']}"
    if col["not_null"]:
        frag += " NOT NULL"
    return frag


def build_create_table(conn, cur, schema: str, table: str) -> str:
    cols = fetch_columns(cur, schema, table)
    if not cols:
        raise RuntimeError(f"Sem colunas em {schema}.{table} (tabela ausente ou vazia?)")
    col_parts = [col_sql_fragment(conn, c) for c in cols]
    cur.execute(INLINE_CONSTRAINTS_SQL, (schema, table))
    for row in cur.fetchall():
        cname, defn, _ctype = row
        col_parts.append(f"CONSTRAINT {qi(conn, cname)} {defn}")
    inner = ",\n    ".join(col_parts)
    qs = qi(conn, schema)
    qt = qi(conn, table)
    return f"CREATE TABLE {qs}.{qt} (\n    {inner}\n);"


def build_add_column(conn, schema: str, table: str, col: dict[str, Any]) -> str:
    frag = col_sql_fragment(conn, col)
    return f"ALTER TABLE {qi(conn, schema)}.{qi(conn, table)} ADD COLUMN {frag};"


def fetch_fk_alters(conn, cur, schema: str, table: str) -> list[str]:
    cur.execute(FK_CONSTRAINTS_SQL, (schema, table))
    alters = []
    for conname, defn in cur.fetchall():
        alters.append(
            f"ALTER TABLE {qi(conn, schema)}.{qi(conn, table)} "
            f"ADD CONSTRAINT {qi(conn, conname)} {defn};"
        )
    return alters


def fetch_new_table_fk_deps(cur, schema: str, table: str, new_table_keys: set[tuple[str, str]]) -> set[tuple[str, str]]:
    cur.execute(FK_DEPS_SQL, (schema, table))
    deps = set()
    for ref_schema, ref_table in cur.fetchall():
        key = (ref_schema, ref_table)
        if key in new_table_keys:
            deps.add(key)
    return deps


def topological_create_order(
    new_tables: set[tuple[str, str]], edges: list[tuple[tuple[str, str], tuple[str, str]]]
) -> list[tuple[str, str]]:
    """edges: (prereq, dependent) — prereq deve aparecer antes de dependent na saída."""
    indegree: dict[tuple[str, str], int] = {n: 0 for n in new_tables}
    adj: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for prereq, dependent in edges:
        if prereq in new_tables and dependent in new_tables:
            adj[prereq].append(dependent)
            indegree[dependent] += 1
    queue = [n for n in new_tables if indegree[n] == 0]
    order: list[tuple[str, str]] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in adj[n]:
            indegree[m] -= 1
            if indegree[m] == 0:
                queue.append(m)
    if len(order) != len(new_tables):
        leftover = [n for n in new_tables if n not in order]
        raise RuntimeError(
            "Ciclo ou dependência não resolvida na ordem de CREATE TABLE. "
            f"Sobrou: {leftover}. Revise FKs (ex.: autof-referência) ou use NOT VALID manualmente."
        )
    return order


def fetch_indexes(cur, schema: str, table: str) -> list[str]:
    cur.execute(INDEXES_SQL, (schema, table))
    return [row[1] + ";" for row in cur.fetchall()]


def detect_extensions_from_defaults(stmts: list[Statement]) -> list[str]:
    """Heurística: defaults comuns em DEV."""
    exts = []
    blob = "\n".join(s.text for s in stmts)
    if "uuid_generate_v4()" in blob or "uuid_generate_v4 (" in blob:
        exts.append('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    if "gen_random_uuid()" in blob:
        exts.append('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    return exts


def heuristic_warnings(stmts: list[Statement]) -> list[str]:
    w: list[str] = []
    for s in stmts:
        if s.kind == "drop_column":
            w.append(
                f"DROP COLUMN {s.meta.get('schema')}.{s.meta.get('table')}.{s.meta.get('column')} "
                "(pode falhar por dependências ou perder dados)."
            )
        if s.kind == "add_column" and s.meta.get("risk_nonempty"):
            w.append(
                f"ADD COLUMN NOT NULL sem DEFAULT em {s.meta.get('schema')}.{s.meta.get('table')}.{s.meta.get('column')}: "
                "falha se a tabela no PROD já tiver linhas (use etapa em duas fases ou DEFAULT temporário)."
            )
        if s.kind == "extension":
            w.append(
                f"CREATE EXTENSION ({s.text.strip()}): pode exigir superuser ou papel com privilégio para criar extensões."
            )
    return w


def classify_validation_error(msg: str) -> str:
    low = msg.lower()
    if "already exists" in low:
        return "provavelmente idempotência — objeto já existe no PROD"
    if "does not exist" in low:
        return "dependência ausente ou ordem incorreta"
    if "must be owner" in low or "permission denied" in low:
        return "permissão / owner"
    if "violates foreign key" in low or "foreign key constraint" in low:
        return "dados no PROD incompatíveis com FK (ou FK nova sobre dados existentes)"
    if "cannot drop column" in low or "depends on" in low:
        return "objeto dependente (índice, view, FK de outra tabela, etc.)"
    return "outro"


def validate_on_prod(prod_url: str, stmts: list[Statement], stop_on_first: bool) -> list[tuple[int, str, str, str]]:
    """
    Executa cada comando no PROD dentro de SAVEPOINTs sob uma transação, depois ROLLBACK total.
    Assim um comando inválido não impede de testar os seguintes.
    """
    errors: list[tuple[int, str, str, str]] = []
    conn = get_conn(prod_url)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")
        for i, s in enumerate(stmts):
            sp = f"sync_validate_{i}"
            try:
                cur.execute(f"SAVEPOINT {sp}")
                cur.execute(s.text)
                cur.execute(f"RELEASE SAVEPOINT {sp}")
            except Exception as ex:  # noqa: BLE001
                cur.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                msg = str(ex).strip()
                errors.append((i + 1, s.text[:500], msg, classify_validation_error(msg)))
                if stop_on_first:
                    break
        cur.execute("ROLLBACK")
    finally:
        cur.close()
        conn.close()
    return errors


def plan_sync(dev_url: str, prod_url: str) -> list[Statement]:
    dev = get_conn(dev_url)
    prod = get_conn(prod_url)
    try:
        dc = dev.cursor()
        pc = prod.cursor()
        dev_schemas = fetch_schemas(dc)
        prod_schemas = fetch_schemas(pc)
        stmts: list[Statement] = []

        for schema in dev_schemas:
            if schema not in prod_schemas:
                stmts.append(
                    Statement(
                        "create_schema",
                        f"CREATE SCHEMA {qi(dev, schema)};",
                        {"schema": schema},
                    )
                )

        dev_tables: dict[str, set[str]] = {}
        prod_tables: dict[str, set[str]] = {}
        for schema in dev_schemas:
            dev_tables[schema] = fetch_tables(dc, schema)
            prod_tables[schema] = fetch_tables(pc, schema) if schema in prod_schemas else set()

        new_tables: set[tuple[str, str]] = set()
        for schema in dev_schemas:
            for t in dev_tables[schema] - prod_tables.get(schema, set()):
                new_tables.add((schema, t))

        edges: list[tuple[tuple[str, str], tuple[str, str]]] = []
        for schema, table in new_tables:
            deps = fetch_new_table_fk_deps(dc, schema, table, new_tables)
            for ref_schema, ref_table in deps:
                edges.append(((ref_schema, ref_table), (schema, table)))

        create_order = topological_create_order(new_tables, edges)

        for schema, table in create_order:
            ddl = build_create_table(dev, dc, schema, table)
            stmts.append(Statement("create_table", ddl, {"schema": schema, "table": table}))

        for schema, table in create_order:
            for fk in fetch_fk_alters(dev, dc, schema, table):
                stmts.append(Statement("add_fk", fk, {"schema": schema, "table": table}))

        for schema in dev_schemas:
            common = dev_tables[schema] & prod_tables.get(schema, set())
            for table in sorted(common):
                dcols = {c["name"]: c for c in fetch_columns(dc, schema, table)}
                pcols = {c["name"] for c in fetch_columns(pc, schema, table)}
                for colname in sorted(set(dcols) - pcols):
                    col = dcols[colname]
                    risk = (
                        col["not_null"]
                        and not col["default_expr"]
                        and not (col["identity"] or "")
                        and (col.get("generated") or "") != "s"
                    )
                    stmts.append(
                        Statement(
                            "add_column",
                            build_add_column(dev, schema, table, col),
                            {
                                "schema": schema,
                                "table": table,
                                "column": colname,
                                "risk_nonempty": risk,
                            },
                        )
                    )

        for schema in dev_schemas:
            common = dev_tables[schema] & prod_tables.get(schema, set())
            for table in sorted(common):
                dcols_set = {c["name"] for c in fetch_columns(dc, schema, table)}
                pcols = {c["name"]: c for c in fetch_columns(pc, schema, table)}
                for colname in sorted(set(pcols) - dcols_set):
                    stmts.append(
                        Statement(
                            "drop_column",
                            (
                                f"ALTER TABLE {qi(dev, schema)}.{qi(dev, table)} "
                                f"DROP COLUMN {qi(dev, colname)};"
                            ),
                            {"schema": schema, "table": table, "column": colname},
                        )
                    )

        for schema, table in create_order:
            for idef in fetch_indexes(dc, schema, table):
                stmts.append(Statement("create_index", idef, {"schema": schema, "table": table}))

        ext_stmts = [Statement("extension", e, {}) for e in detect_extensions_from_defaults(stmts)]
        return ext_stmts + stmts
    finally:
        dev.close()
        prod.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Espelha esquema DEV -> PROD (public + city_*).")
    parser.add_argument(
        "--dev-url",
        "--dev_url",
        default=os.environ.get("DATABASE_URL_DEV"),
        help="URL do banco DEV",
    )
    parser.add_argument(
        "--prod-url",
        "--prod_url",
        default=os.environ.get("DATABASE_URL_PROD"),
        help="URL do banco PROD",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Opcional: deixa explícito o modo só simulação (é o padrão quando --execute não é usado).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Aplica no PROD (sem isso, só imprime SQL e simula no PROD com ROLLBACK).",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Só imprime SQL e avisos; não conecta ao PROD para simulação.",
    )
    parser.add_argument(
        "--stop-on-first-error",
        action="store_true",
        help="Na validação, parar no primeiro erro (padrão: tentar todos e acumular).",
    )
    parser.add_argument(
        "--out-sql",
        default="",
        help="Opcional: caminho para salvar o SQL gerado em um arquivo (.sql).",
    )
    args = parser.parse_args()
    dev_url = args.dev_url
    prod_url = args.prod_url
    if not dev_url or not prod_url:
        print("Informe --dev-url e --prod-url ou DATABASE_URL_DEV / DATABASE_URL_PROD.", file=sys.stderr)
        return 2

    print("Planejando diff DEV -> PROD ...")
    try:
        stmts = plan_sync(dev_url, prod_url)
    except Exception as ex:  # noqa: BLE001
        print(f"Erro ao planejar: {ex}", file=sys.stderr)
        return 1

    if not stmts:
        print("Nada a fazer: PROD já contém os mesmos objetos rastreados (tabelas/colunas básicas).")
        return 0

    print(f"\n--- SQL gerado ({len(stmts)} comandos) ---\n")
    sql_lines: list[str] = []
    for i, s in enumerate(stmts, 1):
        header = f"-- [{i}] {s.kind}"
        sql_lines.append(header)
        sql_lines.append(s.text)
        sql_lines.append("")
        print(header)
        print(s.text)
        print()

    if args.out_sql:
        try:
            with open(args.out_sql, "w", encoding="utf-8") as f:
                f.write("\n".join(sql_lines).rstrip() + "\n")
            print(f"SQL salvo em: {args.out_sql}\n")
        except Exception as ex:  # noqa: BLE001
            print(f"Falha ao salvar --out-sql em '{args.out_sql}': {ex}", file=sys.stderr)

    warns = heuristic_warnings(stmts)
    if warns:
        print("--- Avisos heurísticos (risco / dados) ---")
        for w in warns:
            print(f" * {w}")
        print()

    if args.execute:
        print("--- Aplicando no PROD (COMMIT por comando) ---")
        conn = get_conn(prod_url)
        conn.autocommit = True
        cur = conn.cursor()
        try:
            for i, s in enumerate(stmts, 1):
                try:
                    cur.execute(s.text)
                    print(f"OK [{i}/{len(stmts)}] {s.kind}")
                except Exception as ex:  # noqa: BLE001
                    print(f"FALHA [{i}] {s.kind}: {ex}", file=sys.stderr)
                    return 1
        finally:
            cur.close()
            conn.close()
        print("Concluído.")
        return 0

    if args.no_validate:
        print("--- Validação omitida (--no-validate); revise o SQL antes de usar --execute. ---")
        return 0

    print("--- Validação no PROD (BEGIN + SAVEPOINT por comando ... ROLLBACK) ---")
    errs = validate_on_prod(prod_url, stmts, stop_on_first=args.stop_on_first_error)
    if not errs:
        print("Nenhum erro do PostgreSQL na simulação.")
    else:
        print(f"Encontrados {len(errs)} erro(s) na simulação:\n")
        for idx, preview, msg, bucket in errs:
            print(f"[{idx}] classe: {bucket}")
            print(f"    SQL (trecho): {preview[:320]}...")
            print(f"    Erro: {msg}\n")
    print("(Nenhuma alteração persistida — transação revertida.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
