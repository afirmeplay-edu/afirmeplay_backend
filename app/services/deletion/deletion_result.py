from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeletionResult:
    success: bool
    entity: str
    id: str
    deleted: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "entity": self.entity,
            "id": self.id,
            "deleted": self.deleted,
            "warnings": self.warnings,
        }

