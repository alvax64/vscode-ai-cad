"""Shared ForgeCAD error types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ErrorPayload:
    """Stable machine-readable error payload."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "recoverable": self.recoverable,
        }


class ForgeCADError(Exception):
    """Exception carrying the service error shape."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
    ) -> None:
        super().__init__(message)
        self.payload = ErrorPayload(
            code=code,
            message=message,
            details=details or {},
            recoverable=recoverable,
        )

    @property
    def code(self) -> str:
        return self.payload.code

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.payload.to_dict()}
