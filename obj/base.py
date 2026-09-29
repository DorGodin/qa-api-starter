from __future__ import annotations

from typing import Any

from obj.client import ApiClient, Response


class Base:
    """Standard CRUD for one API resource.

    Subclasses set `resource` and add action methods. Business logic, payload
    building and url building live here, never in a test.
    """

    resource: str = ""

    def __init__(self, client: ApiClient) -> None:
        if not self.resource:
            raise ValueError(f"{type(self).__name__} must set `resource`")
        self.client = client

    @property
    def path(self) -> str:
        return f"/{self.resource}"

    def create(self, data: dict[str, Any], persona: str | None = "__active__") -> Response:
        return self.client.request("POST", self.path, persona=persona, json=data)

    def get_by_id(self, entity_id: str, params: dict | None = None, persona: str | None = "__active__") -> Response:
        return self.client.request("GET", f"{self.path}/{entity_id}", persona=persona, params=params)

    def find(self, params: dict | None = None, persona: str | None = "__active__") -> Response:
        return self.client.request("GET", self.path, persona=persona, params=params)

    def update_by_id(self, entity_id: str, data: dict, persona: str | None = "__active__") -> Response:
        return self.client.request("PATCH", f"{self.path}/{entity_id}", persona=persona, json=data)

    def delete_by_id(self, entity_id: str, persona: str | None = "__active__") -> Response:
        return self.client.request("DELETE", f"{self.path}/{entity_id}", persona=persona)

    def find_first(self, params: dict | None = None, persona: str | None = "__active__") -> dict[str, Any]:
        resp = self.find(params=params, persona=persona).assert_ok(200)
        content = resp.content
        if not content:
            raise AssertionError(f"no {self.resource} matched {params!r} on {self.client.config['env']}")
        return content[0]
