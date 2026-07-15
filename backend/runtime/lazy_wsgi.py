"""Lazy WSGI application construction for import-safe process entrypoints."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class LazyWsgiApplication:
    """Create the concrete WSGI application only when it is first used."""

    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._application: Any | None = None
        self._lock = threading.Lock()

    def get(self) -> Any:
        if self._application is None:
            with self._lock:
                if self._application is None:
                    self._application = self._factory()
        return self._application

    def __call__(self, environ: Any, start_response: Any) -> Any:
        return self.get()(environ, start_response)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.get(), name)
