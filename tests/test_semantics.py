"""Store semantics: handoff prominence, [unverified] markers,
supersedes navigation."""


def test_handoff_strip_pins_active_handoffs(viewer):
    strip = viewer.locator("#handoffStrip")
    assert strip.is_visible()
    items = strip.locator(".stripitem")
    assert items.count() == 1  # only the ACTIVE handoff, not the consumed one
    assert "viewer upgrade context" in items.first.inner_text()


def test_handoff_strip_opens_entry(viewer):
    page = viewer
    page.locator("#handoffStrip .stripitem").first.click()
    card = page.locator('#list .card[data-id="fx-handoff-active"]')
    page.wait_for_function(
        "el => !el.querySelector('.body').classList.contains('hidden')",
        arg=card.element_handle(),
    )
    assert "unread" not in card.get_attribute("class")


def test_unverified_marker_on_untrusted_entry(viewer):
    card = viewer.locator('#list .card[data-id="fx-hostile-entry"]')
    assert card.locator(".chip.unverified").count() == 1
    trusted_card = viewer.locator('#list .card[data-id="fx-shipped-today"]')
    assert trusted_card.locator(".chip.unverified").count() == 0


def test_unverified_note_in_body(viewer):
    page = viewer
    card = page.locator('#list .card[data-id="fx-hostile-entry"]')
    card.locator("h2").click()
    body = card.locator(".body")
    page.wait_for_function(
        "el => el.textContent.includes('unverified')", arg=body.element_handle()
    )
    assert "[unverified]" in body.inner_text()


def test_supersedes_navigation_reveals_hidden_target(viewer):
    page = viewer
    # fx-plan-superseded is hidden by the active-only default.
    assert page.locator('#list .card[data-id="fx-plan-superseded"]').count() == 0
    card = page.locator('#list .card[data-id="fx-shipped-today"]')
    card.locator("h2").click()
    body = card.locator(".body")
    page.wait_for_function(
        "el => el.querySelectorAll('.suprow').length > 0",
        arg=body.element_handle(),
    )
    assert "supersedes" in body.locator(".supnav").inner_text()
    body.locator("button.suplink").first.click()
    target = page.locator('#list .card[data-id="fx-plan-superseded"]')
    page.wait_for_function(
        "() => document.querySelector('#list .card[data-id=\\'fx-plan-superseded\\']') !== null"
    )
    assert target.count() == 1  # revealed despite history off
    assert "unread" not in target.get_attribute("class")


def test_superseded_entry_links_back(viewer):
    page = viewer
    page.click("#historyBtn")  # show history so the superseded card is present
    card = page.locator('#list .card[data-id="fx-plan-superseded"]')
    card.locator("h2").click()
    body = card.locator(".body")
    page.wait_for_function(
        "el => el.querySelectorAll('.suprow').length > 0",
        arg=body.element_handle(),
    )
    assert "superseded by" in body.locator(".supnav").inner_text()

