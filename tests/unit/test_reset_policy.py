import pytest

from tests.conftest import reset_between_modules, reset_for_one_test


class FakeResponse:
    def assert_ok(self, expected):
        return self


class FakeApi:
    def __init__(self):
        self.calls = []

    def request(self, method, path, persona=None, **kwargs):
        self.calls.append((method, path, persona))
        return FakeResponse()


def test_an_environment_with_hooks_is_reset_between_modules():
    api = FakeApi()

    assert reset_between_modules(api, {"env": "local", "test_hooks": True})
    assert api.calls == [("POST", "/_test/reset", "admin")]


def test_a_real_product_is_never_sent_a_reset_it_does_not_have():
    api = FakeApi()

    assert not reset_between_modules(api, {"env": "qa", "test_hooks": False})
    assert api.calls == []


def test_a_test_that_needs_a_clean_slate_is_skipped_with_the_reason_on_a_shared_env():
    api = FakeApi()

    with pytest.raises(pytest.skip.Exception, match="ENV=qa declares test_hooks=false"):
        reset_for_one_test(api, {"env": "qa", "test_hooks": False})
    assert api.calls == []
