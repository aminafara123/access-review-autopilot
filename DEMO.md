# 60-second demo script

Goal: show a raw IAM export become a signed-off-ready access review. Record `docs/demo.gif`.

## Setup (before recording)
```bash
pip install -e ".[dev]"
rm -rf out
clear
```

## Recording (~60s)

1. **The problem (5s).** Show the raw export — a wall of users and entitlements:
   ```bash
   column -s, -t access_review/data/sample_users.csv | head -12
   ```

2. **One command (10s).** Run the review on the bundled sample:
   ```bash
   access-review --as-of 2026-10-14
   ```
   Point at the console line: `13 findings across 10 users (high 7, medium 6, low 0)`.

3. **The reviewer worksheet (20s).** Open it — one row per flagged entitlement, with blank
   `decision` / `reviewer` / `notes` columns to fill in:
   ```bash
   column -s, -t out/access_review_worksheet.csv | head -8
   ```
   Call out a high-severity row: an admin grant, an SoD conflict, an orphaned account.

4. **The audit summary (15s).** Show the markdown report — counts by severity/type and the
   per-manager breakdown, with the AI/deterministic honesty banner at the top:
   ```bash
   sed -n '1,20p' out/access_review_summary.md
   ```

5. **The gate (10s).** Prove the core is deterministic and offline:
   ```bash
   pytest -q
   ```
   End on `15 passed`.

## Talking track
"Access certification is a quarterly manual chore for SOX and SOC 2. This reads any IAM
export, applies a deterministic risk engine — dormant, over-privileged, SoD, orphaned, MFA —
and produces a reviewer worksheet plus an audit-ready summary. The LLM only drafts the
narrative, and it's labelled AI-generated: a human signs off."
