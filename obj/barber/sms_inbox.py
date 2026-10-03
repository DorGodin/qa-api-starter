from __future__ import annotations

import re
import time

import requests

CODE = re.compile(r"\b(\d{4})\b")


class SmsInbox:
    """The fake SMS provider's inbox (utils/fake_sms.py): what the barbershop
    sent to a number, read the way a person reads their phone."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def messages(self, phone: str) -> list[dict]:
        resp = requests.get(f"{self.base_url}/messages", params={"to": phone}, timeout=5)
        if resp.status_code != 200:
            raise RuntimeError(f"the fake SMS inbox at {self.base_url} answered {resp.status_code}")
        return resp.json()

    def last_id(self, phone: str) -> int:
        found = self.messages(phone)
        return found[-1]["id"] if found else 0

    def code_for(self, phone: str, after: int = 0, wait_seconds: float = 5) -> str:
        """The code in the newest message to that number sent after message
        `after` - waited for briefly, since the product sends it while it answers."""
        deadline = time.monotonic() + wait_seconds
        while True:
            newer = [m for m in self.messages(phone) if m["id"] > after]
            if newer:
                match = CODE.search(newer[-1]["text"])
                if match is None:
                    raise AssertionError(f"the SMS to {phone} has no 4-digit code: {newer[-1]['text']!r}")
                return match.group(1)
            if time.monotonic() > deadline:
                raise AssertionError(f"no SMS reached {phone} within {wait_seconds}s")
            time.sleep(0.1)
