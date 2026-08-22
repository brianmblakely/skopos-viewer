"""TC-1 + TC-2 + TC-4: sharing an increment from the reading surface.

Neither headless engine has a share target, so navigator.share and
navigator.clipboard are seeded by an init script into observable sinks
(window.__shared / window.__clipboard). Assertions are on the payload text
and on the button's own state, never on "the stub was called" - the sink is
a delivery point, not the subject under test.
"""

import pytest
import yaml

SHARE_OK = """
window.__shared = [];
navigator.share = (data) => { window.__shared.push(data); return Promise.resolve(); };
"""

SHARE_ABORTS = """
window.__shared = [];
navigator.share = (data) => {
  window.__shared.push(data);
  const err = new Error('cancelled');
  err.name = 'AbortError';
  return Promise.reject(err);
};
"""

SHARE_ABSENT = """
try { delete navigator.share; } catch (e) {}
Object.defineProperty(navigator, 'share', { value: undefined, configurable: true });
"""

CLIPBOARD = """
window.__clipboard = [];
Object.defineProperty(navigator, 'clipboard', {
  configurable: true,
  value: { writeText: (t) => { window.__clipboard.push(t); return Promise.resolve(); } },
});
"""


def load(page, app_server, *scripts):
    page.add_init_script("localStorage.setItem('skopos_pat', 'test-token')")
    for src in scripts:
        page.add_init_script(src)
    page.goto(app_server + "/index.html")
    page.wait_for_selector("#list .card")
    return page


def expand(page, entry_id):
    card = page.locator('#list .card[data-id="%s"]' % entry_id)
    card.locator("h2").click()
    btn = card.locator("button.sharebtn")
    btn.wait_for()
    return card, btn


def test_share_from_expanded_card_carries_that_increment(wire_api, app_server):
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    card, btn = expand(page, "fx-shipped-today")
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    text = page.evaluate("window.__shared[0].text")
    title = card.locator("h2").inner_text()
    assert 'title: "%s"' % title in text  # the payload is about THIS increment
    assert "shipped" in text and "claude-code" in text
    assert "\n\n" in text  # frontmatter, then prose - not one run-on blob


def test_shared_payload_is_plain_text_not_escaped_html(wire_api, app_server):
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    _, btn = expand(page, "fx-shipped-today")
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    text = page.evaluate("window.__shared[0].text")
    # chipsHTML/linksHTML would have left entities and tags in the clipboard.
    for artifact in ("&amp;", "&quot;", "&lt;", "<span", "<a href", "<div"):
        assert artifact not in text


def test_sparse_entry_shares_without_a_link_tail(wire_api, app_server):
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    _, btn = expand(page, "fx-progress-sparse")
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    text = page.evaluate("window.__shared[0].text")
    # issue/pr/commit/repo are optional in the store schema; absent is not empty.
    assert "issue:" not in text and "pr:" not in text
    assert text.strip()


def test_unverified_marker_travels_with_the_payload(wire_api, app_server):
    """An untrusted increment must not lose its provenance by being shared."""
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    untrusted = page.locator("#list .card").filter(
        has=page.locator(".chip.unverified")).first
    untrusted.locator("h2").click()
    btn = untrusted.locator("button.sharebtn")
    btn.wait_for()
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    assert 'title: "[unverified] ' in page.evaluate("window.__shared[0].text")


def test_long_body_is_truncated_on_a_word_boundary_with_a_marker(wire_api, app_server):
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    _, btn = expand(page, "fx-shipped-today")
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    text = page.evaluate("window.__shared[0].text")
    # blocks: frontmatter, title, excerpt, links, skopos_id
    blocks = text.split("\n\n")
    excerpt = blocks[2]
    assert excerpt and not excerpt.startswith("title:")  # not the header block
    if excerpt.endswith("…"):
        assert not excerpt[:-1].endswith(" ")  # trimmed at the space, not mid-word
    assert len(excerpt) <= 601


def test_share_falls_back_to_clipboard_without_web_share(wire_api, app_server):
    page = load(wire_api, app_server, CLIPBOARD, SHARE_ABSENT)
    _, btn = expand(page, "fx-shipped-today")
    btn.click()
    page.wait_for_function("() => window.__clipboard.length === 1")
    assert btn.inner_text() == "copied"  # the operator is told it worked
    page.wait_for_function(
        "() => document.querySelector('button.sharebtn').textContent === 'share'",
        timeout=4000,
    )


def test_dismissed_share_sheet_is_not_an_error(wire_api, app_server):
    errors = []
    page = wire_api
    page.on("pageerror", lambda e: errors.append(str(e)))
    load(page, app_server, CLIPBOARD, SHARE_ABORTS)
    _, btn = expand(page, "fx-shipped-today")
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    page.wait_for_timeout(200)  # let any rejection surface
    assert errors == []
    assert page.evaluate("window.__clipboard.length") == 0  # cancel != copy
    assert btn.inner_text() == "share"  # no false confirmation
    assert page.locator("#banner").is_hidden()


def test_sharing_does_not_change_read_state(wire_api, app_server):
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    _, btn = expand(page, "fx-shipped-today")
    before = page.locator("#unreadBadge").inner_text()
    stored = page.evaluate("localStorage.getItem('skopos_read')")
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    assert page.locator("#unreadBadge").inner_text() == before
    assert page.evaluate("localStorage.getItem('skopos_read')") == stored


def test_share_control_is_absent_until_the_card_is_expanded(wire_api, app_server):
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    card = page.locator('#list .card[data-id="fx-shipped-today"]')
    # Collapsed rows must not offer it: sharing something unread has no
    # meaning in the read-state model (see test_feed.py).
    assert card.locator("button.sharebtn").count() == 0
    card.locator("h2").click()
    card.locator("button.sharebtn").wait_for()
    assert card.locator("button.sharebtn").count() == 1


def test_reading_pane_offers_the_same_control(wire_api, app_server):
    page = wire_api
    page.set_viewport_size({"width": 1024, "height": 768})
    load(page, app_server, CLIPBOARD, SHARE_OK)
    page.locator('#list .card[data-id="fx-shipped-today"] h2').click()
    btn = page.locator("#reader button.sharebtn")
    btn.wait_for()
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    assert page.evaluate("window.__shared[0].text").strip()


def test_prose_with_angle_brackets_survives_sanitizing(wire_api, app_server):
    """Regression: a blanket <...> strip ate comparisons and generics."""
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    page.wait_for_selector("#list .card")
    out = page.evaluate(
        """(bodies) => {
             const e = {id:'x', title:'T', type:'plan', agent:'a', created:'2026-08-21'};
             return bodies.map((b) => sharePayload(e, b));
           }""",
        ["if x < 5 and y > 3 then ship",
         "returns Promise<string> from the cache",
         "run cmd < in.txt > out.txt"],
    )
    assert "if x < 5 and y > 3 then ship" in out[0]
    assert "Promise<string>" in out[1]
    assert "cmd < in.txt > out.txt" in out[2]


def test_executable_markup_is_still_stripped(wire_api, app_server):
    """The other half of the regression: inert prose kept, executables removed."""
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    out = page.evaluate(
        """(bodies) => {
             const e = {id:'x', title:'T', type:'plan', agent:'a', created:'2026-08-21'};
             return bodies.map((b) => sharePayload(e, b));
           }""",
        ["<script>window.__pwned=1</script> tail",
         '<img src=x onerror="window.__pwned=1"> tail',
         '<div onclick="window.__pwned=1">tail</div>',
         "see [x](javascript:alert(1)) tail"],
    )
    for text in out:
        assert "<script" not in text.lower()
        assert "onerror" not in text.lower()
        assert "onclick" not in text.lower()
        assert "javascript:" not in text.lower()
        assert "tail" in text  # surrounding prose is not collateral damage


def test_clipboard_failure_is_reported_not_swallowed(wire_api, app_server):
    """TC-4: the control must never look like it worked while delivering nothing."""
    page = load(
        wire_api, app_server, SHARE_ABSENT,
        "Object.defineProperty(navigator, 'clipboard', {configurable: true,"
        " value: {writeText: () => Promise.reject(new Error('denied'))}});",
    )
    _, btn = expand(page, "fx-shipped-today")
    btn.click()
    page.wait_for_function(
        "() => document.querySelector('button.sharebtn').textContent === 'copy failed'")
    assert "failed" in btn.get_attribute("class")


def test_missing_clipboard_api_is_reported_not_swallowed(wire_api, app_server):
    page = load(
        wire_api, app_server, SHARE_ABSENT,
        "Object.defineProperty(navigator, 'clipboard',"
        " {configurable: true, value: undefined});",
    )
    _, btn = expand(page, "fx-shipped-today")
    btn.click()
    page.wait_for_function(
        "() => document.querySelector('button.sharebtn').textContent === 'copy failed'")


def test_history_revealed_entry_can_be_shared(wire_api, app_server):
    """TC-1: superseded entries behind the history toggle are a share surface."""
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    page.locator("#historyBtn").click()
    card = page.locator('#list .card[data-id="fx-plan-superseded"]')
    card.locator("h2").click()
    btn = card.locator("button.sharebtn")
    btn.wait_for()
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    assert page.evaluate("window.__shared[0].text").strip()


def test_handoff_strip_entry_can_be_shared(wire_api, app_server):
    """TC-1: the handoff strip opens an entry; that entry must be shareable."""
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    page.locator("#handoffStrip .stripitem").first.click()
    btn = page.locator("button.sharebtn").first
    btn.wait_for()
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    assert page.evaluate("window.__shared[0].text").strip()


def test_share_control_meets_touch_target_guidance(wire_api, app_server):
    """A phone-first action control below ~44px is hard to hit deliberately."""
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    _, btn = expand(page, "fx-shipped-today")
    box = btn.bounding_box()
    assert box["height"] >= 44
    assert box["width"] >= 44


def test_payload_opens_with_frontmatter_the_vault_ingester_reads(wire_api, app_server):
    """The capture contract: obsidian/ingest.py reads these exact keys.

    `date` not `date_captured` - the latter is the column name, not the
    frontmatter key, and getting it wrong loses the date silently.
    """
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    _, btn = expand(page, "fx-shipped-today")
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    text = page.evaluate("window.__shared[0].text")
    head = text.split("---")[1]
    for key in ("title:", "date:", "category:", "description:",
                "status: captured", "tags:", "skopos_id:"):
        assert key in head, key
    assert text.startswith("---" + chr(10))
    assert 'category: "Skopos"' in head  # a registered obsidian category


def test_increment_id_survives_into_the_note_body(wire_api, app_server):
    """The join key back to the store.

    The ingester keeps only its named frontmatter fields and there is no
    skopos_id column, so a frontmatter-only id would be discarded. The body
    copy is what lands in `ideas.body` and stays queryable.
    """
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    _, btn = expand(page, "fx-shipped-today")
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    text = page.evaluate("window.__shared[0].text")
    body = text.split("---", 2)[2]
    assert "skopos_id: fx-shipped-today" in body


def test_hostile_title_cannot_break_out_of_the_frontmatter_block(wire_api, app_server):
    """A raw quote in a title would terminate the YAML scalar and corrupt
    every field after it - the note would ingest as untyped prose."""
    page = load(wire_api, app_server, CLIPBOARD, SHARE_OK)
    untrusted = page.locator("#list .card").filter(
        has=page.locator(".chip.unverified")).first
    untrusted.locator("h2").click()
    btn = untrusted.locator("button.sharebtn")
    btn.wait_for()
    btn.click()
    page.wait_for_function("() => window.__shared.length === 1")
    head = page.evaluate("window.__shared[0].text").split("---")[1]
    # The real contract is "a YAML parser accepts this", not a quote count.
    parsed = yaml.safe_load(head)
    assert isinstance(parsed, dict)
    assert parsed["title"].startswith("[unverified] ")
    assert '"' in parsed["title"]  # the hostile quote round-trips as data
    # Everything after the title is still typed, not swallowed by a broken scalar.
    assert parsed["category"] == "Skopos"
    assert parsed["status"] == "captured"
    assert parsed["skopos_id"] == "fx-hostile-entry"
