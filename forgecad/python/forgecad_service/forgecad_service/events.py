"""In-memory service event log."""

from __future__ import annotations

from collections import deque
from itertools import count
from typing import Any

from forgecad_core.models import ServiceEvent


class EventLog:
    def __init__(self, max_events: int = 500) -> None:
        self._events: deque[ServiceEvent] = deque(maxlen=max_events)
        self._counter = count(1)

    def emit(
        self,
        event_type: str,
        *,
        session_id: str | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ServiceEvent:
        event = ServiceEvent(
            event_id=f"evt_{next(self._counter):08d}",
            event_type=event_type,
            session_id=session_id,
            model_id=model_id,
            revision_id=revision_id,
            payload=payload or {},
        )
        self._events.append(event)
        return event

    def list_events(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events]
