"""Ingestion: CSV and JSON must normalize to the same User list; field parsing."""
from datetime import date
from pathlib import Path

import access_review
from access_review import ingest

DATA = Path(access_review.__file__).parent / "data"


def test_csv_and_json_parse_identically():
    from_csv = ingest.load_users(DATA / "sample_users.csv")
    from_json = ingest.load_users(DATA / "sample_users.json")
    assert from_csv == from_json
    assert len(from_csv) == 24


def test_field_parsing():
    users = {u.username: u for u in ingest.load_users(DATA / "sample_users.csv")}
    lmartin = users["lmartin"]
    assert lmartin.mfa_enabled is False
    assert lmartin.last_login == date(2026, 9, 20)
    assert lmartin.entitlements == ["aws:AdministratorAccess", "db:read"]

    pstale = users["pstale"]
    assert pstale.last_login is None           # empty -> never logged in
    assert pstale.created == date(2024, 5, 1)

    kbrown = users["kbrown"]
    assert kbrown.manager == ""                # blank manager preserved


def test_unsupported_format_raises(tmp_path):
    bad = tmp_path / "users.txt"
    bad.write_text("nope")
    try:
        ingest.load_users(bad)
        assert False, "expected ValueError"
    except ValueError:
        pass
