"""The headers that keep the booking page from being turned against its users.

The page keeps the sign-in in sessionStorage, which any script running in it can
read. Escaping every name is the first defence; the Content-Security-Policy is
the second, for the day an escape is missed: only the page's own script and
style run, by hash, and nothing is fetched from or sent to another site.
"""

from __future__ import annotations

import base64
import hashlib
import re


def directives(header: str) -> dict[str, list[str]]:
    return {name: values for name, *values in (part.split() for part in header.split(";") if part.strip())}


def sha256(body: str) -> str:
    return f"'sha256-{base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()}'"


def test_the_page_runs_its_own_script_and_style_and_nothing_else(api):
    page = api.request("GET", "/", persona=None)
    policy = directives(page.headers["Content-Security-Policy"])

    (script,) = re.findall(r"<script>(.*?)</script>", page.text, re.S)
    (style,) = re.findall(r"<style>(.*?)</style>", page.text, re.S)
    assert policy["script-src"] == [
        sha256(script)
    ], "exactly the script it serves - no other, and no inline handler"
    assert policy["style-src"] == [sha256(style)]
    assert policy["default-src"] == ["'none'"]
    assert policy["connect-src"] == ["'self'"], "nothing it reads can be sent to another site"
    assert policy["frame-ancestors"] == ["'none'"]
    assert "'unsafe-inline'" not in page.headers["Content-Security-Policy"]
    assert "'unsafe-eval'" not in page.headers["Content-Security-Policy"]


def test_every_answer_carries_the_basic_protections(api):
    for path in ("/", "/shop", "/health"):
        headers = api.request("GET", path, persona=None).headers
        assert headers["X-Content-Type-Options"] == "nosniff", path
        assert headers["X-Frame-Options"] == "DENY", path
        assert headers["Referrer-Policy"] == "no-referrer", path


def test_an_api_answer_is_never_a_page(api):
    policy = directives(api.request("GET", "/shop", persona=None).headers["Content-Security-Policy"])

    assert policy == {"default-src": ["'none'"], "frame-ancestors": ["'none'"]}
