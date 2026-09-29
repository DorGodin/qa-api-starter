from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from config.loader import load_env_config
from utils import artifacts, http_trace

DEFAULT_TIMEOUT = 20


@dataclass
class Response:
    """Thin wrapper so tests never touch requests directly."""

    raw: requests.Response

    @property
    def status_code(self) -> int:
        return self.raw.status_code

    @property
    def ok(self) -> bool:
        return self.raw.ok

    @property
    def as_dict(self) -> dict[str, Any]:
        if not self.raw.content:
            return {}
        try:
            return self.raw.json()
        except ValueError:
            return {"raw_text": self.raw.text}

    @property
    def content(self) -> list[dict[str, Any]]:
        return self.as_dict.get("content", [])

    def assert_ok(self, expected: int | tuple[int, ...] = (200, 201, 204)) -> "Response":
        expected = (expected,) if isinstance(expected, int) else expected
        if self.status_code not in expected:
            raise AssertionError(
                f"{self.raw.request.method} {self.raw.request.url} -> {self.status_code} "
                f"(expected {expected}): {self.raw.text[:400]}"
            )
        return self


@dataclass
class ApiClient:
    """Owns the session, the base url and the persona tokens.

    Personas are registered once per run and selected per call, so a test never
    juggles headers.
    """

    env: str | None = None
    _config: dict = field(default_factory=dict, init=False)
    _session: requests.Session = field(default_factory=requests.Session, init=False)
    _tokens: dict[str, str] = field(default_factory=dict, init=False)
    _active: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._config = load_env_config(self.env)

    @property
    def base_url(self) -> str:
        return self._config["url"].rstrip("/")

    @property
    def config(self) -> dict:
        return dict(self._config)

    def register_persona(self, name: str, username: str, password: str) -> str:
        resp = self.request("POST", "/auth/token", persona=None, json={"username": username, "password": password})
        resp.assert_ok(200)
        token = resp.as_dict["access_token"]
        self._tokens[name] = token
        if self._active is None:
            self._active = name
        return token

    def use(self, persona: str) -> "ApiClient":
        if persona not in self._tokens:
            raise KeyError(f"persona {persona!r} not registered. Known: {sorted(self._tokens)}")
        self._active = persona
        return self

    def request(self, method: str, path: str, persona: str | None = "__active__", **kwargs) -> Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        name = self._active if persona == "__active__" else persona
        if name is not None:
            token = self._tokens.get(name)
            if token is None:
                raise KeyError(f"persona {name!r} not registered")
            headers.setdefault("Authorization", f"Bearer {token}")
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        response = Response(self._session.request(method, f"{self.base_url}{path}", headers=headers, **kwargs))
        http_trace.record(
            artifacts.current_test(),
            http_trace.Call(method=method.upper(), path=path, status=response.status_code, persona=name),
        )
        return response
