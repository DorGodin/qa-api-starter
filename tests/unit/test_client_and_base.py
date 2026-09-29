import pytest

from obj.base import Base
from obj.client import Response


class FakeRequest:
    method = "GET"
    url = "http://api.test/orders"


class FakeRaw:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = b"x" if payload is not None or text else b""
        self.request = FakeRequest()
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_empty_body_reads_as_an_empty_dict():
    assert Response(FakeRaw(status_code=204)).as_dict == {}


def test_non_json_body_is_surfaced_not_swallowed():
    assert Response(FakeRaw(status_code=200, text="<html>")).as_dict == {"raw_text": "<html>"}


def test_content_defaults_to_an_empty_list():
    assert Response(FakeRaw(payload={"total": 0})).content == []


def test_assert_ok_returns_self_so_calls_can_chain():
    resp = Response(FakeRaw(payload={"id": 1}))
    assert resp.assert_ok(200) is resp


def test_assert_ok_message_names_the_request_and_the_body():
    resp = Response(FakeRaw(status_code=422, text="price must be greater than 0", payload=None))
    with pytest.raises(AssertionError) as err:
        resp.assert_ok(201)

    message = str(err.value)
    assert "GET" in message and "http://api.test/orders" in message
    assert "422" in message and "expected (201,)" in message
    assert "price must be greater than 0" in message


class StubClient:
    def __init__(self, rows):
        self.rows = rows
        self.config = {"env": "staging"}

    def request(self, method, path, persona="__active__", **kwargs):
        return Response(FakeRaw(payload={"total": len(self.rows), "content": self.rows}))


class Widgets(Base):
    resource = "widgets"


def test_resource_is_mandatory():
    class NoResource(Base):
        pass

    with pytest.raises(ValueError, match="must set `resource`"):
        NoResource(StubClient([]))


def test_path_is_built_from_the_resource():
    assert Widgets(StubClient([])).path == "/widgets"


def test_find_first_returns_the_first_row():
    assert Widgets(StubClient([{"id": "a"}, {"id": "b"}])).find_first() == {"id": "a"}


def test_find_first_names_the_environment_when_nothing_matches():
    with pytest.raises(AssertionError) as err:
        Widgets(StubClient([])).find_first(params={"name": "ghost"})

    assert "widgets" in str(err.value)
    assert "staging" in str(err.value), "the message must say which environment was searched"
