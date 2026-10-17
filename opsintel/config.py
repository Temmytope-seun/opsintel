"""Central configuration. Everything is overridable by environment variable."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("OPSINTEL_ROOT", Path(__file__).resolve().parent.parent))


def load_dotenv(path: Path | None = None) -> None:
    """Read KEY=VALUE lines from the git-ignored .env (secrets such as ANTHROPIC_API_KEY,
    SN_CLIENT_SECRET). Variables already set in the environment win."""
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v:  # an empty placeholder must not mask a real value from the environment
            os.environ.setdefault(k.strip(), v)


load_dotenv()
DATA_DIR = Path(os.environ.get("OPSINTEL_DATA_DIR", ROOT / "data"))
KNOWLEDGE_DIR = Path(os.environ.get("OPSINTEL_KNOWLEDGE_DIR", ROOT / "knowledge"))

# The synthetic data set is a snapshot. "Now" for the platform is the end of the
# extract, so "this month" = Sep 2026, "last quarter" = Q3 2026, "next week" = the
# week starting 2026-10-01. A ServiceNow extract carries its own dates in
# source_manifest.json, which override these.
DATA_START = date(2025, 4, 1)
SNAPSHOT_DATE = date(2026, 9, 30)
SOURCE = "synthetic"


def use_data_dir(path, db_path=None) -> None:
    """Point the platform at a data directory (synthetic `data/` or a ServiceNow extract)."""
    import json

    global DATA_DIR, RAW_DIR, TRUTH_DIR, DB_PATH, CMDB_PATH, DATA_START, SNAPSHOT_DATE, SOURCE
    DATA_DIR = Path(path)
    RAW_DIR = DATA_DIR / "raw"            # what the "enterprise systems" export
    TRUTH_DIR = DATA_DIR / "truth"        # clean generator output, used ONLY by evaluation
    DB_PATH = Path(db_path or os.environ.get("OPSINTEL_DB", DATA_DIR / "opsintel.db"))
    CMDB_PATH = RAW_DIR / "cmdb.sqlite"
    manifest = DATA_DIR / "source_manifest.json"
    if manifest.exists():
        m = json.loads(manifest.read_text())
        SOURCE = m.get("source", "external")
        if m.get("data_start") and m.get("snapshot_date"):
            DATA_START, SNAPSHOT_DATE = date.fromisoformat(m["data_start"]), date.fromisoformat(m["snapshot_date"])


use_data_dir(DATA_DIR)

# Optional REST source for monitoring alerts. When unset, the ETL calls the bundled
# mock monitoring API in-process (same HTTP contract, no network needed).
MONITORING_API_URL = os.environ.get("OPSINTEL_MONITORING_URL")

# LLM
LLM_MODEL = os.environ.get("OPSINTEL_MODEL", "claude-opus-5-5")
LLM_EFFORT = os.environ.get("OPSINTEL_EFFORT", "medium")
LLM_MAX_TOOL_ROUNDS = int(os.environ.get("OPSINTEL_MAX_TOOL_ROUNDS", "8"))

# Optional outbound webhook for approved-action notifications (e.g. Teams/Slack
# incoming webhook). When unset, notifications go to the outbox table only.
NOTIFY_WEBHOOK_URL = os.environ.get("OPSINTEL_WEBHOOK_URL")

SQL_ROW_LIMIT = 200
