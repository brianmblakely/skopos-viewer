"""Fixture-drift guard: the fixture store must conform to CONTRACT.md.

If the store contract changes, this fails first - update fixtures and
viewer together, never let them drift apart silently.
"""

from pathlib import Path

from conftest import FIXTURES

REQUIRED = {"agent", "created", "id", "path", "status", "title", "trusted", "type"}
ALL_KEYS = REQUIRED | {
    "commit", "depends_on", "evidence", "issue", "pr", "repo", "supersedes", "tags"
}
TYPES = {"handoff", "plan", "progress", "review-request", "shipped"}
STATUSES = {"abandoned", "active", "superseded"}


def test_entries_conform_to_contract(store):
    entries = store["entries"]
    assert len(entries) >= 10
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))
    for e in entries:
        assert REQUIRED <= set(e), "missing required keys: %s" % e["id"]
        assert set(e) <= ALL_KEYS, "unknown keys on %s" % e["id"]
        assert e["type"] in TYPES
        assert e["status"] in STATUSES
        assert isinstance(e["trusted"], bool)
        # Sparse means absent, never null.
        assert all(v is not None for v in e.values())


def test_fixtures_cover_all_enums_and_trust_states(store):
    entries = store["entries"]
    assert {e["type"] for e in entries} == TYPES
    assert {e["status"] for e in entries} == STATUSES
    assert any(e["trusted"] is False for e in entries)
    assert any(e["type"] == "handoff" and e["status"] == "active" for e in entries)
    assert any(e.get("supersedes") for e in entries)


def test_index_is_newest_first(store):
    # All fixture offsets are -05:00, so lexicographic compare is valid.
    created = [e["created"] for e in store["entries"]]
    assert created == sorted(created, reverse=True)


def test_every_entry_has_a_body_fixture(store):
    for e in store["entries"]:
        name = Path(e["path"]).name
        assert (FIXTURES / "bodies" / name).exists(), "no body fixture for %s" % name

