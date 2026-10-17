"""Numeric grounding check: every figure in an answer must be a rounding of a number
that appears in the evidence the tools returned. Ungrounded figures are flagged in the
UI and counted in evaluation (they are the hallucination signal for numbers)."""
from __future__ import annotations

import math
import re

NUM = re.compile(r"(?<![\w.])(£|\$)?(-|\+|−)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?(?:(k|m|bn)\b)?(%| ?pp\b| ?percentage points)?(?![\w.-]*\d)", re.I)
MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
SKIP_CONTEXT = re.compile(r"(?:\b[EPQ]|SVC-|INC|RITM|CI-|CUS-|ACT-|v|fw |firmware |version )$", re.I)


def _evidence_numbers(obj, out: set):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        if not (isinstance(obj, float) and math.isnan(obj)):
            out.add(float(obj))
        return
    if isinstance(obj, str):
        for m in re.finditer(r"-?\d[\d,]*\.?\d*", obj):
            try:
                out.add(float(m.group().replace(",", "").rstrip(".")))
            except ValueError:
                pass
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _evidence_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _evidence_numbers(v, out)


def extract_figures(text: str) -> list[dict]:
    figs = []
    for m in NUM.finditer(text):
        cur, sign, whole, frac, mult, unit = m.groups()
        start = m.start()
        prefix = text[max(0, start - 10):start]
        if SKIP_CONTEXT.search(prefix):
            continue
        value = float(whole.replace(",", "") + (frac or ""))
        if 1990 <= value <= 2100 and not (cur or unit or frac):
            continue  # a year
        if re.match(r"[-/]\d", text[m.end():m.end() + 2]) or re.search(r"\d[-/]$", prefix):
            continue  # part of a date / range token like 2026-09
        if value <= 31 and not (cur or unit or frac or mult) and (
                re.match(rf"\s*{MONTH}\b", text[m.end():m.end() + 12], re.I) or re.search(rf"\b{MONTH}\s+$", prefix, re.I)):
            continue  # day of month, e.g. "30 September" / "June 30"
        if value <= 12 and not (cur or unit or frac or mult):
            continue  # list numbering, "top 3", step numbers
        decimals = len(frac) - 1 if frac else 0
        scale = {"k": 1e3, "m": 1e6, "bn": 1e9}.get((mult or "").lower(), 1)
        if sign in ("-", "−"):
            value = -value
        figs.append({"text": m.group().strip(), "value": value * scale, "tolerance": 0.5 * 10 ** (-decimals) * scale,
                     "is_percent": bool(unit and "%" in unit), "signed": bool(sign)})
    return figs


def check(answer: str, evidence_results: list[dict]) -> dict:
    nums: set[float] = set()
    for r in evidence_results:
        _evidence_numbers(r, nums)
    pool = nums | {n * 100 for n in nums if abs(n) <= 1}  # ratios shown as percentages
    grounded, ungrounded = [], []
    for f in extract_figures(answer):
        tol = f["tolerance"] + 1e-9
        cands = pool | {n * 100 for n in nums} if f["is_percent"] else pool   # 2.32 -> "232%"
        ok = any(abs(abs(f["value"]) - abs(n)) <= tol for n in cands)
        (grounded if ok else ungrounded).append(f["text"])
    total = len(grounded) + len(ungrounded)
    return {"figures": total, "grounded": grounded, "ungrounded": ungrounded,
            "grounding_rate": round(len(grounded) / total, 3) if total else 1.0}
