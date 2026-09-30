"""How a persona logs in. One function per login style, picked by the
environment's `auth.type`.

Each strategy receives the HTTP call to make (`post`) rather than making it, so
it can be tested without a network, and returns the headers every later request
of that persona should carry. It never touches the shared session: the client
logs each persona in on a session of its own, so a cookie the product sets at
login cannot follow a different persona's requests.

Adding a login style is one function here and one line in STRATEGIES.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

Post = Callable[..., Any]
TIMEOUT = 20


class LoginFailed(RuntimeError):
    pass


def _absolute(base_url: str, path_or_url: str) -> str:
    return path_or_url if path_or_url.startswith(("http://", "https://")) else f"{base_url}{path_or_url}"


def _require(cfg: dict, key: str, style: str) -> Any:
    if key not in cfg:
        raise KeyError(f"auth type {style!r} needs {key!r} in the environment's auth block")
    return cfg[key]


def _check(resp, persona: str, url: str):
    if not 200 <= resp.status_code < 300:
        # The body can say why. The password is never part of the message.
        raise LoginFailed(
            f"login for persona {persona!r} failed: POST {url} -> {resp.status_code}: {resp.text[:200]}"
        )
    return resp


def _field(resp, name: str, persona: str, url: str) -> str:
    try:
        value = resp.json().get(name)
    except ValueError:
        value = None
    if not value:
        # Some products answer a bad password with 200 and a reason in the body -
        # Restful-Booker does. The body is what says which it was.
        raise LoginFailed(
            f"login for persona {persona!r} at {url} answered {resp.status_code} but returned no {name!r}: "
            f"{resp.text[:200]}"
        )
    return value


def password_token(post: Post, base_url: str, cfg: dict, persona: str, username: str, password: str) -> dict:
    """POST a JSON username and password, get a bearer token back. The demo API,
    and most in-house APIs.

    auth: {"type": "password_token", "path": "/auth/token"}
    optional: username_field, password_field, token_field ("access_token"), scheme ("Bearer")
    """
    url = _absolute(base_url, _require(cfg, "path", "password_token"))
    body = {cfg.get("username_field", "username"): username, cfg.get("password_field", "password"): password}
    resp = _check(post(url, json=body, timeout=TIMEOUT), persona, url)
    token = _field(resp, cfg.get("token_field", "access_token"), persona, url)
    return {"Authorization": f"{cfg.get('scheme', 'Bearer')} {token}"}


def oauth_password(post: Post, base_url: str, cfg: dict, persona: str, username: str, password: str) -> dict:
    """OAuth2 resource-owner password grant - Keycloak, Auth0 and most identity
    providers. Form encoded, not JSON; that difference alone breaks most first
    attempts at a Keycloak login.

    auth: {"type": "oauth_password", "token_url": "https://id.example/realms/x/protocol/openid-connect/token",
           "client_id": "qa-client"}
    optional: client_secret_env (the NAME of the variable holding the secret), scope
    """
    url = _absolute(base_url, _require(cfg, "token_url", "oauth_password"))
    form = {
        "grant_type": "password",
        "client_id": _require(cfg, "client_id", "oauth_password"),
        "username": username,
        "password": password,
    }
    if "client_secret_env" in cfg:
        secret = os.environ.get(cfg["client_secret_env"])
        if not secret:
            raise KeyError(f"auth needs a client secret in ${cfg['client_secret_env']}, and it is not set")
        form["client_secret"] = secret
    if "scope" in cfg:
        form["scope"] = cfg["scope"]
    resp = _check(post(url, data=form, timeout=TIMEOUT), persona, url)
    return {"Authorization": f"Bearer {_field(resp, 'access_token', persona, url)}"}


def cookie_token(post: Post, base_url: str, cfg: dict, persona: str, username: str, password: str) -> dict:
    """Log in, then send the session back as a cookie on every request.

    The cookie goes out as an explicit header of this persona, never through a
    shared cookie jar: a jar is per session, and the personas share a session.

    auth: {"type": "cookie_token", "path": "/auth", "cookie_name": "token"}
    optional: token_field - read the value from the JSON body instead of from
              the Set-Cookie header (Restful-Booker returns it in the body)
    """
    url = _absolute(base_url, _require(cfg, "path", "cookie_token"))
    name = _require(cfg, "cookie_name", "cookie_token")
    body = {cfg.get("username_field", "username"): username, cfg.get("password_field", "password"): password}
    resp = _check(post(url, json=body, timeout=TIMEOUT), persona, url)
    if "token_field" in cfg:
        value = _field(resp, cfg["token_field"], persona, url)
    else:
        value = resp.cookies.get(name)
        if not value:
            raise LoginFailed(f"login for persona {persona!r} at {url} set no {name!r} cookie")
    return {"Cookie": f"{name}={value}"}


STRATEGIES: dict[str, Callable[..., dict]] = {
    "password_token": password_token,
    "oauth_password": oauth_password,
    "cookie_token": cookie_token,
}


def login(post: Post, base_url: str, auth_cfg: dict, persona: str, username: str, password: str) -> dict:
    style = auth_cfg.get("type")
    strategy = STRATEGIES.get(style)
    if strategy is None:
        raise KeyError(f"unknown auth type {style!r}. Known: {', '.join(sorted(STRATEGIES))}")
    return strategy(post, base_url, auth_cfg, persona, username, password)
