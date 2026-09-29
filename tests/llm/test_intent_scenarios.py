"""Intents come from a file so a non-engineer can extend the coverage."""
import pytest

from utils.scenarios import load_json

INTENTS = load_json("assistant_intents.json")


@pytest.mark.parametrize("case", INTENTS["in_scope"], ids=[c["question"][:22] for c in INTENTS["in_scope"]])
def test_an_in_scope_question_is_answered_from_the_right_data(assistant, case):
    body = assistant.answer(case["question"])

    assert body["refused"] is False, f"refused a question it has data for: {case['question']!r}"
    if case["expects"] == "budget":
        assert "budget" in body["grounded_in"]
    else:
        assert "order_count" in body["grounded_in"]


@pytest.mark.parametrize("case", INTENTS["out_of_scope"], ids=[c["question"][:22] for c in INTENTS["out_of_scope"]])
def test_an_out_of_scope_question_is_refused(assistant, case):
    body = assistant.answer(case["question"])

    assert body["refused"] is True, f"answered something it has no data for: {case['question']!r}"
    assert body["grounded_in"] == {}
