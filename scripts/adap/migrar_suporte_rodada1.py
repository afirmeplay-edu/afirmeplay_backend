# -*- coding: utf-8 -*-
"""
Migração dos alunos de Suporte 1, 2 e 3 para a subturma ADAP 1, 2 e 3 da turma regular.

Simulação por padrão (não grava). Lógica em app/services/adap_migracao_suporte.py.
--rodada (padrão 2) só muda o nome do log e o motivo gravado na marca de descarte.

Uso (a partir de afirmeplay_backend, com venv e app/.env):

  # simulação do município (todas as escolas)
  python scripts/adap/migrar_suporte_rodada1.py --schema city_xxxx
  # simulação de uma escola (id ou parte do nome)
  python scripts/adap/migrar_suporte_rodada1.py --schema city_xxxx --escola "NOME DA ESCOLA"
  # gravação (exige a escolha do questionário)
  python scripts/adap/migrar_suporte_rodada1.py --schema city_xxxx --escola "NOME DA ESCOLA" \
      --write --questionario-quem-respondeu nao-criar
  # reversão pelo log (simulação; acrescente --write para aplicar)
  python scripts/adap/migrar_suporte_rodada1.py --reverter C:/.../adap_rodada1_..._gravacao_....json

Em banco de produção, --write também exige --confirmar-producao <mesmo schema>.
Os logs ficam em ~/afirmeplay_backups/adap_migracao (fora do repositório).
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _bootstrap():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)
    os.environ["ENABLE_SCHEDULER"] = "0"


def _print_resumo(result: dict) -> None:
    banco = result.get("banco", {})
    print(f"[{result['modo'].upper()}] schema={result['schema']} banco={banco.get('host')}/{banco.get('database')}"
          + (f" escola={result['escola_filtro']}" if result.get("escola_filtro") else ""))
    if "resumo" in result and "elegiveis" in result["resumo"]:
        r = result["resumo"]
        print(f"  elegíveis: {r['elegiveis']} em {r['escolas']} escola(s) | por tipo: {r['por_tipo']}")
        print(f"  por tipo e nível: {r['por_tipo_nivel']}")
        print(f"  subturmas de destino: {r['subturmas_destino']} em {r['turmas_destino']} turma(s) | "
              f"cadastros regulares a desvincular: {r['cadastros_regulares_a_desvincular']} | "
              f"cadastros de Suporte a desvincular (fica o regular): {r.get('cadastros_suporte_a_desvincular', 0)}")
        print(f"  excluídos: {r['excluidos']} | por motivo: {r['excluidos_por_motivo']}")
        q = r["questionario_previsto"]
        print(f"  questionário: {q['alunos_com_formulario_novo']} aluno(s) ganhariam formulário novo; "
              f"{q['alunos_que_ja_responderam_com_formulario_novo']} já responderam outro | "
              f"destinatários novos: criar={q['opcao_criar']} nao-criar={q['opcao_nao_criar']}")
        m = r.get("questionario_mover") or {}
        print(f"  questionário do cadastro descartado: {m.get('alunos', 0)} aluno(s); passam para o mantido "
              f"{m.get('destinatarios', 0)} destinatário(s) e {m.get('respostas', 0)} resposta(s); "
              f"pendentes do mantido removidos: {m.get('removidos_do_mantido', 0)}; "
              f"ficam no descartado: {m.get('ficam_no_descartado', 0)}")
        print("  por escola (em Suporte 1/2/3 | migrariam | ficam de fora):")
        for escola, t in r.get("por_escola_nivel", {}).items():
            extra = f" +{t['nivel_indefinido']} sem nível" if t.get("nivel_indefinido") else ""
            print(f"    - {escola}: {t['suporte_1']}/{t['suporte_2']}/{t['suporte_3']}{extra} | "
                  f"{t['migrariam']} | {t['ficam_de_fora']}")
        print(f"  turmas de Suporte depois: {r.get('turmas_suporte_vazias_depois', 0)} vazia(s), "
              f"{r.get('turmas_suporte_com_alunos_depois', 0)} ainda com alunos")
    if result["modo"] == "gravacao":
        if "gravados" in result:
            print(f"  gravados: {result['gravados']} | subturmas criadas: {len(result.get('subturmas_criadas', []))} "
                  f"| caches: {result.get('caches')}")
        else:
            print(f"  reversão: {result.get('resumo')} | subturmas: {result.get('subturmas')} | caches: {result.get('caches')}")
    elif "subturmas" in result:
        print(f"  reversão (simulação): {result.get('resumo')} | subturmas: {result.get('subturmas')}")
    if result.get("erros"):
        print(f"  ERROS: {len(result['erros'])}")
        for e in result["erros"]:
            print(f"    - {e}")
    print(f"  log: {result['log']}")


def main(argv=None) -> int:
    _bootstrap()
    parser = argparse.ArgumentParser(description="Migra alunos de Suporte 1, 2 e 3 para a subturma ADAP.")
    parser.add_argument("--schema", help="Schema city_… do município (obrigatório, exceto na reversão).")
    parser.add_argument("--escola", help="Id ou parte do nome de uma escola (opcional; sem ela, todas).")
    parser.add_argument("--rodada", type=int, choices=[1, 2], default=2,
                        help="Número da rodada (nome do log e motivo da marca de descarte). Padrão: 2.")
    parser.add_argument("--write", action="store_true", help="Grava. Sem esta flag, só simula.")
    parser.add_argument("--questionario-quem-respondeu", choices=["criar", "nao-criar"],
                        help="Obrigatório no --write: criar ou não o destinatário novo para quem já respondeu.")
    parser.add_argument("--incluir-questionario-descartado", action="store_true",
                        help="Inclui quem respondeu o questionário só no cadastro descartado (move as respostas).")
    parser.add_argument("--excluir-aluno", action="append", default=[], metavar="STUDENT_ID",
                        help="Deixa este aluno (id do cadastro de Suporte) fora da rodada. Pode repetir.")
    parser.add_argument("--reverter", metavar="LOG", help="Desfaz a gravação descrita neste log.")
    parser.add_argument("--forcar", action="store_true", help="Na reversão, reverte mesmo se o estado mudou.")
    parser.add_argument("--log-dir", help="Pasta dos logs (fora do repositório).")
    parser.add_argument("--confirmar-producao", metavar="SCHEMA", help="Necessário para gravar em produção.")
    parser.add_argument("--json", action="store_true", help="Imprime o resultado completo em JSON.")
    args = parser.parse_args(argv)

    from app import create_app
    from app.services.adap_migracao_suporte import MigracaoError, executar, reverter
    from app.utils.tenant_middleware import set_search_path

    app = create_app()
    with app.app_context():
        try:
            if args.reverter:
                with open(args.reverter, encoding="utf-8") as fh:
                    schema = json.load(fh).get("schema")
                set_search_path(schema)
                result = reverter(log_path=args.reverter, write=args.write, forcar=args.forcar,
                                  log_dir=args.log_dir, confirmar_producao=args.confirmar_producao)
            else:
                if not args.schema:
                    parser.error("--schema é obrigatório")
                set_search_path(args.schema)
                result = executar(schema=args.schema, escola=args.escola, write=args.write,
                                  questionario=args.questionario_quem_respondeu, log_dir=args.log_dir,
                                  confirmar_producao=args.confirmar_producao,
                                  incluir_questionario_descartado=args.incluir_questionario_descartado,
                                  excluir_alunos=set(args.excluir_aluno), rodada=args.rodada)
        except MigracaoError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        _print_resumo(result)
    return 1 if result.get("erros") else 0


if __name__ == "__main__":
    raise SystemExit(main())
