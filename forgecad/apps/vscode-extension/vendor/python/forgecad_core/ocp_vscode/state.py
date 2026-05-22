"""In-memory state compatibility for service-side legacy imports."""

from __future__ import annotations

from typing import Any

_SERVICES: dict[str, str] = {}


def get_config_file() -> str:
    return "<forgecad-service-memory>"


def update_state(port: int | str, connectionFile: str) -> None:
    _SERVICES[str(port)] = connectionFile


def add_port(port: int | str) -> None:
    _SERVICES[str(port)] = ""


def del_port(port: int | str) -> None:
    _SERVICES.pop(str(port), None)


def get_ports() -> list[str]:
    return list(_SERVICES)


def atomic_operation(callback: Any) -> Any:
    return callback({"version": 2, "services": _SERVICES})


__all__ = [
    "add_port",
    "atomic_operation",
    "del_port",
    "get_config_file",
    "get_ports",
    "update_state",
]
