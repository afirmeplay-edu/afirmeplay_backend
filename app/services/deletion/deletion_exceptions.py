from __future__ import annotations


class DeletionError(Exception):
    """Erro base para deleções."""


class EntityNotFoundError(DeletionError):
    """Entidade não encontrada."""


class PermissionDeniedError(DeletionError):
    """Sem permissão para executar deleção."""


class PhaseCommitError(DeletionError):
    """Erro ao commitar uma fase."""


