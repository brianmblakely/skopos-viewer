"""TC-6 + contract compliance: coherent-pair reads, 304 fast path,
failure taxonomy, offline fallbacks."""

import json

import pytest


def seed_and_load(page, app_server):
    page.add_init_script("localStorage.setItem('skopos_pat', 'test-token')")
    page.goto(app_server + "/index.html")
    page.wait_for_selector("#list .card")


def test_coherent_pair_fetch(wire_api, app_server, api_log):
    seed_and_load(wire_api, app_server)
    assert any(p.endswith("/commits/main") for p in api_log)
    assert any(p.endswith("/contents/index.json") for p in api_log)
    assert any(p.endswith("/contents/index.meta.json") for p in api_log)


def test_refresh_304_skips_contents_fetch(wire_api, app_server, api_log, browser_name):
    if browser_name == "webkit":
        pytest.skip("webkit route layer cannot fulfill 304; logic covered on chromium")
    page = wire_api
    seed_and_load(page, app_server)
    index_fetches = len([p for p in api_log if p.endswith("/contents/index.json")])
    page.click("#refreshBtn")
    page.wait_for_function(
        "() => document.getElementById('fetchedAt').textContent.includes('up to date')"
    )
    after = len([p for p in api_log if p.endswith("/contents/index.json")])
    assert after == index_fetches  # 304 on commits/main short-circuited
    assert page.locator("#list .card").count() > 0


def test_meta_404_treated_as_v1(wire_api, app_server):
    page = wire_api
    page.route(
        "https://api.github.com/**/contents/index.meta.json*",
        lambda route: route.fulfill(status=404, body="{}"),
    )
    seed_and_load(page, app_server)
    assert page.locator("#banner").is_hidden()
    assert page.locator("#list .card").count() > 0


def test_newer_schema_degrades_gracefully(wire_api, app_server):
    page = wire_api
    wrapped = json.dumps({"schema_version": 2, "entries": []})
    page.route(
        "https://api.github.com/**/contents/index.json*",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=wrapped),
    )
    page.route(
        "https://api.github.com/**/contents/index.meta.json*",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body='{"projection": "sha256:000000000000", "schema_version": 2}'),
    )
    page.add_init_script("localStorage.setItem('skopos_pat', 'test-token')")
    page.goto(app_server + "/index.html")
    page.wait_for_function(
        "() => document.getElementById('status').textContent.includes('newer than this viewer')"
    )
    assert page.locator("#gate").is_hidden()  # schema drift is not an auth problem


def test_projection_mismatch_fails_open_to_cache(wire_api, app_server, store):
    page = wire_api
    seed_and_load(page, app_server)  # good load primes the cache
    page.evaluate("localStorage.removeItem('skopos_commits_etag')")
    page.route(
        "https://api.github.com/**/contents/index.meta.json*",
        lambda route: route.fulfill(
            status=200, content_type="application/json",
            body='{"projection": "sha256:deadbeef0000", "schema_version": 1}'),
    )
    page.click("#refreshBtn")
    page.wait_for_function(
        "() => document.getElementById('banner').textContent.includes('inconsistent')"
    )
    assert page.locator("#list .card").count() > 0  # cached copy still shown


def test_rate_limit_is_banner_not_gate(wire_api, app_server):
    page = wire_api
    seed_and_load(page, app_server)
    page.evaluate("localStorage.removeItem('skopos_commits_etag')")
    page.route(
        "https://api.github.com/**/commits/main*",
        lambda route: route.fulfill(
            status=403,
            headers={
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "4102444800",
                "Access-Control-Expose-Headers":
                    "ETag, X-RateLimit-Remaining, X-RateLimit-Reset",
            },
            body='{"message": "rate limited"}'),
    )
    page.click("#refreshBtn")
    page.wait_for_function(
        "() => document.getElementById('banner').textContent.includes('rate limited')"
    )
    assert page.locator("#gate").is_hidden()
    assert page.locator("#list .card").count() > 0


def test_401_returns_to_gate(wire_api, app_server):
    page = wire_api
    page.route(
        "https://api.github.com/**/commits/main*",
        lambda route: route.fulfill(status=401, body='{"message": "bad"}'),
    )
    page.add_init_script("localStorage.setItem('skopos_pat', 'bad-token')")
    page.goto(app_server + "/index.html")
    page.wait_for_selector("#gate:not(.hidden)")
    assert "Token rejected" in page.locator("#gateError").inner_text()


def test_404_explains_token_scope(wire_api, app_server):
    page = wire_api
    page.route(
        "https://api.github.com/**/commits/main*",
        lambda route: route.fulfill(status=404, body='{"message": "not found"}'),
    )
    page.add_init_script("localStorage.setItem('skopos_pat', 'scopeless-token')")
    page.goto(app_server + "/index.html")
    page.wait_for_selector("#gate:not(.hidden)")
    assert "lacks access" in page.locator("#gateError").inner_text()


def test_network_failure_falls_back_to_cache(wire_api, app_server):
    page = wire_api
    seed_and_load(page, app_server)
    page.evaluate("localStorage.removeItem('skopos_commits_etag')")
    page.route(
        "https://api.github.com/**/commits/main*",
        lambda route: route.abort(),
    )
    page.click("#refreshBtn")
    page.wait_for_function(
        "() => document.getElementById('banner').textContent.includes('offline')",
        timeout=15000,  # two retries with backoff happen first
    )
    assert page.locator("#list .card").count() > 0


def test_previously_read_body_available_offline(wire_api, app_server):
    page = wire_api
    seed_and_load(page, app_server)
    card = page.locator('#list .card[data-id="fx-progress-sparse"]')
    card.locator("h2").click()
    page.wait_for_function(
        "el => el.textContent.includes('Sparse entry')",
        arg=card.locator(".body").element_handle(),
    )
    # Now sever body fetches and reload: the body must come from the cache.
    page.route(
        "https://api.github.com/**/contents/increments/**",
        lambda route: route.abort(),
    )
    page.reload()
    page.wait_for_selector("#list .card")
    card = page.locator('#list .card[data-id="fx-progress-sparse"]')
    card.locator("h2").click()
    page.wait_for_function(
        "el => el.textContent.includes('Sparse entry')",
        arg=card.locator(".body").element_handle(),
    )


def test_sparse_entry_renders_without_links(viewer):
    card = viewer.locator('#list .card[data-id="fx-progress-sparse"]')
    assert card.locator(".links a").count() == 0
    assert card.locator(".chips .chip").count() >= 4
    text = card.inner_text()
    assert "undefined" not in text and "null" not in text and "NaN" not in text

