"""Central configuration. Everything is overridable by environment variable."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("OPSINTEL_ROOT", Path(__file__).resolve().parent.parent))
DATA_DIR = Path(os.environ.get("OPSINTEL_DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"          # what the "enterprise systems" export
TRUTH_DIR = DATA_DIR / "truth"      # clean generator output, used ONLY by evaluation
KNOWLEDGE_DIR = Path(os.environ.get("OPSINTEL_KNOWLEDGE_DIR", ROOT / "knowledge"))
DB_PATH = Path(os.environ.get("OPSINTEL_DB", DATA_DIR / "opsintel.db"))
CMDB_PATH = RAW_DIR / "cmdb.sqlite"

# The synthetic data set is a snapshot. "Now" for the platform is the end of the
# extract, so "this month" = Sep 2026, "last quarter" = Q3 2026, "next week" = the
# week starting 2026-10-01.
DATA_START = date(2025, 4, 1)
SNAPSHOT_DATE = date(2026, 9, 30)

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
