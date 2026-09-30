from __future__ import annotations

from dataclasses import dataclass, field
from http.cookiejar import DefaultCookiePolicy
from typing import Any

import requests

from config.loader import load_env_config, password_for
from obj.auth import login
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

    def assert_ok(self, expected: int | tuple[int, ...] = (200, 201, 204)) -> Response:
        expected = (expected,) if isinstance(expected, int) else expected
        if self.status_code not in expected:
            raise AssertionError(
                f"{self.raw.request.method} {self.raw.request.url} -> {self.status_code} "
                f"(expected {expected}): {self.raw.text[:400]}"
            )
        return self


def _shared_session() -> requests.Session:
    """The session every persona's requests go through, with cookies refused.

    A session keeps every cookie a server sets and sends it on every later
    request. The personas share this one, so a session cookie set for the owner
    would ride along on the customer's calls, and a permission test would pass
    for the wrong persona. Identity travels only in each persona's own headers.
    """
    session = requests.Session()
    session.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
    return session


def _login_post(url: str, **kwargs) -> requests.Response:
    """Each login on a fresh session, thrown away afterwards, so nothing it sets
    can reach the shared one."""
    with requests.Session() as session:
        return session.post(url, **kwargs)


@dataclass
class ApiClient:
    """Owns the session, the base url and each persona's credentials.

    Personas come from the environment's config and are logged in once per run;
    a test only names one per call and never juggles headers.
    """

    env: str | None = None
    _config: dict = field(default_factory=dict, init=False)
    _session: requests.Session = field(default_factory=_shared_session, init=False)
    _headers: dict[str, dict[str, str]] = field(default_factory=dict, init=False)
    _active: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._config = load_env_config(self.env)

    @property
    def base_url(self) -> str:
        return self._config["url"].rstrip("/")

    @property
    def config(self) -> dict:
        return dict(self._config)

    @property
    def personas(self) -> list[str]:
        return list(self._config["personas"])

    def register_persona(self, name: str, username: str, password: str) -> dict[str, str]:
        headers = login(_login_post, self.base_url, self._config["auth"], name, username, password)
        self._headers[name] = headers
        if self._active is None:
            self._active = name
        return headers

    def login_personas(self) -> ApiClient:
        """Every persona the environment declares, each with its own password."""
        env = self._config["env"]
        for name, username in self._config["personas"].items():
            self.register_persona(name, username, password_for(name, env))
        return self

    def auth_headers(self, persona: str) -> dict[str, str]:
        """What identifies this persona on the wire. For tests that have to put
        a credential somewhere unusual - a query string, a second header - to
        prove the product rejects it."""
        if persona not in self._headers:
            raise KeyError(f"persona {persona!r} not registered. Known: {sorted(self._headers)}")
        return dict(self._headers[persona])

    def use(self, persona: str) -> ApiClient:
        if persona not in self._headers:
            raise KeyError(f"persona {persona!r} not registered. Known: {sorted(self._headers)}")
        self._active = persona
        return self

    def request(self, method: str, path: str, persona: str | None = "__active__", **kwargs) -> Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        name = self._active if persona == "__active__" else persona
        if name is not None:
            persona_headers = self._headers.get(name)
            if persona_headers is None:
                raise KeyError(f"persona {name!r} not registered")
            for key, value in persona_headers.items():
                headers.setdefault(key, value)
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        response = Response(
            self._session.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
        )
        http_trace.record(
            artifacts.current_test(),
            http_trace.Call(method=method.upper(), path=path, status=response.status_code, persona=name),
        )
        return response
