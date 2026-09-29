from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def ui_base_url(env_config):
    return env_config["url"].rstrip("/")


@pytest.fixture(autouse=True)
def _reset_between_ui_tests(fresh_state):
    """Every UI test starts from a clean slate.

    A browser test reads whatever is on the screen, so leftover rows from an
    earlier test do not just add noise, they change what `.first` and `.last`
    point at.
    """


@pytest.fixture
def signed_in(page, ui_base_url, env_config):
    """Sign in through the real form, not by injecting a token.

    A UI suite that fakes the login stops covering the login.
    """

    def _sign_in(persona: str = "member"):
        passwords = {"admin": "admin-secret", "member": "member-secret"}
        page.goto(ui_base_url)
        page.get_by_test_id("username").fill(env_config[f"{persona}_user"])
        page.get_by_test_id("password").fill(passwords[persona])
        page.get_by_test_id("login").click()
        page.get_by_test_id("budget").wait_for()
        return page

    return _sign_in
