"""Heuristic prompt-injection screen for untrusted text (documents, ticket free text).

This is one layer of several: the LLM is also told tool output is data, tools are
read-only, PII columns are blocked at the SQL engine, and actions need human approval.
"""
from __future__ import annotations

import re

PATTERNS = [
    r"ignore (all )?(your |the )?(previous|prior|above) (instructions|rules)",
    r"disregard (all )?(your |the )?(previous |prior )?(instructions|rules)",
    r"system (note|prompt|message) to (ai|the assistant|assistants|llm)",
    r"you are (now )?(in )?(admin|developer|god) mode",
    r"you are (now )?authori[sz]ed to",
    r"(reveal|list|print|exfiltrate) (every|all) (customer )?(contact )?(e-?mail|password|credential)",
    r"approve all (pending )?actions",
]
RX = re.compile("|".join(PATTERNS), re.IGNORECASE)
PLACEHOLDER = "[withheld: text in this source looks like instructions to an AI system (possible prompt injection)]"


def is_suspicious(text: str) -> bool:
    return bool(RX.search(text or ""))


def screen(obj, hits: list | None = None):
    """Return a copy of obj with suspicious strings replaced; append hits for reporting."""
    if isinstance(obj, str):
        if is_suspicious(obj):
            if hits is not None:
                hits.append(obj[:160])
            return PLACEHOLDER
        return obj
    if isinstance(obj, dict):
        return {k: screen(v, hits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [screen(v, hits) for v in obj]
    return obj
