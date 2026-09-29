from __future__ import annotations

import json
from pathlib import Path

from utils.helpers import current_env

REQUIRED_KEYS = ("url", "admin_user", "member_user")
_CONFIG_PATH = Path(__file__).with_name("config.json")
_LOCAL_OVERRIDE = Path(__file__).with_name("config.local.json")


def load_env_config(env: str | None = None) -> dict:
    """Return the block for `env`. No if/elif ladder, no computed defaults."""
    env = env or current_env()
    blocks = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    if _LOCAL_OVERRIDE.exists():
        for name, block in json.loads(_LOCAL_OVERRIDE.read_text(encoding="utf-8")).items():
            blocks.setdefault(name, {}).update(block)

    if env not in blocks:
        raise KeyError(f"unknown ENV {env!r}. Known environments: {', '.join(sorted(blocks))}")

    block = blocks[env]
    missing = [k for k in REQUIRED_KEYS if k not in block]
    if missing:
        raise KeyError(f"environment {env!r} is missing required key(s): {', '.join(missing)}")
    return {"env": env, **block}
