from utils import http_trace
from utils.http_trace import Call


def setup_function():
    http_trace.clear()


def test_calls_are_listed_in_the_order_they_happened():
    for call in (Call("POST", "/items", 201, "admin"), Call("GET", "/orders", 200, "member")):
        http_trace.record("t", call)

    assert http_trace.steps_for("t") == ["POST /items as admin -> 201", "GET /orders as member -> 200"]


def test_a_step_without_a_persona_reads_cleanly():
    http_trace.record("t", Call("GET", "/health", 200))
    assert http_trace.steps_for("t") == ["GET /health -> 200"]


def test_harness_calls_are_left_out_of_the_steps():
    http_trace.record("t", Call("POST", "/auth/token", 200))
    http_trace.record("t", Call("POST", "/_test/reset", 204, "admin"))
    http_trace.record("t", Call("POST", "/items", 201, "admin"))

    assert http_trace.steps_for("t") == ["POST /items as admin -> 201"]
    assert len(http_trace.steps_for("t", include_harness=True)) == 3


def test_a_test_never_inherits_the_previous_tests_calls():
    http_trace.record("first", Call("POST", "/items", 201))
    http_trace.reset("first")

    assert http_trace.steps_for("first") == []


def test_a_runaway_test_cannot_produce_an_unreadable_ticket():
    for i in range(200):
        http_trace.record("t", Call("GET", f"/items/{i}", 200))

    assert len(http_trace.steps_for("t")) == http_trace.MAX_STEPS
