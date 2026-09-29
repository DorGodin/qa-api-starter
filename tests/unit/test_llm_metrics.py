from deepeval.test_case import LLMTestCase

from utils.llm_metrics import FactsSurvivedMetric, NoInventedNumbersMetric, StaysInScopeMetric


def case(output: str, context=None, refused: bool = False) -> LLMTestCase:
    return LLMTestCase(input="q", actual_output=output, context=context, metadata={"refused": refused})


def test_facts_survived_passes_when_every_number_is_present():
    metric = FactsSurvivedMetric()
    metric.measure(case("You have 500.00 left and 3 orders.", ["budget=500.0", "orders=3"]))

    assert metric.score == 1.0 and metric.is_successful()


def test_facts_survived_scores_partially_and_names_what_is_missing():
    metric = FactsSurvivedMetric()
    metric.measure(case("You have 500.00 left.", ["budget=500.0", "orders=3"]))

    assert metric.score == 0.5
    assert not metric.is_successful()
    assert "3" in metric.reason


def test_facts_survived_passes_when_there_is_nothing_to_ground():
    metric = FactsSurvivedMetric()
    metric.measure(case("I cannot help with that.", context=None))

    assert metric.is_successful(), "a refusal has no facts to keep and must not be penalised"


def test_no_invented_numbers_catches_a_figure_from_nowhere():
    metric = NoInventedNumbersMetric()
    metric.measure(case("Your budget is 999.", ["budget=500.0"]))

    assert metric.score == 0.0
    assert "999" in metric.reason


def test_no_invented_numbers_allows_an_explicitly_ignored_value():
    metric = NoInventedNumbersMetric(ignore={2026.0})
    metric.measure(case("In 2026 your budget is 500.00.", ["budget=500.0"]))

    assert metric.is_successful()


def test_no_invented_numbers_treats_a_reformatted_number_as_the_same_value():
    metric = NoInventedNumbersMetric()
    metric.measure(case("You have 500.00 left.", ["budget=500.0"]))

    assert metric.is_successful(), "500 and 500.00 are the same fact"


def test_stays_in_scope_requires_a_refusal_when_one_is_expected():
    refused = StaysInScopeMetric(should_refuse=True)
    refused.measure(case("I can only answer about budget and orders.", refused=True))
    assert refused.is_successful()

    answered = StaysInScopeMetric(should_refuse=True)
    answered.measure(case("It will be sunny.", refused=False))
    assert not answered.is_successful()


def test_stays_in_scope_fails_a_refusal_that_should_have_been_an_answer():
    metric = StaysInScopeMetric(should_refuse=False)
    metric.measure(case("I cannot help with that.", refused=True))

    assert not metric.is_successful()
    assert "answer" in metric.reason


def test_negative_numbers_are_compared_as_values_not_as_text():
    metric = FactsSurvivedMetric()
    metric.measure(case("Your balance is -12.5.", ["balance=-12.5"]))

    assert metric.is_successful()
