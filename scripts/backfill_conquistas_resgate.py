#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para marcar como resgatadas as conquistas já atingidas por alunos
que existiam antes do sistema de conquistas ser criado.

Para cada aluno, calcula as conquistas atuais (pelas métricas já existentes),
e para cada medalha já alcançada que ainda não foi resgatada: credita as moedas
e adiciona a chave em User.traits["achievements_redeemed"]. Assim as conquistas
aparecem como "completas" (desbloqueadas) e o resgate fica registrado.

Uso (na raiz do projeto):
    python scripts/backfill_conquistas_resgate.py
    python scripts/backfill_conquistas_resgate.py --dry-run   # Só mostra o que seria feito
    python scripts/backfill_conquistas_resgate.py --limit 100  # Limita a 100 alunos
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import text

from app import create_app, db
from app.models.city import City
from app.models.student import Student
from app.models.user import User
from app.utils.tenant_middleware import city_id_to_schema_name
from app.services.achievement_service import (
    get_conquistas,
    get_coin_value_for_medal,
    MEDAL_ORDER,
)
from app.balance.services.coin_service import CoinService
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def backfill_student(student_id: str, dry_run: bool) -> dict:
    """
    Para um aluno: obtém conquistas atuais, resgata (credita moedas e marca em traits)
    todas as medalhas já alcançadas que ainda não estavam resgatadas.
    Retorna {"student_id", "credits": [...], "total_coins", "error"}.
    """
    result = {"student_id": student_id, "credits": [], "total_coins": 0, "error": None}
    try:
        student = Student.query.get(student_id)
        if not student:
            result["error"] = "Aluno não encontrado"
            return result

        user_model = User.query.get(student.user_id) if student.user_id else None
        if not user_model:
            result["error"] = "Usuário do aluno não encontrado"
            return result

        traits = dict(user_model.traits) if user_model.traits and isinstance(user_model.traits, dict) else {}
        redeemed_list = list(traits.get("achievements_redeemed") or [])

        data = get_conquistas(student_id, redeemed_keys=redeemed_list)
        added_any = False

        for c in data.get("conquistas", []):
            achievement_id = c.get("id")
            medalha_atual = c.get("medalha_atual")
            if not medalha_atual:
                continue

            try:
                idx_atual = MEDAL_ORDER.index(medalha_atual)
            except ValueError:
                continue

            for i in range(idx_atual + 1):
                medal = MEDAL_ORDER[i]
                chave = f"{achievement_id}_{medal}"
                if chave in redeemed_list:
                    continue

                valor = get_coin_value_for_medal(achievement_id, medal)
                if valor is None or valor <= 0:
                    continue

                if dry_run:
                    result["credits"].append({"chave": chave, "moedas": valor})
                    result["total_coins"] += valor
                    added_any = True
                    continue

                CoinService.credit_coins(
                    student_id,
                    valor,
                    reason="achievement_redeem",
                    description=chave,
                )
                redeemed_list.append(chave)
                result["credits"].append({"chave": chave, "moedas": valor})
                result["total_coins"] += valor
                added_any = True
                logger.info("  + %s: %d moedas", chave, valor)

        if added_any and not dry_run:
            traits["achievements_redeemed"] = redeemed_list
            user_model.traits = traits
            db.session.commit()

    except Exception as e:
        logger.exception("Erro no aluno %s", student_id)
        result["error"] = str(e)
        db.session.rollback()

    return result


def main():
    parser = argparse.ArgumentParser(description="Backfill de resgate de conquistas para alunos já existentes")
    parser.add_argument("--dry-run", action="store_true", help="Não gravar; apenas mostrar o que seria feito")
    parser.add_argument("--limit", type=int, default=None, help="Limitar número de alunos processados")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        # Tabela student está nos schemas tenant (city_xxx), não em public. Buscar cidades em public.
        db.session.execute(text("SET search_path TO public"))
        cities = City.query.all()
        if not cities:
            logger.warning("Nenhuma cidade encontrada em public.city. Nada a processar.")
            return

        total_alunos = 0
        total_moedas = 0
        alunos_com_resgate = 0
        erros = 0
        limit_restante = args.limit

        logger.info("Encontradas %d cidade(s). Processando alunos por schema tenant.", len(cities))

        for city in cities:
            schema = city_id_to_schema_name(city.id)
            # search_path: schema do tenant primeiro (student, evaluation_results, etc.), public depois (users)
            db.session.execute(text(f'SET search_path TO "{schema}", public'))
            try:
                students = Student.query.all()
            except Exception as e:
                logger.warning("Schema %s: sem tabela student ou erro ao listar: %s", schema, e)
                continue

            if args.limit is not None:
                if limit_restante <= 0:
                    break
                students = students[:limit_restante]
                limit_restante -= len(students)

            total_alunos += len(students)
            logger.info("Schema %s: %d aluno(s)", schema, len(students))

            for i, student in enumerate(students, 1):
                if i % 50 == 0 or i == 1:
                    logger.info("  Aluno %d/%d: %s", i, len(students), student.id)

                # Garantir search_path antes de cada aluno (commit anterior pode ter devolvido outra conexão ao pool)
                db.session.execute(text(f'SET search_path TO "{schema}", public'))
                r = backfill_student(student.id, dry_run=args.dry_run)
                if r["error"]:
                    erros += 1
                    logger.warning("  Erro: %s", r["error"])
                    continue
                if r["credits"]:
                    alunos_com_resgate += 1
                    total_moedas += r["total_coins"]
                    if args.dry_run:
                        for cred in r["credits"]:
                            logger.info("  [dry-run] + %s: %d moedas", cred["chave"], cred["moedas"])

        logger.info(
            "Fim: %d aluno(s) processado(s), %d com resgate aplicado, %d moedas creditadas no total, %d erro(s).",
            total_alunos,
            alunos_com_resgate,
            total_moedas,
            erros,
        )
        if args.dry_run:
            logger.info("Execute sem --dry-run para aplicar as alterações.")


if __name__ == "__main__":
    main()
