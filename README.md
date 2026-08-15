# skopos-viewer

Read-only mobile viewer for the private [Skopos](https://github.com/brianmblakely/skopos)
increment store. **Code only - no data, no secrets ever land in this repo.**

Served by GitHub Pages: https://brianmblakely.github.io/skopos-viewer/

## How it works

- Static app (`index.html` + `sw.js` + `manifest.webmanifest`); no server,
  no build, no CDN dependencies.
- On first visit it asks for a **fine-grained GitHub PAT** scoped to the
  `skopos` repo only, permission **Contents: Read-only**. The token is kept
  in `localStorage` on the device and sent only to `api.github.com`. A CSP
  meta tag pins that: the page cannot connect anywhere else.
- Reads follow the store's machine contract (`CONTRACT.md` in the store):
  resolve HEAD once (ETag-conditional - unchanged stores cost one 304),
  fetch `index.json` + `index.meta.json` pinned to that sha, verify the
  projection hash, and fail open to the cached copy on any inconsistency.
- Increment bodies lazy-load on tap and are cached by id (increments are
  append-only and immutable), so previously read increments work offline.

## Reading surface

- **Active-only feed by default**, newest first, grouped by day; the
  `history (+N)` toggle reveals superseded/abandoned increments (dimmed).
- **"New since last visit" divider** and an unread count; an increment is
  marked read when you expand it or tap one of its links - never by
  scrolling past it.
- **Inbound handoffs** (active `handoff` increments) pin to a strip above
  the timeline.
- `[unverified]` marker on entries from untrusted producer classes
  (parity with the store's `LATEST.md`).
- Supersedes navigation: expanded entries link to what they supersede and
  what superseded them.
- Filters (agent / repo / type) plus free-text search over title, id, and
  tags; filter state lives in the URL hash.
- On tablet-class widths the app switches to a two-pane layout: list on
  the left, reading pane on the right.

The surface is read-only by construction: every code path is a GET, and the
only credential it ever holds cannot write to anything. Read state and the
last-visit watermark are deliberately per-device (localStorage) - syncing
them would require a write path this surface must not have.

## Install (iOS)

Use Share -> Add to Home Screen: home-screen web apps get durable storage,
so the token and read state survive Safari's 7-day script-storage eviction.
The installed app has its own storage partition - enter the token once more
after installing. The service worker caches the app shell only (network-
first, offline fallback); it never touches `api.github.com` responses.

## Tests

`tests/` is a pytest + Playwright harness that serves the repo locally and
intercepts every `api.github.com` call with fixtures - no network, no real
token. CI runs it on chromium and webkit (webkit being the only engine iOS
can run). `test_hostile.py` pins the hostile-frontmatter hardening: title
and body payloads must render inert, with zero requests to any non-GitHub
origin.

```
pip install -r tests/requirements.txt
playwright install chromium webkit
pytest tests/ --browser chromium --browser webkit
```
