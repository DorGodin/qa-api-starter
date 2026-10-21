from __future__ import annotations

import base64
import secrets

from obj.base import Base
from obj.client import Response

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
JPEG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDoaKKK+MPZP//Z"
)
WEBP_1X1 = base64.b64decode(
    "UklGRjoAAABXRUJQVlA4IC4AAACwAQCdASoBAAEAAUAmJaACdLoABGaAAP7t7Wf+px/8yv/1lf7V3+4Mz6uv8AAA"
)
GIF_HEAD = b"GIF89a" + b"\x00" * 20


class Courses(Base):
    resource = "courses"

    def build_course_payload(
        self,
        title: str | None = None,
        subtitle: str = "8 מפגשים",
        starts_on: str | None = "2026-11-02",
        price_minor: int | None = 320000,
    ) -> dict:
        return {
            "title": title or f"קורס QA {secrets.token_hex(3)}",
            "subtitle": subtitle,
            "starts_on": starts_on,
            "price_minor": price_minor,
        }

    def create_fake_course(self, persona: str = "owner", **kwargs) -> dict:
        return self.create(self.build_course_payload(**kwargs), persona=persona).assert_ok(201).as_dict

    def withdraw(self, course_id: str, persona: str = "owner") -> dict:
        return self.update_by_id(course_id, {"active": False}, persona=persona).assert_ok(200).as_dict

    @staticmethod
    def encode(raw: bytes) -> dict:
        return {"data": base64.b64encode(raw).decode()}

    def set_image(self, course_id: str, raw: bytes, persona: str = "owner") -> Response:
        return self.client.request(
            "PUT", f"{self.path}/{course_id}/image", persona=persona, json=self.encode(raw)
        )

    def remove_image(self, course_id: str, persona: str = "owner") -> Response:
        return self.client.request("DELETE", f"{self.path}/{course_id}/image", persona=persona)

    def listing(self, persona: str) -> list[dict]:
        return self.find(persona=persona).assert_ok(200).as_dict["content"]
