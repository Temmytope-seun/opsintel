"""Document retrieval over runbooks, policies and problem records.

TF-IDF + cosine similarity: deterministic, no external service, good enough for a
corpus of procedures with distinctive vocabulary. The interface (search -> chunks with
ids, scores, classification) is what a pgvector/embedding retriever would also return.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from opsintel import config
from opsintel.ai.injection import PLACEHOLDER, is_suspicious


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    classification: str
    owner: str
    reviewed: str
    text: str
    path: str


def _parse(path: Path) -> list[Chunk]:
    raw = path.read_text()
    meta, body = {}, raw
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    parts = re.split(r"\n(?=## )", body)
    if len(parts) > 1 and len(parts[0]) < 300:   # fold a title-only preamble into the first section
        parts = [parts[0] + "\n" + parts[1]] + parts[2:]
    chunks = []
    for i, part in enumerate(parts):
        heading = part.strip().splitlines()[0].lstrip("# ").strip() if part.strip() else ""
        text = part.strip()
        if not text:
            continue
        chunks.append(Chunk(f"{meta.get('id', path.stem)}#{i}", meta.get("id", path.stem), meta.get("title", path.stem),
                            heading, meta.get("classification", "internal"), meta.get("owner", ""),
                            meta.get("reviewed", ""), text, path.name))
    return chunks


_SUFFIX = re.compile(r"(ing|ed|es|s)$")


def _tokens(text: str) -> list[str]:
    """Lowercase word tokens with light suffix stripping (reboots/rebooting -> reboot)."""
    out = []
    for t in re.findall(r"[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z0-9]", text.lower()):
        if t not in ENGLISH_STOP_WORDS:
            out.append(_SUFFIX.sub("", t) if len(t) > 4 else t)
    return out


class KnowledgeIndex:
    def __init__(self, directory: Path):
        self.chunks: list[Chunk] = [c for p in sorted(directory.glob("*.md")) for c in _parse(p)]
        # Index the screened text: injected paragraphs must not attract retrieval either.
        corpus = [f"{c.title} {c.section} " + " ".join(x for x in c.text.split("\n\n") if not is_suspicious(x)) for c in self.chunks]
        self.vec = TfidfVectorizer(tokenizer=_tokens, token_pattern=None, lowercase=False,
                                   ngram_range=(1, 2), sublinear_tf=True, min_df=1)
        self.matrix = self.vec.fit_transform(corpus)

    def search(self, query: str, allowed_levels: set[str], k: int = 4, min_score: float = 0.05, max_per_doc: int = 2) -> dict:
        q = self.vec.transform([query])
        scores = (self.matrix @ q.T).toarray().ravel()
        order = np.argsort(-scores)
        results, withheld, injection, per_doc = [], 0, [], {}
        for i in order:
            if scores[i] < min_score or len(results) >= k:
                break
            c = self.chunks[i]
            if c.classification not in allowed_levels:
                withheld += 1
                continue
            if per_doc.get(c.doc_id, 0) >= max_per_doc:
                continue
            per_doc[c.doc_id] = per_doc.get(c.doc_id, 0) + 1
            # Screen paragraph by paragraph so legitimate content in the same chunk survives.
            paras = c.text.split("\n\n")
            flagged = any(is_suspicious(x) for x in paras)
            text = "\n\n".join(PLACEHOLDER if is_suspicious(x) else x for x in paras)
            if flagged:
                injection.append(c.chunk_id)
            results.append({"chunk_id": c.chunk_id, "doc_id": c.doc_id, "title": c.title, "section": c.section,
                            "classification": c.classification, "owner": c.owner, "reviewed": c.reviewed,
                            "score": round(float(scores[i]), 3), "text": text, "injection_flagged": flagged})
        return {"query": query, "results": results, "withheld_by_access_control": withheld,
                "injection_flagged_chunks": injection,
                "summary": (f"{len(results)} relevant passages: " + ", ".join(sorted({r['doc_id'] for r in results})))
                if results else "No sufficiently relevant documents found."}


@lru_cache(maxsize=1)
def index() -> KnowledgeIndex:
    return KnowledgeIndex(config.KNOWLEDGE_DIR)
