from __future__ import annotations

from dataclasses import dataclass
from contextlib import suppress
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
        
        # Warning if using localhost in what might be a non-dev env
        if "localhost" in self.uri or "127.0.0.1" in self.uri:
             print(f"WARNING: MongoClientManager is using a LOCALHOST URI: {self.uri}")

        try:
            from pymongo import MongoClient

            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=2000)
            self._client.admin.command("ping")
            self._last_error = None
        except Exception as exc:
            self._client = None
            self._last_error = str(exc)
            print(f"WARNING: Failed to connect to MongoDB at {self.uri}: {exc}")

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
        if self._client is not None and not hasattr(self._client, "close"):
            with suppress(Exception):
                setattr(self._client, "close", lambda: None)
        return self._client

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
        self._client = None


@dataclass
class RedisClientManager:
    url: str
    enabled: bool
    _client: Any = None
    _last_error: str | None = None

    def connect(self) -> None:
        if not self.enabled:
            return

        if "localhost" in self.url or "127.0.0.1" in self.url:
             print(f"WARNING: RedisClientManager is using a LOCALHOST URL: {self.url}")

        try:
            import redis

            self._client = redis.from_url(self.url, socket_timeout=2)
            self._client.ping()
            self._last_error = None
        except Exception as exc:
            self._client = None
            self._last_error = str(exc)
            print(f"WARNING: Failed to connect to Redis at {self.url}: {exc}")

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
        if self._client is not None and not hasattr(self._client, "close"):
            with suppress(Exception):
                setattr(self._client, "close", lambda: None)
        return self._client

    def disconnect(self) -> None:
        if self._client:
            with suppress(Exception):
                self._client.close()
        self._client = None
