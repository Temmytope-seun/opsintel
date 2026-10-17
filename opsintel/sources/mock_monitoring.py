"""Mock monitoring platform REST API (stands in for e.g. a PRTG / Zabbix / LogicMonitor feed).

Paginated, at-least-once delivery semantics: the backing data deliberately contains
duplicate events and inconsistent severity casing, as real feeds do.
Run standalone:  uvicorn opsintel.sources.mock_monitoring:app --port 8099
"""
from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI, Query

from opsintel import config

app = FastAPI(title="Mock Monitoring API", version="1.0")


@lru_cache(maxsize=1)
def _events() -> list[dict]:
    return json.loads((config.RAW_DIR / "monitoring_alerts.json").read_text())


@app.get("/v1/alerts")
def list_alerts(page: int = Query(1, ge=1), page_size: int = Query(1000, ge=1, le=5000)):
    events = _events()
    start = (page - 1) * page_size
    items = events[start:start + page_size]
    total_pages = max(1, -(-len(events) // page_size))
    return {"page": page, "page_size": page_size, "total_pages": total_pages,
            "next_page": page + 1 if page < total_pages else None, "items": items}
