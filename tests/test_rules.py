"""Risk engine: each rule's trigger AND non-trigger, plus dormancy boundary math."""
from datetime import date

from access_review.ingest import User
from access_review.rules import ReviewConfig, is_high_risk, review

TODAY = date(2026, 10, 14)

CFG = ReviewConfig(
    dormant_days=90,
    stale_days=180,
    role_baseline={"Finance": ["finance:", "ap:", "db:read"],
                   "HR": ["hr:", "db:read"]},
    sod_rules=[["ap:create", "ap:approve"]],
)


def _user(**kw):
    base = dict(username="u", dept="Finance", title="t", manager="jmorgan",
                status="active", last_login=date(2026, 10, 1), created=date(2024, 1, 1),
                mfa_enabled=True, entitlements=["finance:entry"])
    base.update(kw)
    return User(**base)


def _types(users):
    return {f.type for f in review(users, CFG, today=TODAY)}


def _mgr_set(u):
    # include the manager as a real user so orphan rule doesn't fire by accident
    return [u, _user(username=u.manager, manager="jmorgan")]


# --- high-risk / over-privileged detection ---
def test_high_risk_patterns():
    assert is_high_risk("aws:AdministratorAccess", CFG.high_risk_patterns)
    assert is_high_risk("db:*", CFG.high_risk_patterns)
    assert not is_high_risk("db:read", CFG.high_risk_patterns)


def test_over_privileged_trigger_and_safe():
    assert "over_privileged" in _types(_mgr_set(_user(entitlements=["db:*"])))
    assert "over_privileged" not in _types(_mgr_set(_user(entitlements=["db:read"])))


# --- dormancy boundary ---
def test_dormancy_boundary():
    # exactly N days -> not dormant; N+1 -> dormant
    at_threshold = _user(last_login=date(2026, 7, 16))   # 90 days before TODAY
    assert (TODAY - date(2026, 7, 16)).days == 90
    assert "dormant_account" not in _types(_mgr_set(at_threshold))
    over = _user(last_login=date(2026, 7, 15))           # 91 days
    assert "dormant_account" in _types(_mgr_set(over))


def test_disabled_but_active():
    u = _user(status="disabled", last_login=date(2026, 10, 10))
    assert "disabled_but_active" in _types(_mgr_set(u))
    # disabled + old login -> not flagged as "still active"
    u2 = _user(status="disabled", last_login=date(2025, 1, 1))
    assert "disabled_but_active" not in _types(_mgr_set(u2))


def test_stale_account():
    u = _user(last_login=None, created=date(2024, 1, 1))   # never logged, old
    assert "stale_account" in _types(_mgr_set(u))
    u2 = _user(last_login=None, created=TODAY)             # new, no login yet
    assert "stale_account" not in _types(_mgr_set(u2))


def test_orphaned_account():
    missing_mgr = _user(username="x", manager="ghost")
    assert "orphaned_account" in _types([missing_mgr])
    blank_mgr = _user(username="x", manager="")
    assert "orphaned_account" in _types([blank_mgr])
    # present manager -> not orphaned
    assert "orphaned_account" not in _types(_mgr_set(_user(username="x", manager="jmorgan")))


def test_sod_conflict_pair_and_safe_pair():
    conflict = _user(entitlements=["ap:create", "ap:approve", "db:read"])
    assert "sod_conflict" in _types(_mgr_set(conflict))
    safe = _user(entitlements=["ap:create", "db:read"])   # only one half of the pair
    assert "sod_conflict" not in _types(_mgr_set(safe))


def test_mfa_on_privileged():
    no_mfa = _user(mfa_enabled=False, entitlements=["aws:AdministratorAccess"])
    assert "mfa_disabled_privileged" in _types(_mgr_set(no_mfa))
    with_mfa = _user(mfa_enabled=True, entitlements=["aws:AdministratorAccess"])
    assert "mfa_disabled_privileged" not in _types(_mgr_set(with_mfa))
    # mfa off but no privileged access -> not flagged
    no_priv = _user(mfa_enabled=False, entitlements=["db:read"])
    assert "mfa_disabled_privileged" not in _types(_mgr_set(no_priv))


def test_role_baseline_mismatch():
    mismatch = _user(dept="HR", manager="jmorgan", entitlements=["hr:manage", "finance:approver"])
    assert "privilege_mismatch" in _types(_mgr_set(mismatch))
    ok = _user(dept="HR", manager="jmorgan", entitlements=["hr:manage", "db:read"])
    assert "privilege_mismatch" not in _types(_mgr_set(ok))
    # dept absent from baseline -> cannot judge -> no mismatch
    unknown = _user(dept="Legal", manager="jmorgan", entitlements=["anything:here"])
    assert "privilege_mismatch" not in _types(_mgr_set(unknown))
