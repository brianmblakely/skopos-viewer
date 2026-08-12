# skopos-viewer

Read-only mobile viewer for the private [Skopos](https://github.com/brianmblakely/skopos)
increment store. **Code only - no data, no secrets ever land in this repo.**

Served by GitHub Pages: https://brianmblakely.github.io/skopos-viewer/

## How it works

- Single static `index.html`; no server, no build, no CDN dependencies.
- On first visit it asks for a **fine-grained GitHub PAT** scoped to the
  `skopos` repo only, permission **Contents: Read-only**. The token is kept
  in `localStorage` on the device and sent only to `api.github.com`.
- It fetches `index.json` (ETag-cached) via the GitHub contents API and
  lazy-loads increment bodies on tap. Offline shows the last cached index.
- Read-state (seen increments) also lives in `localStorage`.

The surface is read-only by construction: every code path is a GET, and the
only credential it ever holds cannot write to anything.

On iOS, use Share -> Add to Home Screen: home-screen web apps get durable
storage, so the token survives Safari's 7-day script-storage eviction.
