"""iPad-class two-pane layout: list + reading pane at tablet widths,
phone flow untouched below the breakpoint."""

import pytest


@pytest.fixture()
def wide_viewer(wire_api, app_server):
    page = wire_api
    page.set_viewport_size({"width": 1024, "height": 768})
    page.add_init_script("localStorage.setItem('skopos_pat', 'test-token')")
    page.goto(app_server + "/index.html")
    page.wait_for_selector("#list .card")
    return page


def test_select_opens_reading_pane(wide_viewer):
    page = wide_viewer
    card = page.locator('#list .card[data-id="fx-shipped-today"]')
    card.locator("h2").click()
    reader = page.locator("#reader")
    page.wait_for_function(
        "el => !el.classList.contains('hidden') && el.textContent.length > 40",
        arg=reader.element_handle(),
    )
    assert "viewer feature slice" in reader.locator("h2").inner_text()
    assert reader.locator(".chips .chip").count() >= 4
    # The list card did NOT inline-expand; it is marked selected + read.
    assert "hidden" in card.locator(".body").get_attribute("class")
    assert "selected" in card.get_attribute("class")
    assert "unread" not in card.get_attribute("class")


def test_supersedes_navigation_in_pane(wide_viewer):
    page = wide_viewer
    page.locator('#list .card[data-id="fx-shipped-today"] h2').click()
    reader = page.locator("#reader")
    page.wait_for_function(
        "el => el.querySelectorAll('.suprow').length > 0",
        arg=reader.element_handle(),
    )
    reader.locator("button.suplink").first.click()
    page.wait_for_function(
        "el => el.querySelector('h2').textContent.includes('scoped')",
        arg=reader.element_handle(),
    )
    # Target was revealed in the list despite history being off.
    assert page.locator('#list .card[data-id="fx-plan-superseded"]').count() == 1


def test_narrow_viewport_keeps_inline_flow(wide_viewer):
    page = wide_viewer
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(200)  # matchMedia change listener re-renders
    card = page.locator('#list .card[data-id="fx-progress-sparse"]')
    card.locator("h2").click()
    body = card.locator(".body")
    page.wait_for_function(
        "el => el.textContent.includes('Sparse entry')",
        arg=body.element_handle(),
    )
    assert page.locator("#reader").is_hidden()

