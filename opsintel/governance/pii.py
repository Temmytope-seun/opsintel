"""Output-side PII masking (defence in depth behind column-level SQL denial)."""
from __future__ import annotations

import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
UK_PHONE = re.compile(r"(?:\+44\s?|0)7\d{3}\s?\d{6}|\+44\s?\d{4}\s?\d{6}")


def mask_text(text: str) -> str:
    text = EMAIL.sub("[email redacted]", text)
    return UK_PHONE.sub("[phone redacted]", text)


def mask(obj):
    if isinstance(obj, str):
        return mask_text(obj)
    if isinstance(obj, dict):
        return {k: mask(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [mask(v) for v in obj]
    return obj
