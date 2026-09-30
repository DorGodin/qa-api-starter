"""One block per environment, and the only place a password is resolved.

A block declares everything about an environment - who the personas are, how
they log in, where the health check lives, and whether the product exposes test
hooks. Nothing is computed or defaulted, because a default is a guess, and a
guess about test hooks is how a suite ends up calling /_test/reset on a product
that has never heard of it.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from utils.helpers import current_env

REQUIRED_KEYS = ("url", "product", "personas", "admin_persona", "auth", "health_path", "test_hooks")
_CONFIG_PATH = Path(__file__).with_name("config.json")
_LOCAL_OVERRIDE = Path(__file__).with_name("config.local.json")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def is_local_host(url: str) -> bool:
    """Loopback, or a hostname with no dot - a docker service name, never a
    public host. Only these may carry a password in the committed config."""
    host = urlsplit(url).hostname or ""
    if host == "localhost" or "." not in host:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _blocks(committed: dict, local: dict) -> dict:
    blocks = {name: dict(block) for name, block in committed.items()}
    for name, block in local.items():
        blocks.setdefault(name, {}).update(block)
    return blocks


def load_env_config(env: str | None = None) -> dict:
    """The block for `env`, validated, with passwords removed.

    Passwords never travel inside the config dict. It is handed around, copied
    and printed; a secret in it would eventually be logged. Ask
    `password_for` at the moment of logging in instead.
    """
    env = env or current_env()
    committed = _read(_CONFIG_PATH)
    blocks = _blocks(committed, _read(_LOCAL_OVERRIDE))

    if env not in blocks:
        raise KeyError(f"unknown ENV {env!r}. Known environments: {', '.join(sorted(blocks))}")

    block = blocks[env]
    missing = [k for k in REQUIRED_KEYS if k not in block]
    if missing:
        raise KeyError(f"environment {env!r} is missing required key(s): {', '.join(missing)}")

    # "false" is a truthy string. Accepting it would call /_test/reset against a
    # real product, so only a real boolean is accepted.
    if not isinstance(block["test_hooks"], bool):
        raise TypeError(f"environment {env!r}: test_hooks must be true or false, got {block['test_hooks']!r}")
    if not isinstance(block["personas"], dict) or not block["personas"]:
        raise ValueError(f"environment {env!r}: personas must map at least one persona to a username")
    if block["admin_persona"] not in block["personas"]:
        raise ValueError(
            f"environment {env!r}: admin_persona {block['admin_persona']!r} is not one of its personas "
            f"({', '.join(block['personas'])})"
        )
    if not isinstance(block["auth"], dict) or "type" not in block["auth"]:
        raise ValueError(f"environment {env!r}: auth must be an object with a type")

    committed_passwords = committed.get(env, {}).get("passwords")
    if committed_passwords and not is_local_host(block["url"]):
        raise ValueError(
            f"environment {env!r} points at {urlsplit(block['url']).hostname}, and config/config.json "
            "holds a password for it. That file is committed. Move the passwords to "
            "config/config.local.json (gitignored) or to QA_<PERSONA>_PASSWORD environment variables."
        )

    return {"env": env, **{k: v for k, v in block.items() if k != "passwords"}}


def password_env_var(persona: str) -> str:
    return f"QA_{re.sub(r'[^A-Za-z0-9]', '_', persona).upper()}_PASSWORD"


def resolve_password(persona: str, env: str | None = None) -> tuple[str, str]:
    """(password, where it came from), most specific source first.

    1. QA_<PERSONA>_PASSWORD in the environment - what CI sets from its secrets
    2. "passwords" in config/config.local.json - a developer's own machine
    3. "passwords" in config/config.json - demo environments on a local host only;
       load_env_config refuses anything else

    The source is what a diagnosis needs. The value never has to be printed.
    """
    env = env or current_env()
    load_env_config(env)

    variable = password_env_var(persona)
    if os.environ.get(variable):
        return os.environ[variable], variable
    for label, source in (
        ("config/config.local.json", _read(_LOCAL_OVERRIDE)),
        ("config/config.json", _read(_CONFIG_PATH)),
    ):
        password = (source.get(env, {}).get("passwords") or {}).get(persona)
        if password:
            return password, label
    raise KeyError(
        f"no password for persona {persona!r} on ENV={env!r}. Set {variable}, "
        f'or add it under "passwords" for {env!r} in config/config.local.json (gitignored).'
    )


def password_for(persona: str, env: str | None = None) -> str:
    return resolve_password(persona, env)[0]
