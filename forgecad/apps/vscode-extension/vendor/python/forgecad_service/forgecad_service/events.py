"""In-memory service event log."""

from __future__ import annotations

from collections import deque
from itertools import count
from queue import Queue
from threading import Lock
from typing import Any

from forgecad_core.models import ServiceEvent


class EventSubscription:
    def __init__(self, event_log: "EventLog", queue: Queue[dict[str, Any]]) -> None:
        self._event_log = event_log
        self._queue = queue
        self._closed = False

    def get(self, timeout: float | None = None) -> dict[str, Any]:
        return self._queue.get(timeout=timeout)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._event_log.unsubscribe(self)

    @property
    def queue(self) -> Queue[dict[str, Any]]:
        return self._queue


class EventLog:
    def __init__(self, max_events: int = 500) -> None:
        self._events: deque[ServiceEvent] = deque(maxlen=max_events)
        self._counter = count(1)
        self._lock = Lock()
        self._subscribers: list[EventSubscription] = []

    def emit(
        self,
        event_type: str,
        *,
        session_id: str | None = None,
        model_id: str | None = None,
        revision_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ServiceEvent:
        with self._lock:
            event = ServiceEvent(
                event_id=f"evt_{next(self._counter):08d}",
                event_type=event_type,
                session_id=session_id,
                model_id=model_id,
                revision_id=revision_id,
                payload=payload or {},
            )
            self._events.append(event)
            event_data = event.to_dict()
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.queue.put(event_data)
        return event

    def list_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [event.to_dict() for event in self._events]

    def subscribe(self, *, replay: bool = False) -> EventSubscription:
        queue: Queue[dict[str, Any]] = Queue()
        subscription = EventSubscription(self, queue)
        with self._lock:
            if replay:
                for event in self._events:
                    queue.put(event.to_dict())
            self._subscribers.append(subscription)
        return subscription

    def unsubscribe(self, subscription: EventSubscription) -> None:
        with self._lock:
            self._subscribers = [
                item for item in self._subscribers if item is not subscription
            ]
