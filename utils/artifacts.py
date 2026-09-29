"""What a run created, and where.

After a run against a shared environment, the question nobody can usually answer
is "what did that leave behind". Every create goes through `Base.create`, so
recording there costs the tests nothing and misses nothing.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_current_test: str = "unknown"


def set_current_test(nodeid: str) -> None:
    global _current_test
    _current_test = nodeid


def current_test() -> str:
    return _current_test


@dataclass(frozen=True)
class Artifact:
    resource: str
    entity_id: str
    env: str
    test: str
    persona: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


class ArtifactLog:
    """Records every entity a run creates, so it can be listed or cleaned up."""

    def __init__(self, env: str) -> None:
        self.env = env
        self._items: list[Artifact] = []

    def record(self, resource: str, payload: Any, persona: str | None = None) -> None:
        entity_id = payload.get("id") if isinstance(payload, dict) else None
        if not entity_id:
            return
        self._items.append(
            Artifact(resource=resource, entity_id=str(entity_id), env=self.env,
                     test=current_test(), persona=persona)
        )

    @property
    def items(self) -> list[Artifact]:
        return list(self._items)

    def by_resource(self) -> dict[str, list[Artifact]]:
        grouped: dict[str, list[Artifact]] = {}
        for item in self._items:
            grouped.setdefault(item.resource, []).append(item)
        return dict(sorted(grouped.items()))

    def summary(self) -> dict[str, int]:
        return {resource: len(items) for resource, items in self.by_resource().items()}

    def append_to(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for item in self._items:
                handle.write(json.dumps(asdict(item)) + "\n")
        return path


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tail(records: Iterable[dict], limit: int) -> list[dict]:
    items = list(records)
    return items[-limit:] if limit else items
