"""Test harness for the skopos-viewer static page.

Serves the repo root over localhost (secure context: crypto.subtle and
service workers both work) and intercepts every https://api.github.com
request with fixture responses, so no test ever touches the network or
needs a real PAT. Any api.github.com URL the fixtures don't recognize
fails the test - that catches accidental new endpoints.
"""

import hashlib
import json
import threading
from datetime import datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

COMMITS_ETAG = 'W/"fixture-head"'
TEST_PAT = "test-token"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102 - silence request logging
        pass


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # Phone-class viewport by default: the primary client is iPhone/iPad
    # Safari, and below 760px the viewer uses the inline-expand card flow
    # most tests exercise. Two-pane tests set a wide viewport explicitly.
    #
    # Service workers are blocked in the default context: once the SW claims
    # the page, WebKit routes fetches through it and page.route() no longer
    # intercepts them (the SW never touches api.github.com, but the test
    # harness must). The dedicated SW test opens its own allowing context.
    return {
        **browser_context_args,
        "viewport": {"width": 390, "height": 844},
        "service_workers": "block",
    }


@pytest.fixture(scope="session")
def app_server():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(_QuietHandler, directory=str(REPO_ROOT))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


def _substitute_dates(raw):
    """Replace {dN} tokens with the local calendar date N days ago.

    Fixture times are mid-day at -05:00 so the calendar day is the same
    in UTC (CI) and local (dev) zones.
    """
    now = datetime.now().astimezone()
    for token, days in (("{d0}", 0), ("{d1}", 1), ("{d2}", 2), ("{d7}", 7), ("{d30}", 30)):
        raw = raw.replace(token, (now - timedelta(days=days)).strftime("%Y-%m-%d"))
    return raw


@pytest.fixture(scope="session")
def store():
    """Fixture store: index bytes + a genuinely coherent meta sidecar."""
    raw = (FIXTURES / "index.template.json").read_text(encoding="utf-8")
    index_bytes = _substitute_dates(raw).encode("utf-8")
    digest = hashlib.sha256(index_bytes).hexdigest()[:12]
    meta = {"projection": "sha256:" + digest, "schema_version": 1}
    return {
        "index": index_bytes,
        "meta": json.dumps(meta).encode("utf-8"),
        "entries": json.loads(index_bytes),
    }


@pytest.fixture()
def external_requests():
    """Every request the page issued to a non-fixture, non-local origin."""
    return []


@pytest.fixture()
def unmatched_api():
    return []


@pytest.fixture()
def api_log():
    """Chronological log of fulfilled api.github.com paths."""
    return []


def wire_page(page, store, external_requests, unmatched_api, api_log,
              allow_304=True):
    """Route api.github.com to fixtures; record everything unexpected."""

    def on_request(request):
        host = urlsplit(request.url).netloc
        if host not in ("api.github.com",) and not host.startswith("127.0.0.1"):
            external_requests.append(request.url)

    page.on("request", on_request)

    def handle_api(route, request):
        url = request.url
        path = urlsplit(url).path
        api_log.append(path)
        # The real GitHub API exposes these via Access-Control-Expose-Headers;
        # without it the page cannot read ETag / rate-limit headers cross-origin.
        expose = {"Access-Control-Expose-Headers":
                  "ETag, X-RateLimit-Remaining, X-RateLimit-Reset"}
        if path.endswith("/commits/main"):
            full = dict(
                status=200,
                headers={"ETag": COMMITS_ETAG, **expose},
                content_type="application/json",
                body=(FIXTURES / "commits_main.json").read_bytes(),
            )
            # WebKit's route layer cannot fulfill 304 (allow_304=False there):
            # serve the full response and the viewer takes the normal path.
            if allow_304 and request.headers.get("if-none-match") == COMMITS_ETAG:
                route.fulfill(status=304, headers={"ETag": COMMITS_ETAG, **expose})
            else:
                route.fulfill(**full)
        elif path.endswith("/contents/index/manifest.json"):
            # The fixture store is in the single-file layout: it has no month
            # files, so the viewer's first question is answered "not there"
            # and it reads index.json + index.meta.json (Ampliphi #2719).
            route.fulfill(status=404, body='{"message": "Not Found"}')
        elif path.endswith("/contents/index.json"):
            route.fulfill(
                status=200,
                headers={"ETag": 'W/"fixture-index"'},
                content_type="application/json",
                body=store["index"],
            )
        elif path.endswith("/contents/index.meta.json"):
            route.fulfill(
                status=200, content_type="application/json", body=store["meta"]
            )
        elif "/contents/increments/" in path:
            body_file = FIXTURES / "bodies" / unquote(path.rsplit("/", 1)[-1])
            if body_file.exists():
                route.fulfill(
                    status=200,
                    content_type="text/plain; charset=utf-8",
                    body=body_file.read_bytes(),
                )
            else:
                unmatched_api.append(url)
                route.fulfill(status=404, body="missing fixture body")
        else:
            unmatched_api.append(url)
            route.fulfill(status=500, body="unmatched api route")

    page.route("https://api.github.com/**", handle_api)


@pytest.fixture()
def wire_api(page, store, external_requests, unmatched_api, api_log, browser_name):
    wire_page(page, store, external_requests, unmatched_api, api_log,
              allow_304=(browser_name != "webkit"))
    yield page
    assert unmatched_api == [], "unmatched api.github.com calls: %s" % unmatched_api


@pytest.fixture()
def viewer(wire_api, app_server):
    """The app, PAT pre-seeded, loaded and past the gate."""
    page = wire_api
    page.add_init_script(
        "localStorage.setItem('skopos_pat', '%s')" % TEST_PAT
    )
    page.goto(app_server + "/index.html")
    page.wait_for_selector("#list .card")
    return page
