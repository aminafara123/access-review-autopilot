"""access-review CLI: load an identity export, run the risk engine, write outputs."""
from __future__ import annotations

import argparse
import json
from datetime import date
from importlib import resources
from pathlib import Path

from . import ingest, llm, report, rules


def _bundled(name: str) -> str:
    # ponytail: assumes an unpacked install (pip/pipx); not a zipimport.
    # single-arg joinpath chaining stays valid on Python 3.9/3.10.
    return str(resources.files("access_review").joinpath("data").joinpath(name))


def _narrative_prompt(stats: dict, findings) -> str:
    top = "\n".join(f"- {f.username} [{f.severity}] {f.type}: {f.evidence}"
                    for f in findings[:15])
    return ("Summarise this user access review in 4-6 sentences for a compliance report. "
            "Be factual, do not claim compliance.\n"
            f"Totals: {json.dumps(stats)}\nTop findings:\n{top}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="access-review",
        description="Automate user access reviews / access certification (SOX, SOC 2, ISO 27001).")
    ap.add_argument("-i", "--input", help="IAM/identity export (.csv or .json). Default: bundled sample.")
    ap.add_argument("-o", "--out", default="out", help="Output directory (default: ./out)")
    ap.add_argument("--baseline", help="Role-baseline JSON (dept -> allowed prefixes). Default: bundled.")
    ap.add_argument("--sod", help="SoD conflict-rules JSON (list of [entA, entB]). Default: bundled.")
    ap.add_argument("--dormant-days", type=int, default=90)
    ap.add_argument("--stale-days", type=int, default=180)
    ap.add_argument("--as-of", help="Reference date YYYY-MM-DD for dormancy math (default: today).")
    ap.add_argument("--no-llm", action="store_true", help="Skip the LLM narrative; use the template.")
    args = ap.parse_args(argv)

    input_path = args.input or _bundled("sample_users.csv")
    baseline_path = args.baseline or _bundled("role_baseline.json")
    sod_path = args.sod or _bundled("sod_rules.json")
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()

    users = ingest.load_users(input_path)
    cfg = rules.load_config(baseline_path, sod_path,
                            dormant_days=args.dormant_days, stale_days=args.stale_days)
    findings = rules.review(users, cfg, today=as_of)
    stats = report.summarize(findings)

    narrative, is_ai = report.template_narrative(stats), False
    if not args.no_llm:
        text = llm.chat(_narrative_prompt(stats, findings),
                        system="You are a GRC analyst summarising an access review. Be concise and factual.")
        if text:
            narrative, is_ai = text, True

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ws = report.write_worksheet(findings, out / "access_review_worksheet.csv")
    md = out / "access_review_summary.md"
    md.write_text(report.render_summary_md(stats, narrative, is_ai, as_of.isoformat()), encoding="utf-8")
    sj = out / "access_review_summary.json"
    sj.write_text(json.dumps({"as_of": as_of.isoformat(), **stats,
                              "findings": [f.__dict__ for f in findings]}, indent=2), encoding="utf-8")

    sev = stats["by_severity"]
    print(f"Access review as of {as_of.isoformat()}: {stats['total_findings']} findings "
          f"across {stats['users_flagged']} users "
          f"(high {sev.get('high', 0)}, medium {sev.get('medium', 0)}, low {sev.get('low', 0)}).")
    print(f"  worksheet: {ws}")
    print(f"  summary:   {md}")
    print(f"  summary:   {sj}")
    if not args.no_llm and not is_ai:
        print("  note: LLM unreachable -> narrative used the deterministic template.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
