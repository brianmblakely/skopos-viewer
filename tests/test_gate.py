"""PAT gate behavior: empty token, save-and-load, forget."""

from conftest import TEST_PAT


def test_gate_shows_without_token(wire_api, app_server):
    page = wire_api
    page.goto(app_server + "/index.html")
    assert page.locator("#gate").is_visible()
    assert page.locator("#topbar").is_hidden()


def test_empty_token_is_rejected(wire_api, app_server):
    page = wire_api
    page.goto(app_server + "/index.html")
    page.click("#patSave")
    assert page.locator("#gateError").inner_text().strip() != ""
    assert page.locator("#gate").is_visible()


def test_save_token_loads_feed(wire_api, app_server):
    page = wire_api
    page.goto(app_server + "/index.html")
    page.fill("#patInput", TEST_PAT)
    page.click("#patSave")
    page.wait_for_selector("#list .card")
    assert page.locator("#topbar").is_visible()
    assert page.locator("#gate").is_hidden()


def test_forget_token_returns_to_gate(viewer):
    page = viewer
    page.click("#forgetBtn")
    assert page.locator("#gate").is_visible()
    assert page.evaluate("localStorage.getItem('skopos_pat')") is None

