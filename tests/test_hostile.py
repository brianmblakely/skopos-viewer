"""TC-5: hostile frontmatter and bodies must render inert.

This pins the hardening shipped under #2008 c2 (commit 0f7f8c3). It must be
green against the pre-rewrite renderer AND stay green through every later
change. If this file fails, the viewer does not ship.
"""


def _expand_hostile_card(page):
    card = page.locator(".card", has_text="HOSTILE-FIXTURE").first
    card.locator("h2").click()
    body = card.locator(".body")
    page.wait_for_function(
        "el => el.textContent.includes('__pwned')",
        arg=body.element_handle(),
    )
    return card, body


def test_hostile_entry_renders_inert(viewer, external_requests):
    page = viewer
    card, body = _expand_hostile_card(page)

    # 1. Nothing executed - neither title payloads nor body payloads.
    assert page.evaluate("window.__pwned") is None

    # 2. No element injection: the img payloads must not become elements.
    assert page.locator("img").count() == 0
    assert page.locator("script[src]").count() == 0

    # 3. Payloads are visible as literal text, not consumed as markup.
    body_text = body.inner_text()
    assert "<script>window.__pwned = 1</script>" in body_text
    assert "javascript:alert(1)" in body_text

    # 4. Every anchor on the page is https - the javascript: link must not
    #    have become a link, and attribute breakouts stay inside the value.
    hrefs = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )
    assert hrefs, "expected rendered links elsewhere on the page"
    assert all(h.startswith("https://") for h in hrefs)

    # 5. No request ever left for a non-api.github.com origin (beacons).
    assert external_requests == []


def test_hostile_title_inert_without_expanding(viewer, external_requests):
    page = viewer
    card = page.locator(".card", has_text="HOSTILE-FIXTURE").first
    title = card.locator("h2").inner_text()
    assert "onerror=" in title  # literal text, not an attribute
    assert page.evaluate("window.__pwned") is None
    assert card.locator("img").count() == 0
    assert external_requests == []


def test_hostile_link_urls_stay_inside_attributes(viewer):
    page = viewer
    card = page.locator(".card", has_text="HOSTILE-FIXTURE").first
    # The issue URL carries a quote + onclick payload; it must survive as
    # data inside href, never become an attribute of its own.
    issue_link = card.locator(".links a", has_text="issue").first
    href = issue_link.get_attribute("href")
    assert href.startswith("https://github.com/x/y/issues/1")
    assert issue_link.get_attribute("onclick") is None

