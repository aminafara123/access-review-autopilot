"""Deterministic access-review risk engine. Pure, offline, no LLM, no network.

This is the certification logic: every finding here is reproducible and
explainable from the input + config alone.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from .ingest import User

HIGH, MEDIUM, LOW = "high", "medium", "low"
SEVERITY_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}
ACCOUNT = "(account)"  # entitlement column value for account-level findings

# ponytail: admin/wildcard detection is a static substring list, not a policy
# engine. Add patterns here (or extend ReviewConfig) if the IAM naming differs.
DEFAULT_HIGH_RISK_PATTERNS = ["admin", "*", "root", "owner", "superuser"]


@dataclass
class Finding:
    username: str
    dept: str
    manager: str
    type: str
    severity: str
    entitlement: str          # specific entitlement, a SoD pair, or "(account)"
    evidence: str
    recommended_action: str   # "review" | "revoke"


@dataclass
class ReviewConfig:
    dormant_days: int = 90
    stale_days: int = 180
    high_risk_patterns: List[str] = field(
        default_factory=lambda: list(DEFAULT_HIGH_RISK_PATTERNS))
    # ponytail: role baseline is a static dept -> allowed-prefix map, not role mining.
    role_baseline: Dict[str, List[str]] = field(default_factory=dict)
    # ponytail: SoD rules are explicit entitlement pairs, not inferred toxic combos.
    sod_rules: List[List[str]] = field(default_factory=list)


def load_config(baseline_path=None, sod_path=None, **kw) -> ReviewConfig:
    cfg = ReviewConfig(**kw)
    if baseline_path:
        cfg.role_baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    if sod_path:
        cfg.sod_rules = json.loads(Path(sod_path).read_text(encoding="utf-8"))
    return cfg


def is_high_risk(entitlement: str, patterns) -> bool:
    low = entitlement.lower()
    return any(p in low for p in patterns)


def _fits_baseline(entitlement: str, allowed_prefixes) -> bool:
    return any(entitlement.startswith(pfx) for pfx in allowed_prefixes)


def review(users: List[User], config: ReviewConfig, today: Optional[date] = None) -> List[Finding]:
    """Run every rule against every user; return findings sorted by severity."""
    today = today or date.today()
    names = {u.username for u in users if u.username}
    findings: List[Finding] = []
    for u in users:
        findings.extend(_review_user(u, names, config, today))
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.username, f.entitlement))
    return findings


def _review_user(u: User, names, cfg: ReviewConfig, today: date) -> List[Finding]:
    out: List[Finding] = []

    def add(type_, sev, ent, evidence, action):
        out.append(Finding(u.username, u.dept, u.manager, type_, sev, ent, evidence, action))

    # --- account-level ---
    if not u.manager:
        add("orphaned_account", MEDIUM, ACCOUNT, "No manager/owner assigned", "review")
    elif u.manager not in names:
        add("orphaned_account", MEDIUM, ACCOUNT,
            f"Manager '{u.manager}' not found in directory (left the org?)", "review")

    if u.status == "active" and u.last_login is not None:
        days = (today - u.last_login).days
        if days > cfg.dormant_days:
            add("dormant_account", MEDIUM, ACCOUNT,
                f"No login for {days} days (last {u.last_login.isoformat()}, "
                f"threshold {cfg.dormant_days})", "review")

    if u.status == "disabled" and u.last_login is not None:
        days = (today - u.last_login).days
        if days <= cfg.dormant_days:
            add("disabled_but_active", HIGH, ACCOUNT,
                f"Account marked disabled but logged in {days} days ago "
                f"({u.last_login.isoformat()})", "review")

    if u.last_login is None and u.created is not None:
        age = (today - u.created).days
        if age > cfg.stale_days:
            add("stale_account", MEDIUM, ACCOUNT,
                f"Never logged in; created {age} days ago ({u.created.isoformat()})", "revoke")

    # --- entitlement-level ---
    privileged = [e for e in u.entitlements if is_high_risk(e, cfg.high_risk_patterns)]
    for e in privileged:
        add("over_privileged", HIGH, e, f"High-risk/admin entitlement: {e}", "review")

    if privileged and not u.mfa_enabled:
        add("mfa_disabled_privileged", HIGH, ACCOUNT,
            f"MFA disabled on an account with privileged access ({', '.join(privileged)})",
            "review")

    allowed = cfg.role_baseline.get(u.dept)
    if allowed:  # ponytail: only judge depts present in the baseline; unknown dept = skip
        for e in u.entitlements:
            if not _fits_baseline(e, allowed):
                add("privilege_mismatch", MEDIUM, e,
                    f"Entitlement '{e}' is outside the baseline for dept '{u.dept}'", "revoke")

    held = set(u.entitlements)
    for pair in cfg.sod_rules:
        a, b = pair[0], pair[1]
        if a in held and b in held:
            add("sod_conflict", HIGH, f"{a} + {b}",
                f"Separation-of-duties conflict: holds both '{a}' and '{b}'", "revoke")

    return out
