#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Atualiza password_hash em public.users para alunos de um município,
usando a senha em texto plano registrada em {schema}.student_password_log.

Somente usuários com role ALUNO e city_id igual ao informado são alterados.
Para cada user_id, usa a linha mais recente do log (ORDER BY created_at DESC).

Uso (na raiz do projeto, com venv ativo e DATABASE_URL no app/.env):
    python scripts/rehash_student_passwords_from_log.py --city-id <UUID_DA_CIDADE>
    python scripts/rehash_student_passwords_from_log.py --city-id <UUID> --dry-run
    python scripts/rehash_student_passwords_from_log.py --user-id <UUID_EM_PUBLIC.USERS>

Não altera a tabela student_password_log; apenas public.users.password_hash.
O hash gerado é o mesmo do backend: pbkdf2:sha256:100000 (via app.utils.auth.hash_password).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import text

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from app import create_app, db
from app.models.city import City
from app.models.user import User, RoleEnum
from app.utils.auth import hash_password
from app.utils.tenant_middleware import city_id_to_schema_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_latest_plaintext_per_user(schema: str):
    """
    Uma linha por user_id: senha plaintext da entrada mais recente no log.
    """
    sql = text(
        f"""
        SELECT DISTINCT ON (spl.user_id) spl.user_id, spl.password
        FROM "{schema}".student_password_log spl
        WHERE spl.user_id IS NOT NULL
        ORDER BY spl.user_id, spl.created_at DESC NULLS LAST
        """
    )
    return db.session.execute(sql).fetchall()


def fetch_latest_plaintext_for_user(schema: str, user_id: str):
    sql = text(
        f"""
        SELECT password
        FROM "{schema}".student_password_log
        WHERE user_id = :user_id
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
        """
    )
    row = db.session.execute(sql, {"user_id": user_id}).fetchone()
    return row[0] if row else None


def run_single_user(user_id: str, dry_run: bool) -> None:
    db.session.execute(text("SET search_path TO public"))

    user = db.session.get(User, user_id)
    if not user:
        logger.error("Usuário não encontrado em public.users: %s", user_id)
        sys.exit(1)

    if user.role != RoleEnum.ALUNO:
        logger.error(
            "Usuário %s não é aluno (role=%s). Abortando.",
            user_id,
            getattr(user.role, "value", user.role),
        )
        sys.exit(1)

    if not user.city_id:
        logger.error("Usuário %s sem city_id; não é possível resolver o schema tenant.", user_id)
        sys.exit(1)

    city_id = str(user.city_id)
    city = db.session.get(City, city_id)
    if not city:
        logger.error("Cidade %s (users.city_id) não existe em public.city.", city_id)
        sys.exit(1)

    schema = city_id_to_schema_name(city_id)
    logger.info("Schema tenant: %s (city_id=%s)", schema, city_id)

    try:
        plain_password = fetch_latest_plaintext_for_user(schema, user_id)
    except Exception as exc:
        logger.error("Falha ao ler %s.student_password_log: %s", schema, exc)
        sys.exit(1)

    if not plain_password or not str(plain_password).strip():
        logger.error(
            "Nenhuma senha em texto plano no log para user_id=%s em %s.student_password_log.",
            user_id,
            schema,
        )
        sys.exit(1)

    new_hash = hash_password(str(plain_password))

    if dry_run:
        logger.info(
            "[dry-run] Atualizaria password_hash para user_id=%s (%s)",
            user_id,
            user.email or user.registration or "",
        )
        return

    try:
        user.password_hash = new_hash
        db.session.add(user)
        db.session.commit()
        logger.info(
            "Atualizado user_id=%s (%s)",
            user_id,
            user.email or user.registration or "",
        )
    except Exception as exc:
        db.session.rollback()
        logger.exception("Erro ao persistir: %s", exc)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-hash de senhas de alunos a partir de student_password_log (por city_id)."
    )
    parser.add_argument(
        "--city-id",
        default=None,
        help="UUID da cidade (public.city.id): processa todos os alunos do município",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="UUID em public.users: processa apenas esse usuário (deve ser aluno)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista o que seria feito sem atualizar o banco",
    )
    args = parser.parse_args()

    has_city = bool(args.city_id and str(args.city_id).strip())
    has_user = bool(args.user_id and str(args.user_id).strip())
    if has_city == has_user:
        parser.error("Informe exatamente um: --city-id OU --user-id")

    app = create_app()
    with app.app_context():
        if has_user:
            run_single_user(str(args.user_id).strip(), args.dry_run)
            if args.dry_run:
                logger.info("Execute sem --dry-run para gravar.")
            return

        city_id = str(args.city_id).strip()

        db.session.execute(text("SET search_path TO public"))

        city = db.session.get(City, city_id)
        if not city:
            logger.error("Cidade não encontrada em public.city para city_id=%s", city_id)
            sys.exit(1)

        schema = city_id_to_schema_name(city_id)
        logger.info("Schema tenant: %s", schema)

        try:
            rows = fetch_latest_plaintext_per_user(schema)
        except Exception as exc:
            logger.error(
                "Falha ao ler %s.student_password_log (schema existe?): %s",
                schema,
                exc,
            )
            sys.exit(1)

        logger.info("Linhas distintas por user_id no log: %d", len(rows))

        updated = 0
        skipped_not_student = 0
        skipped_wrong_city = 0
        skipped_no_user = 0
        skipped_empty_password = 0
        errors = 0

        for user_id, plain_password in rows:
            if not plain_password or not str(plain_password).strip():
                skipped_empty_password += 1
                logger.warning("user_id=%s: senha vazia no log; ignorado", user_id)
                continue

            user = db.session.get(User, user_id)
            if not user:
                skipped_no_user += 1
                logger.warning("user_id=%s: não existe em public.users; ignorado", user_id)
                continue

            if user.role != RoleEnum.ALUNO:
                skipped_not_student += 1
                logger.info(
                    "user_id=%s: role=%s (não é aluno); ignorado",
                    user_id,
                    getattr(user.role, "value", user.role),
                )
                continue

            uid_city = str(user.city_id) if user.city_id else None
            if uid_city != city_id:
                skipped_wrong_city += 1
                logger.info(
                    "user_id=%s: city_id do user=%s != %s; ignorado",
                    user_id,
                    uid_city,
                    city_id,
                )
                continue

            new_hash = hash_password(str(plain_password))

            if args.dry_run:
                logger.info(
                    "[dry-run] Atualizaria user_id=%s (%s)",
                    user_id,
                    user.email or user.registration or "",
                )
                updated += 1
                continue

            try:
                user.password_hash = new_hash
                db.session.add(user)
                db.session.commit()
                updated += 1
                logger.info(
                    "Atualizado user_id=%s (%s)",
                    user_id,
                    user.email or user.registration or "",
                )
            except Exception as exc:
                errors += 1
                db.session.rollback()
                logger.exception("Erro ao persistir user_id=%s: %s", user_id, exc)

        logger.info(
            "Resumo: atualizados=%d dry_run=%s | ignorados: não_aluno=%d city_diferente=%d sem_user=%d senha_vazia=%d | erros=%d",
            updated,
            args.dry_run,
            skipped_not_student,
            skipped_wrong_city,
            skipped_no_user,
            skipped_empty_password,
            errors,
        )
        if args.dry_run:
            logger.info("Execute sem --dry-run para gravar as alterações.")


if __name__ == "__main__":
    main()
