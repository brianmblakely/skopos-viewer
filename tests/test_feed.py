"""TC-1 + TC-4: default feed contents, history toggle, day groups,
divider, unread badge, mark-on-expand-only read state."""


def card_ids(page):
    return page.eval_on_selector_all(
        "#list .card", "els => els.map(e => e.dataset.id)"
    )


def active_ids(store):
    return [e["id"] for e in store["entries"] if e["status"] == "active"]


def test_default_feed_is_active_only_newest_first(viewer, store):
    ids = card_ids(viewer)
    assert ids == active_ids(store)  # complete, ordered, no superseded/abandoned


def test_history_toggle_reveals_and_restores(viewer, store):
    page = viewer
    all_ids = [e["id"] for e in store["entries"]]
    page.click("#historyBtn")
    assert card_ids(page) == all_ids
    # Non-active entries are visually distinguishable.
    assert "dim" in page.locator(
        '#list .card[data-id="fx-plan-superseded"]').get_attribute("class")
    page.click("#historyBtn")
    assert card_ids(page) == active_ids(store)


def test_history_button_shows_hidden_count(viewer, store):
    hidden = len(store["entries"]) - len(active_ids(store))
    assert "(+%d)" % hidden in viewer.locator("#historyBtn").inner_text()


def test_day_group_headers(viewer):
    heads = viewer.eval_on_selector_all(
        "#list .dayhead", "els => els.map(e => e.textContent)"
    )
    assert heads[0] == "Today"
    assert heads[1] == "Yesterday"
    assert len(heads) >= 4  # today, yesterday, d2, d7, d30 groups


def test_no_divider_on_first_ever_visit(viewer):
    assert viewer.locator("#list .divider").count() == 0


def test_divider_appears_for_new_entries(wire_api, app_server, store):
    page = wire_api
    # Simulate a previous visit that ended one minute after the newest
    # yesterday entry - deterministic regardless of machine timezone.
    from datetime import datetime

    newest_yesterday = max(
        e["created"] for e in store["entries"]
        if not e["created"].startswith(store["entries"][0]["created"][:10])
    )
    watermark = datetime.fromisoformat(newest_yesterday).timestamp() * 1000 + 60000
    page.add_init_script(
        "localStorage.setItem('skopos_pat', 'test-token');"
        "localStorage.setItem('skopos_watermark', '%d');" % watermark
    )
    page.goto(app_server + "/index.html")
    page.wait_for_selector("#list .card")
    divider = page.locator("#list .divider")
    assert divider.count() == 1
    assert "new since" in divider.inner_text()
    # Everything above the divider is strictly newer than the watermark:
    # today's active entries sit above, yesterday's below.
    above = page.evaluate(
        """() => {
            const out = [];
            for (const el of document.querySelectorAll('#list > *')) {
              if (el.classList.contains('divider')) break;
              if (el.classList.contains('card')) out.push(el.dataset.id);
            }
            return out;
        }"""
    )
    todays = [e["id"] for e in store["entries"]
              if e["status"] == "active" and e["created"].startswith(
                  store["entries"][0]["created"][:10])]
    assert above == todays


def test_unread_badge_counts_visible_unread(viewer, store):
    badge = viewer.locator("#unreadBadge")
    assert badge.inner_text() == str(len(active_ids(store)))


def test_expand_marks_read_and_persists(viewer, app_server):
    page = viewer
    card = page.locator('#list .card[data-id="fx-shipped-today"]')
    before = int(page.locator("#unreadBadge").inner_text())
    card.locator("h2").click()
    page.wait_for_function(
        "() => document.querySelector('#list .card[data-id=\\'fx-shipped-today\\'] .body').textContent.length > 20"
    )
    assert "unread" not in card.get_attribute("class")
    assert int(page.locator("#unreadBadge").inner_text()) == before - 1
    # Survives a reload (localStorage-backed).
    page.reload()
    page.wait_for_selector("#list .card")
    card = page.locator('#list .card[data-id="fx-shipped-today"]')
    assert "unread" not in card.get_attribute("class")


def test_scrolling_does_not_mark_read(viewer):
    page = viewer
    before = page.locator("#unreadBadge").inner_text()
    page.mouse.wheel(0, 10000)
    page.wait_for_timeout(300)
    page.mouse.wheel(0, -10000)
    assert page.locator("#unreadBadge").inner_text() == before
    stored = page.evaluate("localStorage.getItem('skopos_read')")
    assert stored in (None, "[]")


def test_link_tap_marks_read(viewer, context):
    page = viewer
    card = page.locator('#list .card[data-id="fx-review-request"]')
    with context.expect_page() as popup:
        card.locator(".links a").first.click()
    popup.value.close()
    assert "unread" not in card.get_attribute("class")

