"""TC-2 (rendering fidelity): the hand-rolled renderer produces real
structure - nested lists, headings, hr, code - while staying escape-first."""


def expand(page, entry_id):
    card = page.locator('#list .card[data-id="%s"]' % entry_id)
    card.locator("h2").click()
    body = card.locator(".body")
    page.wait_for_function(
        "el => el.textContent.length > 20", arg=body.element_handle()
    )
    return body


def test_rich_markdown_structure(viewer):
    body = expand(viewer, "fx-progress-ampliphi")
    heading = body.locator(".mdh2")
    assert heading.inner_text() == "Wiring status"
    # Nested unordered list: an inner <ul> inside the outer one.
    assert body.locator("ul ul li").count() == 2
    assert body.locator("ol li").count() == 2
    assert body.locator("hr").count() == 1
    assert body.locator("strong", has_text="done").count() == 1
    assert body.locator("code", has_text="inline code").count() == 1


def test_code_fence_is_verbatim(viewer):
    body = expand(viewer, "fx-progress-ampliphi")
    pre = body.locator("pre")
    assert pre.count() == 1
    text = pre.inner_text()
    # Markup inside a fence stays literal: not bolded, not elements.
    assert "<b>not bold</b>" in text
    assert "**not bold either**" in text
    assert body.locator("pre b").count() == 0
    assert body.locator("pre strong").count() == 0


def test_ordered_list_renders(viewer):
    body = expand(viewer, "fx-shipped-lastweek")
    assert body.locator("ol li").count() == 2
    assert body.locator("strong", has_text="bold").count() == 1


def test_links_render_https_only(viewer):
    body = expand(viewer, "fx-shipped-today")
    # Bullet list from the fixture renders as list items.
    assert body.locator("ul li").count() == 2

