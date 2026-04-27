from __future__ import annotations

import logging
from typing import Any


class BaseDeletionService:
    """
    Base para deleções em fases (tenant/public), com logging e helpers comuns.

    Regras:
    - use bulk deletes sempre que possível
    - commits em fases: tenant primeiro, depois public
    """

    entity: str = "entity"

    def __init__(self, session, logger: logging.Logger | None = None):
        self.session = session
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def log(self, msg: str, **kwargs: Any) -> None:
        if kwargs:
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
            self.logger.info("[%s] %s %s", self.__class__.__name__, msg, extras)
        else:
            self.logger.info("[%s] %s", self.__class__.__name__, msg)

    def log_error(self, msg: str, **kwargs: Any) -> None:
        if kwargs:
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
            self.logger.error("[%s][ERROR] %s %s", self.__class__.__name__, msg, extras)
        else:
            self.logger.error("[%s][ERROR] %s", self.__class__.__name__, msg)

    def commit(self, phase: str) -> None:
        try:
            self.session.commit()
            self.log(f"commit {phase} success")
        except Exception:
            self.session.rollback()
            self.log_error(f"commit {phase} failed", exc_info=True)
            raise

