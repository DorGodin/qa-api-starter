import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from utils.llm_metrics import FactsSurvivedMetric, NoInventedNumbersMetric, StaysInScopeMetric


def build_case(assistant, question: str) -> LLMTestCase:
    body = assistant.answer(question)
    context = [f"{k}={v}" for k, v in (body.get("grounded_in") or {}).items()]
    return LLMTestCase(
        input=question,
        actual_output=body["answer"],
        context=context or None,
        metadata={"refused": body["refused"]},
    )


@pytest.mark.parametrize(
    "question",
    [
        "what is my budget",
        "what is my budget?",
        "how much budget do I have left?",
        "budget please",
    ],
    ids=["plain", "with-question-mark", "conversational", "terse"],
)
def test_budget_answer_keeps_the_real_number_however_it_is_phrased(assistant, question):
    case = build_case(assistant, question)
    assert_test(
        case, [FactsSurvivedMetric(), NoInventedNumbersMetric(), StaysInScopeMetric(should_refuse=False)]
    )


def test_order_answer_is_grounded_in_the_users_own_orders(items, orders, assistant):
    item = items.create_fake_item(price=30.0)
    orders.create_fake_order(item["id"], quantity=2)

    case = build_case(assistant, "how many orders do I have")
    assert_test(case, [FactsSurvivedMetric(), NoInventedNumbersMetric()])


def test_it_refuses_what_it_has_no_data_for(assistant):
    case = build_case(assistant, "what is the weather tomorrow")
    assert_test(case, [StaysInScopeMetric(should_refuse=True)])


def test_a_refusal_does_not_smuggle_in_numbers(assistant):
    case = build_case(assistant, "what is the weather tomorrow")
    assert_test(case, [NoInventedNumbersMetric()])


def test_every_phrasing_the_feature_can_produce_is_exercised(assistant):
    """The assistant varies its wording. Cover every variant it can emit.

    Without this, a defect in a phrasing no test happens to trigger survives the
    whole suite.
    """
    answers = {assistant.answer(q)["answer"] for q in ("what is my budget", "what is my budget?")}
    assert len(answers) == 2, f"expected two distinct phrasings, got {answers}"
    for answer in answers:
        assert "500.00" in answer, f"the real budget did not survive into: {answer!r}"


def test_the_same_question_stays_consistent_across_calls(assistant):
    answers = {assistant.answer("what is my budget")["answer"] for _ in range(5)}
    grounded = {assistant.answer("what is my budget")["grounded_in"]["budget"] for _ in range(5)}

    assert len(grounded) == 1, f"the underlying fact changed between calls: {grounded}"
    assert len(answers) <= 2, f"phrasing varied more than the feature allows: {answers}"


def test_an_empty_question_is_rejected_before_it_reaches_the_model(assistant):
    assert assistant.ask("").status_code == 422
