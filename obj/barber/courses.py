from __future__ import annotations

import base64
import secrets

from obj.base import Base
from obj.client import Response

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
JPEG_HEAD = b"\xff\xd8\xff\xe0" + b"\x00" * 40
WEBP_HEAD = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 40
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
