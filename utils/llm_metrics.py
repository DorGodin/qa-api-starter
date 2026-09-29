"""Deterministic metrics for evaluating an LLM feature.

A judge model is powerful but it costs money, needs a key and is itself
non-deterministic. Most of what a QA team needs to guarantee about an assistant
is checkable without one: did the facts survive, did it refuse what it should
refuse, did it stay inside its scope. Those live here and run offline.

The judged metrics (relevancy, faithfulness, G-Eval) are opt-in and are skipped
when no key is configured. See tests/llm/README.md.
"""
from __future__ import annotations

import re

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _numbers(text: str) -> set[float]:
    return {float(n) for n in NUMBER_RE.findall(text or "")}


class FactsSurvivedMetric(BaseMetric):
    """Every number the feature was grounded in must appear in the answer.

    This is the cheapest defence against a confident answer built on the wrong
    row, and it does not care how the sentence is phrased.
    """

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        expected = _numbers(" ".join(test_case.context or []))
        if not expected:
            self.score, self.reason, self.success = 1.0, "no grounded facts to check", True
            return self.score

        found = _numbers(test_case.actual_output)
        kept = {value for value in expected if value in found}
        self.score = len(kept) / len(expected)
        missing = sorted(expected - kept)
        self.reason = "all grounded facts present" if not missing else f"missing from the answer: {missing}"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "Facts survived"


class NoInventedNumbersMetric(BaseMetric):
    """The answer may not contain a number that was not in the grounding data.

    An assistant that invents a figure is worse than one that refuses, because
    the invented figure looks like an answer.
    """

    def __init__(self, threshold: float = 1.0, ignore: set[float] | None = None):
        self.threshold = threshold
        self.ignore = ignore or set()

    def measure(self, test_case: LLMTestCase) -> float:
        grounded = _numbers(" ".join(test_case.context or [])) | self.ignore
        invented = sorted(_numbers(test_case.actual_output) - grounded)
        self.score = 0.0 if invented else 1.0
        self.reason = "no invented numbers" if not invented else f"not grounded anywhere: {invented}"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "No invented numbers"


class StaysInScopeMetric(BaseMetric):
    """Out of scope questions must be refused, in scope questions must not be."""

    def __init__(self, should_refuse: bool, threshold: float = 1.0):
        self.should_refuse = should_refuse
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase) -> float:
        refused = bool((test_case.metadata or {}).get("refused"))
        self.score = 1.0 if refused == self.should_refuse else 0.0
        expectation = "refuse" if self.should_refuse else "answer"
        self.reason = f"expected the assistant to {expectation}; refused={refused}"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "Stays in scope"
