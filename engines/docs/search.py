"""Document search (MASTER_PLAN Part D `search_documents`).

Returns passages with an EvidenceRef (file + page) so a manager card can CITE a document.
Simple keyword scoring today; a hybrid (BM25 + dense + rerank) upgrade plugs in later
(MASTER_PLAN Part S). Documents are evidence — citations, not numbers.
"""
from __future__ import annotations

from dataclasses import dataclass

from engines.docs.models import Document
from shared.contracts.models import EvidenceRef


@dataclass
class Passage:
    text: str
    score: int
    evidence: EvidenceRef
    needs_review: bool


def _snippet(text: str, terms: list[str], width: int = 160) -> str:
    low = text.lower()
    pos = next((low.find(t) for t in terms if low.find(t) >= 0), 0)
    start = max(0, pos - width // 2)
    return " ".join(text[start : start + width].split())


def search_documents(docs: list[Document], query: str, top_k: int = 3) -> list[Passage]:
    terms = [t for t in query.lower().split() if t]
    hits: list[Passage] = []
    for doc in docs:
        for page in doc.pages:
            low = page.text.lower()
            score = sum(low.count(t) for t in terms)
            if score == 0:
                continue
            hits.append(
                Passage(
                    text=_snippet(page.text, terms),
                    score=score,
                    evidence=EvidenceRef(
                        source=doc.source_filename,
                        locator=f"page {page.page_no}",
                        method="keyword document search",
                    ),
                    needs_review=page.needs_review,
                )
            )
    hits.sort(key=lambda p: p.score, reverse=True)
    return hits[:top_k]
