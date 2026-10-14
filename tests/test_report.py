"""Worksheet generation and summary aggregation."""
import csv
from datetime import date
from pathlib import Path

import access_review
from access_review import ingest, report, rules

DATA = Path(access_review.__file__).parent / "data"
TODAY = date(2026, 10, 14)


def _findings():
    users = ingest.load_users(DATA / "sample_users.csv")
    cfg = rules.load_config(DATA / "role_baseline.json", DATA / "sod_rules.json")
    return rules.review(users, cfg, today=TODAY)


def test_worksheet_columns_and_one_row_per_finding(tmp_path):
    findings = _findings()
    out = tmp_path / "ws.csv"
    report.write_worksheet(findings, out)
    with out.open(newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == report.WORKSHEET_COLUMNS
    assert len(rows) - 1 == len(findings)          # one row per flagged entitlement
    # the decision/reviewer/notes columns ship blank for the reviewer to fill
    for r in rows[1:]:
        assert r[-3:] == ["", "", ""]


def test_summary_counts_add_up():
    findings = _findings()
    stats = report.summarize(findings)
    assert stats["total_findings"] == len(findings)
    assert sum(stats["by_severity"].values()) == len(findings)
    assert sum(stats["by_type"].values()) == len(findings)
    # the bundled sample is designed to trigger every rule
    expected = {
        "orphaned_account", "dormant_account", "disabled_but_active", "stale_account",
        "over_privileged", "mfa_disabled_privileged", "privilege_mismatch", "sod_conflict",
    }
    assert expected == set(stats["by_type"])


def test_summary_markdown_labels_ai_output():
    stats = report.summarize(_findings())
    ai = report.render_summary_md(stats, "x", True, "2026-10-14")
    assert "AI-GENERATED" in ai
    tmpl = report.render_summary_md(stats, "x", False, "2026-10-14")
    assert "deterministic" in tmpl.lower()
