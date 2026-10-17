"""Command line entry point.

    python -m opsintel.cli setup        # generate synthetic sources + run ETL (fresh database)
    python -m opsintel.cli etl          # re-run ETL only
    python -m opsintel.cli ask "Why did costs rise this month?" --user opsmgr.demo [--engine rules|claude]
    python -m opsintel.cli docs         # regenerate docs/data_dictionary.md from the catalogue
    python -m opsintel.cli servicenow-test          # check SN_* credentials and table read access
    python -m opsintel.cli servicenow-sync          # extract a ServiceNow instance -> data_servicenow/ -> ETL
"""
from __future__ import annotations

import argparse
import json

from opsintel import config, db


def setup():
    from opsintel.datagen import generate
    from opsintel.etl.pipeline import run_pipeline

    generate.main()
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    report = run_pipeline()
    print(f"ETL run {report['_run']['run_id']} complete; foreign-key violations: {report['_run']['foreign_key_violations']}")
    data_dictionary()


def data_dictionary():
    lines = ["# Data dictionary", "", "_Generated from the metadata catalogue (`opsintel/db.py`) by `python -m opsintel.cli docs`._", "",
             "## Metric definitions", ""]
    lines += [f"- **{k}** - {v}" for k, v in db.METRIC_DEFINITIONS.items()]
    with db.session(readonly=True) as con:
        for table in [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")]:
            if table.startswith("sqlite_"):
                continue
            cols = con.execute(f"PRAGMA table_info({table})").fetchall()
            cat = {r[1]: r for r in con.execute("SELECT * FROM catalog WHERE table_name=?", (table,))}
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            lines += ["", f"## {table}", "", f"{n:,} rows", "", "| Column | Type | Description | PII | Source |", "|---|---|---|---|---|"]
            for c in cols:
                meta = cat.get(c[1])
                lines.append(f"| {c[1]} | {c[2] or ''} | {meta[2] if meta else ''} | {'yes' if meta and meta[3] else ''} | {meta[4] if meta else ''} |")
    from opsintel.etl.servicenow import FIELD_MAP

    lines += ["", "## ServiceNow source mapping", "",
              "When the platform is loaded from a ServiceNow instance (`make sn-sync`), the tables above are filled as follows. "
              "The same validation, entity matching, quarantine and lineage apply.", "",
              "| Platform field | ServiceNow source | Rule |", "|---|---|---|"]
    lines += [f"| `{t}` | `{src}` | {rule} |" for t, src, rule in FIELD_MAP]
    (config.ROOT / "docs" / "data_dictionary.md").write_text("\n".join(lines) + "\n")
    print("Wrote docs/data_dictionary.md")


def servicenow_test():
    from opsintel.etl.servicenow import Credentials, ServiceNowClient, check_access

    creds = Credentials.from_env()
    client = ServiceNowClient(creds)
    try:
        print(f"Instance: {creds.instance}   auth: {creds.mode} ({creds.principal})")
        for table, status in check_access(client).items():
            print(f"  {table:16} {status}")
    finally:
        client.close()


def servicenow_sync(since_days: int | None):
    from opsintel.etl.pipeline import run_pipeline
    from opsintel.etl.servicenow import Credentials, ServiceNowClient, extract, land

    creds = Credentials.from_env()
    out = config.ROOT / "data_servicenow"
    client = ServiceNowClient(creds)
    try:
        print(f"Extracting from {creds.instance} ...")
        raw = extract(client, since_days)
    finally:
        client.close()
    manifest = land(raw, out, creds.instance)
    print(json.dumps({k: manifest[k] for k in ("rows", "api_requests", "data_start", "snapshot_date", "mapping_gaps")}, indent=2))
    config.use_data_dir(out)
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    report = run_pipeline()
    inc = report.get("incidents", {})
    print(f"ETL run {report['_run']['run_id']}: incidents loaded {inc.get('after', {}).get('rows')}, "
          f"rejected {inc.get('rejects', {})}, FK violations {report['_run']['foreign_key_violations']}")
    print("Open the dashboard on this data with:  OPSINTEL_DATA_DIR=data_servicenow make ui")


def main():
    ap = argparse.ArgumentParser(prog="opsintel")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    sub.add_parser("etl")
    sub.add_parser("docs")
    sub.add_parser("servicenow-test")
    sn = sub.add_parser("servicenow-sync")
    sn.add_argument("--since-days", type=int, default=None, help="only incidents/requests opened in the last N days")
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.add_argument("--user", default="opsmgr.demo")
    a.add_argument("--engine", default="auto", choices=["auto", "rules", "claude"])
    a.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.cmd == "setup":
        setup()
    elif args.cmd == "etl":
        from opsintel.etl.pipeline import run_pipeline

        print(json.dumps(run_pipeline()["_run"]))
    elif args.cmd in ("servicenow-test", "servicenow-sync"):
        from opsintel.etl.servicenow import ServiceNowError

        try:
            servicenow_test() if args.cmd == "servicenow-test" else servicenow_sync(args.since_days)
        except ServiceNowError as e:
            raise SystemExit(f"ServiceNow: {e}")
    elif args.cmd == "docs":
        data_dictionary()
    elif args.cmd == "ask":
        from opsintel.ai.assistant import ask

        ans = ask(args.question, args.user, engine=args.engine)
        if args.json:
            print(json.dumps({"answer": ans.answer, "engine": ans.engine, "grounding": ans.grounding,
                              "evidence": [{"id": e.evidence_id, "tool": e.tool, "summary": e.summary} for e in ans.evidence]}, indent=2))
        else:
            print(ans.answer)
            print(f"\n-- engine={ans.engine} figures={ans.grounding['figures']} ungrounded={ans.grounding['ungrounded']}")
            for e in ans.evidence:
                print(f"   [{e.evidence_id}] {e.tool}: {e.summary[:110]}")


if __name__ == "__main__":
    main()
