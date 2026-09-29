from __future__ import annotations

from obj.base import Base


class Assistant(Base):
    resource = "assistant"

    def ask(self, question: str, persona: str = "member"):
        return self.client.request("POST", f"{self.path}/answer", persona=persona, json={"question": question})

    def answer(self, question: str, persona: str = "member") -> dict:
        return self.ask(question, persona=persona).assert_ok(200).as_dict
