"""Input a user can actually send.

An assistant that only works on tidy sentences fails the first time someone
pastes, types in another language, or holds down a key.
"""
import pytest


@pytest.mark.parametrize(
    "question",
    [
        "WHAT IS MY BUDGET",
        "   what is my budget   ",
        "what is my budget!!!",
        "budget",
        "Can you please tell me, if it is not too much trouble, what my budget is",
    ],
    ids=["shouting", "padded", "punctuated", "one-word", "polite-and-long"],
)
def test_the_same_intent_is_understood_however_it_is_typed(assistant, orders, question):
    body = assistant.answer(question)

    assert body["refused"] is False, f"a reasonable phrasing was refused: {question!r}"
    assert body["grounded_in"]["budget"] == orders.budget()


@pytest.mark.parametrize(
    "question",
    ["מה התקציב שלי", "¿cuál es mi budget?", "budget 💰?"],
    ids=["hebrew", "spanish", "emoji"],
)
def test_non_ascii_input_does_not_break_it(assistant, question):
    body = assistant.answer(question)
    assert isinstance(body["answer"], str) and body["answer"]


def test_the_longest_accepted_question_is_handled(assistant):
    body = assistant.answer("budget " + "x" * 293)

    assert len(("budget " + "x" * 293)) == 300
    assert body["answer"]


def test_one_character_past_the_limit_is_rejected_not_truncated(assistant):
    assert assistant.ask("x" * 301).status_code == 422


@pytest.mark.parametrize("question", ["", "   "], ids=["empty", "whitespace"])
def test_an_empty_question_never_reaches_the_model(assistant, question):
    resp = assistant.ask(question)
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        assert resp.as_dict["refused"] is True, "a blank question must refuse, not guess"


def test_the_answer_stays_short_enough_to_show_a_user(assistant):
    answer = assistant.answer("what is my budget")["answer"]
    assert len(answer) <= 200, f"an answer this long will be truncated by any UI: {len(answer)} chars"


def test_asking_repeatedly_does_not_drift(assistant):
    grounded = {assistant.answer("what is my budget")["grounded_in"]["budget"] for _ in range(10)}
    assert len(grounded) == 1, f"the underlying fact drifted across calls: {grounded}"
