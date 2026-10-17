import json

import pandas as pd

from eval import ground_truth as gt
from opsintel import config, db
from opsintel.etl.pipeline import run_pipeline
from opsintel.etl.quality import EntityMatcher, Rules, parse_datetime, profile


def test_pipeline_reconciles_with_truth(tmp_path):
    path = tmp_path / "fresh.db"
    report = run_pipeline(path)
    assert report["_run"]["foreign_key_violations"] == 0
    with db.session(path, readonly=True) as con:
        for table in ("incidents", "service_requests", "alerts", "costs"):
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert n == len(gt.t(table)), table
        lineage = {r[0] for r in con.execute("SELECT target_table FROM lineage")}
        assert {"incidents", "service_requests", "alerts", "costs", "services", "assets"} <= lineage
        loaded = pd.read_sql_query("SELECT incident_id, service_id, priority FROM incidents", con)
    truth = gt.t("incidents")[["incident_id", "service_id", "priority"]]
    merged = truth.merge(loaded, on="incident_id", suffixes=("_t", "_l"))
    assert (merged.service_id_t == merged.service_id_l).all(), "entity matching mapped a service wrongly"
    assert (merged.priority_t == merged.priority_l).all(), "priority imputation disagrees with the impact x urgency matrix"


def test_rejects_are_quarantined_with_reasons(tmp_path):
    report = run_pipeline(tmp_path / "r.db")
    manifest = json.loads((config.DATA_DIR / "generation_manifest.json").read_text())
    assert sum(report["incidents"]["rejects"].values()) == manifest["injected_defects"]["incidents"]["junk_rows"]
    assert set(report["incidents"]["rejects"]) == {"test_record", "invalid_timestamps", "orphan_customer"}
    after = report["incidents"]["after"]
    assert after["duplicate_keys"] == 0 and after["schema_violations"] == 0 and after["unmatched_references"] == 0


def test_entity_matcher_levels():
    m = EntityMatcher({"SVC-004": "Business Broadband & SD-WAN", "SVC-010": "Colocation"}, {"SVC-004": ["bb & sd-wan"]})
    assert m.match("  business broadband and sd-wan ") == "SVC-004"
    assert m.match("BB & SD-WAN") == "SVC-004"
    assert m.match("Colocaton") == "SVC-010"          # typo -> fuzzy
    assert m.match("Quantum Computing") is None
    assert m.stats == {"exact_or_normalised": 2, "fuzzy": 1, "unmatched": 1}


def test_parse_datetime_accepts_iso_and_uk():
    s = parse_datetime(pd.Series(["2026-03-04 13:22:00", "04/03/2026 13:22:00", ""]))
    assert s.iloc[0] == s.iloc[1] == pd.Timestamp("2026-03-04 13:22:00")
    assert pd.isna(s.iloc[2])


def test_profile_counts_defects():
    df = pd.DataFrame({"id": ["1", "1", "2"], "d": ["2026-01-01", "2026-01-01", "01/02/2026"], "p": ["P1", "P1", "PX"]})
    m = profile(df, Rules(key=["id"], required=["id"], iso_dates=["d"], enums={"p": {"P1", "P2"}}))
    assert m["exact_duplicate_rows"] == 1 and m["duplicate_keys"] == 1 and m["schema_violations"] == 2
