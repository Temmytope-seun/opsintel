"""Source connectors. Each returns (DataFrame, provenance dict)."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import httpx
import pandas as pd

from opsintel import config


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> tuple[pd.DataFrame, dict]:
    # Everything as string: typing is the pipeline's job, so bad values are visible.
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return df, {"source_type": "csv", "source_uri": str(path.relative_to(config.ROOT)) if path.is_relative_to(config.ROOT) else str(path),
                "source_sha256": _sha256(path)}


def read_sql_table(db_path: Path, table: str) -> tuple[pd.DataFrame, dict]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        df = pd.read_sql_query(f'SELECT * FROM "{table}"', con)
    uri = db_path.relative_to(config.ROOT) if db_path.is_relative_to(config.ROOT) else db_path
    return df, {"source_type": "rdbms", "source_uri": f"sqlite:///{uri}#{table}", "source_sha256": None}


def _client() -> httpx.Client:
    if config.MONITORING_API_URL:
        return httpx.Client(base_url=config.MONITORING_API_URL, timeout=30)
    # No external endpoint configured: call the bundled mock API in-process over the
    # same HTTP contract (Starlette TestClient is an httpx.Client).
    from fastapi.testclient import TestClient

    from opsintel.sources.mock_monitoring import app

    return TestClient(app)


def read_rest_paginated(path: str = "/v1/alerts", page_size: int = 1000, max_pages: int = 10_000) -> tuple[pd.DataFrame, dict]:
    items, page, pages = [], 1, 0
    with _client() as client:
        while page and pages < max_pages:
            resp = client.get(path, params={"page": page, "page_size": page_size})
            resp.raise_for_status()
            body = resp.json()
            items.extend(body["items"])
            page = body["next_page"]
            pages += 1
        base = str(client.base_url)
    payload = pd.DataFrame(items)
    digest = hashlib.sha256(payload.to_json().encode()).hexdigest()
    return payload, {"source_type": "rest_api", "source_uri": f"{base.rstrip('/')}{path} ({pages} pages)", "source_sha256": digest}
