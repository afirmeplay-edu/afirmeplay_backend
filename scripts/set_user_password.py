#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Define password_hash em public.users a partir de e-mail e senha em texto plano.
Usa o mesmo algoritmo do backend (hash_password → pbkdf2:sha256:100000).

Uso (na raiz do projeto):
    # Senha via variável de ambiente (evita aparecer no histórico do shell):
    set INNOVAPLAY_SET_PASSWORD=sua_senha_aqui
    python scripts/set_user_password.py --email aluno@exemplo.com

    # Ou passando na linha de comando (fica no histórico do terminal):
    python scripts/set_user_password.py --email aluno@exemplo.com --password "sua_senha"

    python scripts/set_user_password.py --email aluno@exemplo.com --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import text

from app import create_app, db
from app.models.user import User, RoleEnum
from app.utils.auth import hash_password

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ENV_PASSWORD = "INNOVAPLAY_SET_PASSWORD"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Atualiza a senha (hash) de um usuário em public.users pelo e-mail."
    )
    parser.add_argument("--email", required=True, help="E-mail cadastrado em users.email")
    parser.add_argument(
        "--password",
        default=None,
        help=f"Senha em texto plano (se omitido, usa a variável de ambiente {ENV_PASSWORD})",
    )
    parser.add_argument(
        "--allow-non-student",
        action="store_true",
        help="Permite alterar mesmo se o usuário não for aluno (por padrão só aluno)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Não grava no banco")
    args = parser.parse_args()

    plain = args.password if args.password is not None else os.environ.get(ENV_PASSWORD)
    if not plain or not str(plain).strip():
        logger.error(
            "Defina a senha com --password ou com a variável de ambiente %s.",
            ENV_PASSWORD,
        )
        sys.exit(1)

    email = str(args.email).strip().lower()

    app = create_app()
    with app.app_context():
        db.session.execute(text("SET search_path TO public"))

        user = User.query.filter(db.func.lower(User.email) == email).first()
        if not user:
            user = User.query.filter_by(email=args.email.strip()).first()
        if not user:
            logger.error("Nenhum usuário com e-mail: %s", args.email)
            sys.exit(1)

        if not args.allow_non_student and user.role != RoleEnum.ALUNO:
            logger.error(
                "Usuário %s não é aluno (role=%s). Use --allow-non-student para forçar.",
                user.id,
                getattr(user.role, "value", user.role),
            )
            sys.exit(1)

        new_hash = hash_password(str(plain))

        if args.dry_run:
            logger.info(
                "[dry-run] Atualizaria senha de user_id=%s email=%s",
                user.id,
                user.email,
            )
            return

        user.password_hash = new_hash
        db.session.add(user)
        db.session.commit()
        logger.info("Senha atualizada para user_id=%s (%s)", user.id, user.email)


if __name__ == "__main__":
    main()
