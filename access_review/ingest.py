"""Load IAM/identity exports (CSV or JSON) into one common User model.

CSV and JSON must normalize to the same User list (tested). Entitlements live
in a single `;`-separated CSV field, or a native JSON list.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional

ENT_SEP = ";"  # entitlement separator inside a single CSV field


@dataclass
class User:
    username: str
    dept: str
    title: str
    manager: str
    status: str                  # "active" | "disabled"
    last_login: Optional[date]   # None = never logged in
    created: Optional[date]
    mfa_enabled: bool
    entitlements: List[str] = field(default_factory=list)


def _parse_date(value) -> Optional[date]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return date.fromisoformat(s)  # fail loud on a bad date at the trust boundary


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "t")


def _norm_ents(value) -> List[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else str(value).split(ENT_SEP)
    return [str(e).strip() for e in items if str(e).strip()]


def _user_from_dict(row: dict) -> User:
    return User(
        username=str(row.get("username", "")).strip(),
        dept=str(row.get("dept", "")).strip(),
        title=str(row.get("title", "")).strip(),
        manager=str(row.get("manager", "")).strip(),
        status=(str(row.get("status", "")).strip().lower() or "active"),
        last_login=_parse_date(row.get("last_login")),
        created=_parse_date(row.get("created")),
        mfa_enabled=_parse_bool(row.get("mfa_enabled")),
        entitlements=_norm_ents(row.get("entitlements")),
    )


def load_users(path) -> List[User]:
    """Load users from a .csv or .json export into a list of User."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".json":
        rows = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(rows, dict):           # tolerate {"users": [...]}
            rows = rows.get("users", [])
    elif suffix == ".csv":
        with p.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        raise ValueError(f"Unsupported input format '{suffix}' (use .csv or .json)")
    return [_user_from_dict(r) for r in rows]
