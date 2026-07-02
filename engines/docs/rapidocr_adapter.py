"""Thin repo-owned wrapper around RapidOCR."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field


@dataclass
class RapidOcrResult:
    text: str
    confidence: float
    lines: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class RapidOcrAdapter:
    """Normalize RapidOCR output into a stable local shape."""

    def __init__(self):
        self._engine = None

    def available(self) -> bool:
        return importlib.util.find_spec("rapidocr_onnxruntime") is not None

    def _get_engine(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def ocr(self, image, *, lang_hint: str | None = None) -> RapidOcrResult:
        import numpy as np

        result, elapsed = self._get_engine()(np.array(image))
        if not result:
            return RapidOcrResult(
                text="",
                confidence=0.0,
                lines=[],
                metadata={"lang_hint": lang_hint, "elapsed_ms": elapsed, "result_count": 0},
            )

        lines = [str(item[1]).strip() for item in result if len(item) > 1 and str(item[1]).strip()]
        confs = [float(item[2]) for item in result if len(item) > 2]
        confidence = sum(confs) / len(confs) if confs else 0.0
        return RapidOcrResult(
            text=" ".join(lines),
            confidence=confidence,
            lines=lines,
            metadata={
                "lang_hint": lang_hint,
                "elapsed_ms": elapsed,
                "result_count": len(result),
            },
        )
