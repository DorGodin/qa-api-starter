from http.client import HTTPMessage

import pytest
import requests
from requests.adapters import BaseAdapter

import obj.client as client_module
from obj.client import ApiClient


class SetsASessionCookie(BaseAdapter):
    """A product that sets a session cookie on every response, the way most
    session-based web backends do. Records the Cookie header each request sent."""

    sent_cookies: list = []

    def send(self, request, **kwargs):
        SetsASessionCookie.sent_cookies.append(request.headers.get("Cookie"))
        message = HTTPMessage()
        message["Set-Cookie"] = f"session=for-{request.url.rsplit('/', 1)[-1]}; Path=/"
        raw = type("Raw", (), {"_original_response": type("Original", (), {"msg": message})()})()
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"access_token": "token"}'
        response.raw = raw
        response.request = request
        response.url = request.url
        response.headers = requests.structures.CaseInsensitiveDict({"Content-Type": "application/json"})
        return response

    def close(self):
        pass


class SessionThatSetsCookies(requests.Session):
    def __init__(self):
        super().__init__()
        self.mount("http://", SetsASessionCookie())


@pytest.fixture
def client(monkeypatch):
    SetsASessionCookie.sent_cookies = []
    monkeypatch.setattr(client_module.requests, "Session", SessionThatSetsCookies)
    return ApiClient(env="local")


def test_a_cookie_the_product_sets_never_rides_along_on_a_later_request(client):
    client.request("GET", "/owner-area", persona=None)
    client.request("GET", "/customer-area", persona=None)

    assert SetsASessionCookie.sent_cookies == [None, None]


def test_a_cookie_set_at_login_does_not_follow_another_persona(client):
    client.register_persona("owner", "owner-user", "pw")
    client.register_persona("customer", "customer-user", "pw")
    SetsASessionCookie.sent_cookies = []

    client.request("GET", "/bookings", persona="customer")

    assert SetsASessionCookie.sent_cookies == [None], "the customer's request carried a login cookie"


def test_each_persona_sends_only_its_own_credential(client):
    client.register_persona("owner", "owner-user", "pw")

    assert client.auth_headers("owner") == {"Authorization": "Bearer token"}
    with pytest.raises(KeyError, match="not registered"):
        client.auth_headers("customer")
