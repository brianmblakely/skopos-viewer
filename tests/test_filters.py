"""TC-3: filters and search narrow correctly, compose, clear, and
round-trip through the URL hash."""


def card_ids(page):
    return page.eval_on_selector_all(
        "#list .card", "els => els.map(e => e.dataset.id)"
    )


def test_agent_filter(viewer, store):
    viewer.select_option("#agentFilter", "codex")
    expected = [e["id"] for e in store["entries"]
                if e["status"] == "active" and e["agent"] == "codex"]
    assert card_ids(viewer) == expected


def test_repo_filter(viewer, store):
    viewer.select_option("#repoFilter", "brianmblakely/skopos-viewer")
    ids = card_ids(viewer)
    assert "fx-shipped-today" in ids
    assert "fx-plan-codex" in ids
    assert "fx-progress-ampliphi" not in ids


def test_type_filter(viewer):
    viewer.select_option("#typeFilter", "shipped")
    assert card_ids(viewer) == ["fx-shipped-today", "fx-shipped-lastweek"]


def test_search_matches_title_id_and_tags(viewer):
    page = viewer
    page.fill("#searchInput", "sidecar")
    page.wait_for_timeout(300)  # debounce
    assert card_ids(page) == ["fx-plan-codex"]
    page.fill("#searchInput", "fx-progress-sparse")  # id match
    page.wait_for_timeout(300)
    assert card_ids(page) == ["fx-progress-sparse"]
    page.fill("#searchInput", "epic-3")  # tag match
    page.wait_for_timeout(300)
    assert set(card_ids(page)) == {"fx-shipped-today", "fx-plan-codex"}


def test_filters_compose_and_clear(viewer, store):
    page = viewer
    page.select_option("#agentFilter", "claude-code")
    page.select_option("#typeFilter", "progress")
    ids = card_ids(page)
    assert ids == [e["id"] for e in store["entries"]
                   if e["status"] == "active" and e["agent"] == "claude-code"
                   and e["type"] == "progress"]
    page.select_option("#agentFilter", "")
    page.select_option("#typeFilter", "")
    assert card_ids(page) == [e["id"] for e in store["entries"]
                              if e["status"] == "active"]


def test_no_match_message(viewer):
    page = viewer
    page.fill("#searchInput", "zz-no-such-increment")
    page.wait_for_timeout(300)
    assert card_ids(page) == []
    assert "no increments match" in page.locator("#status").inner_text()


def test_hash_roundtrip_survives_reload(viewer):
    page = viewer
    page.select_option("#agentFilter", "claude-code")
    page.click("#historyBtn")
    assert "agent=claude-code" in page.url
    assert "hist=1" in page.url
    page.reload()
    page.wait_for_selector("#list .card")
    assert page.locator("#agentFilter").input_value() == "claude-code"
    ids = card_ids(page)
    assert "fx-plan-superseded" in ids  # history stayed on
    assert all(i.startswith("fx-") for i in ids)

