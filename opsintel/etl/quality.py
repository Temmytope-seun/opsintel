"""Data-quality profiling and entity matching."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

import pandas as pd

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$")


@dataclass
class Rules:
    key: list[str]
    required: list[str] = field(default_factory=list)
    iso_dates: list[str] = field(default_factory=list)
    enums: dict[str, set] = field(default_factory=dict)
    refs: dict[str, set] = field(default_factory=dict)   # column -> set of valid values
    numeric: list[str] = field(default_factory=list)
    patterns: dict[str, str] = field(default_factory=dict)  # column -> regex


def profile(df: pd.DataFrame, rules: Rules) -> dict[str, float]:
    """Return comparable quality metrics. Works on raw (string) and clean frames."""
    n = len(df)
    out = {"rows": n}
    if n == 0:
        return out
    req = [c for c in rules.required if c in df.columns]
    missing = sum(int((df[c].isna() | (df[c].astype(str).str.strip() == "")).sum()) for c in req)
    out["missing_required_cells"] = missing
    out["missing_required_pct"] = round(100 * missing / max(1, n * len(req)), 3)
    out["exact_duplicate_rows"] = int(df.duplicated().sum())
    keys = [k for k in rules.key if k in df.columns]
    out["duplicate_keys"] = int(df.duplicated(subset=keys).sum()) if keys else 0
    violations = 0
    for c in rules.iso_dates:
        if c in df.columns:
            s = df[c].dropna().astype(str)
            s = s[s.str.strip() != ""]
            violations += int((~s.str.match(ISO_RE)).sum())
    for c, pat in rules.patterns.items():
        if c in df.columns:
            violations += int((~df[c].astype(str).str.fullmatch(pat)).sum())
    for c, allowed in rules.enums.items():
        if c in df.columns:
            s = df[c].dropna().astype(str)
            violations += int((~s.isin(allowed) & (s != "")).sum())
    for c in rules.numeric:
        if c in df.columns:
            violations += int(pd.to_numeric(df[c], errors="coerce").isna().sum() - df[c].isna().sum())
    out["schema_violations"] = violations
    unmatched = 0
    for c, valid in rules.refs.items():
        if c in df.columns:
            s = df[c].dropna().astype(str)
            unmatched += int((~s.isin(valid) & (s != "")).sum())
    out["unmatched_references"] = unmatched
    return out


def parse_datetime(series: pd.Series) -> pd.Series:
    """Accept ISO-8601 and the UK dd/mm/yyyy format a legacy report produces."""
    s = series.astype(str).str.strip().replace({"": None, "NaT": None, "nan": None})
    iso = pd.to_datetime(s, format="ISO8601", errors="coerce")
    uk = pd.to_datetime(s, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    return iso.fillna(uk)


def _norm(s: str) -> str:
    s = s.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", s)


class EntityMatcher:
    """Resolve free-text names to canonical ids using exact, normalised, alias and fuzzy matching."""

    def __init__(self, canonical: dict[str, str], aliases: dict[str, list[str]] | None = None, cutoff: float = 0.88):
        self.lookup: dict[str, str] = {}
        for cid, name in canonical.items():
            self.lookup[_norm(name)] = cid
            self.lookup[_norm(cid)] = cid
        for cid, names in (aliases or {}).items():
            for a in names:
                self.lookup.setdefault(_norm(a), cid)
        self.cutoff = cutoff
        self.stats = {"exact_or_normalised": 0, "fuzzy": 0, "unmatched": 0}

    def match(self, raw: str) -> str | None:
        key = _norm(raw or "")
        if not key:
            self.stats["unmatched"] += 1
            return None
        if key in self.lookup:
            self.stats["exact_or_normalised"] += 1
            return self.lookup[key]
        close = difflib.get_close_matches(key, self.lookup.keys(), n=1, cutoff=self.cutoff)
        if close:
            self.stats["fuzzy"] += 1
            return self.lookup[close[0]]
        self.stats["unmatched"] += 1
        return None
