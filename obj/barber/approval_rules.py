from __future__ import annotations

from datetime import date

from obj.barber.barbers import WEEK
from obj.base import Base
from obj.client import Response


class ApprovalRules(Base):
    resource = "approval-rules"

    @staticmethod
    def build_rules(days: dict[str, list[str] | None] | None = None, enabled: bool = True) -> dict:
        hours = dict.fromkeys(WEEK, None)
        hours.update(days or {})
        return {"enabled": enabled, "hours": hours}

    @staticmethod
    def weekday_of(day: date) -> str:
        return WEEK[day.weekday()]

    def read(self, persona: str = "owner") -> Response:
        return self.client.request("GET", self.path, persona=persona)

    def save(self, rules: dict, persona: str = "owner") -> Response:
        return self.client.request("PUT", self.path, persona=persona, json=rules)

    def current(self) -> dict:
        return self.read().assert_ok(200).as_dict

    def for_day(self, day: date, span: list[str] | None, enabled: bool = True) -> dict:
        return self.save(self.build_rules({self.weekday_of(day): span}, enabled)).assert_ok(200).as_dict
