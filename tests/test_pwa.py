"""TC-7 support: manifest correctness and the service worker's
never-touch-api.github.com property."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_manifest_is_relative_and_standalone():
    manifest = json.loads((REPO_ROOT / "manifest.webmanifest").read_text("utf-8"))
    # Project Pages serves under /skopos-viewer/ - absolute paths would break.
    assert manifest["start_url"].startswith("./")
    assert manifest["scope"].startswith("./")
    assert manifest["display"] == "standalone"
    assert len(manifest["icons"]) >= 3
    assert any(i.get("purpose") == "maskable" for i in manifest["icons"])
    for icon in manifest["icons"]:
        assert not icon["src"].startswith("/")
        assert (REPO_ROOT / icon["src"]).exists()


def test_apple_touch_icon_exists_and_opaque():
    from PIL import Image

    path = REPO_ROOT / "icons" / "apple-touch-icon.png"
    assert path.exists()
    img = Image.open(path)
    assert img.size == (180, 180)
    assert img.mode == "RGB"  # opaque - iOS composites transparency onto black


def test_sw_never_intercepts_cross_origin_source_guard():
    src = (REPO_ROOT / "sw.js").read_text("utf-8")
    assert "origin !== self.location.origin" in src
    code_lines = [
        line for line in src.splitlines() if not line.strip().startswith("//")
    ]
    code = "\n".join(code_lines)
    # No non-comment code references any absolute origin: the precache list
    # is same-origin shell files, and api.github.com is never named.
    assert "api.github.com" not in code
    assert "https://" not in code


def test_service_worker_registers_and_caches_no_api(
        browser, browser_name, store, app_server):
    if browser_name == "webkit":
        pytest.skip("playwright webkit cannot intercept SW-controlled traffic")
    from conftest import wire_page

    context = browser.new_context(
        viewport={"width": 390, "height": 844}, service_workers="allow")
    page = context.new_page()
    external_requests, unmatched_api, api_log = [], [], []
    wire_page(page, store, external_requests, unmatched_api, api_log)
    page.add_init_script("localStorage.setItem('skopos_pat', 'test-token')")
    page.goto(app_server + "/index.html")
    page.wait_for_selector("#list .card")
    page.wait_for_function(
        "() => navigator.serviceWorker.getRegistration().then(r => !!r)"
    )
    # Force API traffic with the SW active, then inspect every cache bucket.
    page.click("#refreshBtn")
    page.wait_for_function(
        "() => document.getElementById('fetchedAt').textContent.length > 0"
    )
    cached_urls = page.evaluate(
        """async () => {
            const urls = [];
            for (const name of await caches.keys()) {
              const cache = await caches.open(name);
              for (const req of await cache.keys()) urls.push(req.url);
            }
            return urls;
        }"""
    )
    context.close()
    assert all("api.github.com" not in u for u in cached_urls)
    assert unmatched_api == []

