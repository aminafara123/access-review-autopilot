"""Build the reviewer worksheet (CSV) and the summary report (markdown + JSON)."""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import List

from .rules import Finding

WORKSHEET_COLUMNS = [
    "username", "dept", "manager", "entitlement", "finding_type", "severity",
    "evidence", "recommended_action", "decision", "reviewer", "notes",
]


def write_worksheet(findings: List[Finding], path) -> Path:
    """One row per flagged user+entitlement; blank decision/reviewer/notes to fill in."""
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(WORKSHEET_COLUMNS)
        for fd in findings:
            w.writerow([fd.username, fd.dept, fd.manager, fd.entitlement, fd.type,
                        fd.severity, fd.evidence, fd.recommended_action, "", "", ""])
    return path


def summarize(findings: List[Finding]) -> dict:
    by_sev = Counter(f.severity for f in findings)
    by_type = Counter(f.type for f in findings)
    by_manager: dict = defaultdict(Counter)
    users_flagged = set()
    for f in findings:
        by_manager[f.manager or "(none)"][f.severity] += 1
        users_flagged.add(f.username)
    return {
        "total_findings": len(findings),
        "users_flagged": len(users_flagged),
        "by_severity": dict(by_sev),
        "by_type": dict(by_type),
        "by_manager": {m: dict(c) for m, c in sorted(by_manager.items())},
    }


def template_narrative(stats: dict) -> str:
    sev = stats["by_severity"]
    return (
        f"This access review flagged {stats['total_findings']} findings across "
        f"{stats['users_flagged']} users: {sev.get('high', 0)} high, "
        f"{sev.get('medium', 0)} medium, {sev.get('low', 0)} low severity. "
        "Prioritise the high-severity items (admin/wildcard entitlements, "
        "separation-of-duties conflicts, disabled-but-active accounts, and "
        "privileged accounts without MFA) for revocation or remediation first, "
        "then confirm the medium-severity dormant, orphaned, and out-of-baseline items."
    )


def render_summary_md(stats: dict, narrative: str, is_ai: bool, as_of: str) -> str:
    L = ["# Access Review Summary", "", f"_Generated {as_of} by access-review-autopilot_", ""]
    if is_ai:
        L += ["> **AI-GENERATED narrative below — a human reviewer must validate every decision.**",
              "> Only the narrative is AI-drafted; the findings come from a deterministic rules engine."]
    else:
        L += ["> Narrative below is from a deterministic template (LLM not used).",
              "> All findings come from a deterministic rules engine; a human must review every decision."]
    L += ["", "## Overview", "", narrative, "", "## Findings by severity", "",
          "| Severity | Count |", "|---|---|"]
    for sev in ("high", "medium", "low"):
        if stats["by_severity"].get(sev):
            L.append(f"| {sev} | {stats['by_severity'][sev]} |")

    L += ["", "## Findings by type", "", "| Type | Count |", "|---|---|"]
    for t, c in sorted(stats["by_type"].items(), key=lambda kv: (-kv[1], kv[0])):
        L.append(f"| {t} | {c} |")

    L += ["", "## Findings by manager", "",
          "| Manager | High | Medium | Low | Total |", "|---|---|---|---|---|"]
    for m, c in stats["by_manager"].items():
        hi, md, lo = c.get("high", 0), c.get("medium", 0), c.get("low", 0)
        L.append(f"| {m} | {hi} | {md} | {lo} | {hi + md + lo} |")

    L += ["", "---", "", "_See `access_review_worksheet.csv` for the per-entitlement review worksheet._", ""]
    return "\n".join(L)
