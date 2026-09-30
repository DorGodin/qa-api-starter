import pytest

from obj.auth import LoginFailed, login


class FakeResponse:
    def __init__(self, status=200, body=None, cookies=None, text=""):
        self.status_code = status
        self._body = body
        self.cookies = cookies or {}
        self.text = text or str(body)

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakePost:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_password_token_sends_json_and_returns_a_bearer_header():
    post = FakePost(FakeResponse(body={"access_token": "t-1"}))

    headers = login(post, "http://api", {"type": "password_token", "path": "/auth/token"}, "admin", "u", "p")

    url, sent = post.calls[0]
    assert url == "http://api/auth/token"
    assert sent["json"] == {"username": "u", "password": "p"}
    assert headers == {"Authorization": "Bearer t-1"}


def test_oauth_password_is_form_encoded_not_json():
    post = FakePost(FakeResponse(body={"access_token": "kc-1"}))
    cfg = {"type": "oauth_password", "token_url": "https://id.test/token", "client_id": "qa"}

    login(post, "http://api", cfg, "admin", "u", "p")

    url, sent = post.calls[0]
    assert url == "https://id.test/token", "an absolute token_url is not glued onto the product url"
    assert "json" not in sent
    assert sent["data"]["grant_type"] == "password"
    assert sent["data"]["client_id"] == "qa"


def test_oauth_reads_the_client_secret_from_the_variable_it_names(monkeypatch):
    monkeypatch.setenv("QA_CLIENT_SECRET", "s3cret")
    post = FakePost(FakeResponse(body={"access_token": "kc-1"}))
    cfg = {
        "type": "oauth_password",
        "token_url": "/t",
        "client_id": "qa",
        "client_secret_env": "QA_CLIENT_SECRET",
    }

    login(post, "http://api", cfg, "admin", "u", "p")

    assert post.calls[0][1]["data"]["client_secret"] == "s3cret"


def test_cookie_token_reads_the_value_from_the_body_when_told_to():
    post = FakePost(FakeResponse(body={"token": "abc"}))
    cfg = {"type": "cookie_token", "path": "/auth", "cookie_name": "token", "token_field": "token"}

    assert login(post, "http://api", cfg, "admin", "u", "p") == {"Cookie": "token=abc"}


def test_cookie_token_reads_the_set_cookie_value_by_default():
    post = FakePost(FakeResponse(body={}, cookies={"session": "xyz"}))
    cfg = {"type": "cookie_token", "path": "/login", "cookie_name": "session"}

    assert login(post, "http://api", cfg, "admin", "u", "p") == {"Cookie": "session=xyz"}


def test_a_rejected_login_names_the_persona_and_never_the_password():
    post = FakePost(FakeResponse(status=401, body={"detail": "bad credentials"}))

    with pytest.raises(LoginFailed) as err:
        login(post, "http://api", {"type": "password_token", "path": "/auth/token"}, "owner", "u", "hunter2")

    assert "owner" in str(err.value) and "401" in str(err.value)
    assert "hunter2" not in str(err.value)


def test_a_successful_login_with_no_token_fails_instead_of_sending_bearer_none():
    post = FakePost(FakeResponse(body={"message": "welcome"}))

    with pytest.raises(LoginFailed, match="access_token"):
        login(post, "http://api", {"type": "password_token", "path": "/auth/token"}, "admin", "u", "p")


def test_an_unknown_auth_type_lists_the_known_ones():
    with pytest.raises(KeyError, match="cookie_token"):
        login(FakePost(FakeResponse()), "http://api", {"type": "saml"}, "admin", "u", "p")


def test_a_200_that_refuses_the_login_shows_the_products_reason():
    post = FakePost(FakeResponse(body={"reason": "Bad credentials"}))
    cfg = {"type": "cookie_token", "path": "/auth", "cookie_name": "token", "token_field": "token"}

    with pytest.raises(LoginFailed, match="Bad credentials"):
        login(post, "http://api", cfg, "owner", "u", "p")
