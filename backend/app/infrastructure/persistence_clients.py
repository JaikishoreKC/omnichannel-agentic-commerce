from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MongoClientManager:
    uri: str
    enabled: bool
    _client: Any = None
    _last_error: str | None = None

    def connect(self) -> None:
        if not self.enabled:
            return
        try:
            from pymongo import MongoClient

            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=2000)
            self._client.admin.command("ping")
            self._last_error = None
        except Exception as exc:
            self._client = None
            self._last_error = str(exc)

    @property
    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self._client is None:
            return "unavailable"
        return "connected"

    @property
    def error(self) -> str | None:
        return self._last_error

    @property
    def client(self) -> Any:
        return self._client


@dataclass
class RedisClientManager:
    url: str
    enabled: bool
    _client: Any = None
    _last_error: str | None = None

    def connect(self) -> None:
        if not self.enabled:
            return
        try:
            import redis

            self._client = redis.from_url(self.url, socket_timeout=2)
            self._client.ping()
            self._last_error = None
        except Exception as exc:
            self._client = None
            self._last_error = str(exc)

    @property
    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self._client is None:
            return "unavailable"
        return "connected"

    @property
    def error(self) -> str | None:
        return self._last_error

    @property
    def client(self) -> Any:
        return self._client
