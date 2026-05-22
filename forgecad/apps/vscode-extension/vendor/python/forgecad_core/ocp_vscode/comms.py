"""Service-side compatibility shims for legacy OCP CAD Viewer comms imports."""

from __future__ import annotations

import enum
import os
from typing import Any


class MessageType(enum.IntEnum):
    DATA = 1
    COMMAND = 2
    UPDATES = 3
    LISTEN = 4
    BACKEND = 5
    BACKEND_RESPONSE = 6
    CONFIG = 7


CMD_PORT = 3939
CMD_HOST = "127.0.0.1"


def is_pytest() -> bool:
    return os.environ.get("OCP_VSCODE_PYTEST") == "1"


def set_port(port: int, host: str = "127.0.0.1") -> None:
    global CMD_PORT, CMD_HOST  # pylint: disable=global-statement
    CMD_PORT = int(port)
    CMD_HOST = host


def get_port() -> int:
    return CMD_PORT


def get_host() -> str:
    return CMD_HOST


def port_check(_: int) -> bool:
    return True


def default(obj: Any) -> Any:
    if isinstance(obj, enum.Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def send_data(data: Any, **_: Any) -> Any:
    return data


def send_config(config: Any, **_: Any) -> Any:
    return config


def send_command(data: Any, **_: Any) -> dict[str, Any]:
    if data == "status" or (isinstance(data, dict) and data.get("type") == "status"):
        return {"command": "status", "text": {"_splash": False}}
    if data == "config" or (isinstance(data, dict) and data.get("type") == "config"):
        return {"_splash": False}
    return {}


def send_backend(data: Any, **_: Any) -> Any:
    return data


def send_response(data: Any, **_: Any) -> Any:
    return data


def listener(*_: Any, **__: Any) -> None:
    return None


__all__ = [
    "MessageType",
    "default",
    "get_host",
    "get_port",
    "is_pytest",
    "listener",
    "port_check",
    "send_backend",
    "send_command",
    "send_config",
    "send_data",
    "send_response",
    "set_port",
]
