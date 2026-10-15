from __future__ import annotations

import secrets
import time

import requests

from obj.base import Base
from obj.client import Response


class Push(Base):
    resource = "push"

    def key(self, persona: str) -> Response:
        return self.client.request("GET", f"{self.path}/key", persona=persona)

    def subscribe(self, endpoint: str, persona: str) -> Response:
        return self.client.request(
            "POST", f"{self.path}/subscribe", persona=persona, json={"endpoint": endpoint}
        )

    def notice(self, endpoint: str) -> Response:
        """What the service worker asks when a push wakes it: no sign-in, its own address as the proof."""
        return self.client.request("POST", f"{self.path}/notice", persona=None, json={"endpoint": endpoint})

    def register_device(self, token: str, persona: str, platform: str = "ios") -> Response:
        """The shop's app on a phone, after the person allowed notifications."""
        return self.client.request(
            "POST", f"{self.path}/devices", persona=persona, json={"platform": platform, "token": token}
        )

    def remove_device(self, token: str, persona: str) -> Response:
        return self.client.request(
            "POST", f"{self.path}/devices/remove", persona=persona, json={"token": token}
        )

    def unsubscribe(self, endpoint: str, persona: str) -> Response:
        return self.client.request(
            "POST", f"{self.path}/unsubscribe", persona=persona, json={"endpoint": endpoint}
        )


class PushInbox:
    """The fake push service (utils/fake_push.py): what the barbershop posted to an address of it."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def new_endpoint(self) -> str:
        return f"{self.base_url}/push/{secrets.token_hex(5)}"

    @staticmethod
    def name(endpoint: str) -> str:
        return endpoint.rsplit("/", 1)[-1]

    def posts(self, endpoint: str) -> list[dict]:
        return requests.get(f"{self.base_url}/pushes/{self.name(endpoint)}", timeout=5).json()

    def answer_with(self, endpoint: str, status: int) -> None:
        requests.put(f"{self.base_url}/answer/{self.name(endpoint)}/{status}", timeout=5).raise_for_status()

    def wait_for(self, endpoint: str, count: int = 1, seconds: float = 5) -> list[dict]:
        deadline = time.monotonic() + seconds
        while True:
            found = self.posts(endpoint)
            if len(found) >= count or time.monotonic() > deadline:
                return found
            time.sleep(0.1)

    def stays_quiet(self, endpoint: str, seconds: float = 1.5) -> list[dict]:
        time.sleep(seconds)
        return self.posts(endpoint)

    # Firebase, for the shop's app on a phone.

    @staticmethod
    def new_device_token() -> str:
        return f"qa-device-{secrets.token_hex(16)}"

    def phone_messages(self, token: str) -> list[dict]:
        return requests.get(f"{self.base_url}/fcm/{token}", timeout=5).json()

    def wait_for_phone(self, token: str, count: int = 1, seconds: float = 5) -> list[dict]:
        deadline = time.monotonic() + seconds
        while True:
            found = self.phone_messages(token)
            if len(found) >= count or time.monotonic() > deadline:
                return found
            time.sleep(0.1)

    def phone_answers_with(self, token: str, status: int) -> None:
        """What Firebase answers for this device from now on - 404: the app was removed from the phone."""
        requests.put(f"{self.base_url}/answer/{token}/{status}", timeout=5).raise_for_status()

    def phone_stays_quiet(self, token: str, seconds: float = 1.5) -> list[dict]:
        time.sleep(seconds)
        return self.phone_messages(token)
