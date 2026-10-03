# -*- coding: utf-8 -*-
"""
Preenche test.paired_regular_test_id (ADAP → regular) em UM schema municipal.

Simulação por padrão (não grava). Exige --write para persistir, e só pares únicos
ainda sem vínculo.

Uso (a partir de afirmeplay_backend, com venv e .env):

  python scripts/pair_adap_regular_tests.py --schema city_xxxx
  python scripts/pair_adap_regular_tests.py --schema city_xxxx --write
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _bootstrap():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)


def main(argv=None) -> int:
    _bootstrap()
    parser = argparse.ArgumentParser(
        description="Pareia provas ADAP com a regular correspondente (um município)."
    )
    parser.add_argument(
        "--schema",
        required=True,
        help="Schema city_… do município (obrigatório; nunca todos de uma vez).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Grava pares únicos novos. Sem esta flag, só simula.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime o relatório em JSON.",
    )
    args = parser.parse_args(argv)

    schema = str(args.schema).strip()
    if not schema.startswith("city_"):
        print("Erro: --schema deve começar com city_", file=sys.stderr)
        return 2

    from app import create_app
    from app.services.adap_test_pairing_fill import run_pairing_for_schema
    from app.utils.tenant_middleware import set_search_path

    app = create_app()
    with app.app_context():
        set_search_path(schema)
        summary = run_pairing_for_schema(schema=schema, write=bool(args.write))

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        modo = "GRAVAÇÃO" if args.write else "SIMULAÇÃO"
        print(f"[{modo}] schema={summary['schema']}")
        print(
            f"  par_unico={summary['par_unico']}  mais_de_um={summary['mais_de_um']}  "
            f"nenhum={summary['nenhum']}  ja_vinculados={summary['ja_vinculados']}  "
            f"a_gravar_ou_gravados={summary['gravados_ou_a_gravar']}"
        )
        for prop in summary["propostas"]:
            cands = ", ".join(t for _id, t in prop["candidates"]) or "(nenhum)"
            flag = ""
            if prop["already_paired"]:
                flag = " [já vinculado — não sobrescreve]"
            elif prop["will_write"]:
                flag = " [gravar]" if args.write else " [seria gravado]"
            print(
                f"  - [{prop['status']}] {prop['adap_title'][:70]} → {cands}{flag}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
