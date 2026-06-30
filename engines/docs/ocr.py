"""OCR cascade (MASTER_PLAN J.2) — fall back to the best OCR available.

Reading complex/poor sources is where extraction breaks. So we *escalate*: try the cheap,
fast engine first; if the result looks poor (the quality gate), fall back to a stronger
engine; keep going up the tiers; and if even the best is poor, flag the page for the
human-review queue — never silently trust it.

Tiers (best-in-class open source, ordered by capability/cost):
  tesseract  CPU, printed text, EN+AR        (real, installed)
  rapidocr   CPU/ONNX, layouts, multilingual (real-if-installed)
  paddleocr  strong layouts/tables/Arabic    (adapter)
  surya      layout + reading order          (adapter)
  vlm        olmOCR-2 / PaddleOCR-VL / GOT-OCR2 / DeepSeek-OCR, hardest scans (adapter, GPU)
"""
from __future__ import annotations

import importlib.util
import re
import shutil
from typing import Protocol

_WORD = re.compile(r"[A-Za-z؀-ۿ]{2,}")  # latin or arabic words


def extraction_quality(text: str) -> float:
    """0..1 — is this extraction usable, or empty/garbage? Drives escalation."""
    t = (text or "").strip()
    if not t:
        return 0.0
    words = _WORD.findall(t)
    if not words:
        return 0.0
    alnum_ratio = sum(c.isalnum() or c.isspace() for c in t) / len(t)
    word_ratio = sum(len(w) for w in words) / len(t)
    score = 0.5 * min(1.0, len(words) / 5) + 0.25 * alnum_ratio + 0.25 * word_ratio
    return round(min(1.0, score), 3)


class OcrEngine(Protocol):
    name: str
    def available(self) -> bool: ...
    def ocr(self, image) -> tuple[str, float]: ...


class NullOcrEngine:
    name = "none"
    def available(self) -> bool:
        return True
    def ocr(self, image) -> tuple[str, float]:
        return "", 0.0


class TesseractOcrEngine:
    name = "tesseract"
    def __init__(self, langs: str = "eng+ara"):
        self.langs = langs
    def available(self) -> bool:
        return shutil.which("tesseract") is not None and importlib.util.find_spec("pytesseract") is not None
    def ocr(self, image) -> tuple[str, float]:
        import pytesseract
        try:
            data = pytesseract.image_to_data(image, lang=self.langs, output_type=pytesseract.Output.DICT)
        except pytesseract.TesseractError:
            data = pytesseract.image_to_data(image, lang="eng", output_type=pytesseract.Output.DICT)
        words, confs = [], []
        for txt, conf in zip(data["text"], data["conf"], strict=False):
            if txt.strip():
                words.append(txt)
                try:
                    c = float(conf)
                    if c >= 0:
                        confs.append(c / 100.0)
                except (ValueError, TypeError):
                    pass
        return " ".join(words), (sum(confs) / len(confs) if confs else 0.0)


class RapidOcrEngine:
    name = "rapidocr"
    def __init__(self):
        self._engine = None
    def available(self) -> bool:
        return importlib.util.find_spec("rapidocr_onnxruntime") is not None
    def ocr(self, image) -> tuple[str, float]:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        if self._engine is None:
            self._engine = RapidOCR()
        result, _ = self._engine(np.array(image))
        if not result:
            return "", 0.0
        texts = [r[1] for r in result]
        confs = [float(r[2]) for r in result if len(r) > 2]
        return " ".join(texts), (sum(confs) / len(confs) if confs else 0.0)


class _AdapterEngine:
    """Stronger engines that need heavy infra: available only when installed."""
    name = "adapter"
    module = ""
    install = "not wired"
    def available(self) -> bool:
        return importlib.util.find_spec(self.module) is not None if self.module else False
    def ocr(self, image) -> tuple[str, float]:
        raise NotImplementedError(self.install)


class PaddleOcrEngine(_AdapterEngine):
    name = "paddleocr"
    module = "paddleocr"
    install = "pip install paddleocr paddlepaddle (strong layouts/tables/Arabic)"


class SuryaOcrEngine(_AdapterEngine):
    name = "surya"
    module = "surya"
    install = "pip install surya-ocr (layout + reading order, multilingual)"


class VlmOcrEngine(_AdapterEngine):
    name = "vlm"
    module = ""  # needs a specific model server
    install = "wire a VLM-OCR (olmOCR-2 / PaddleOCR-VL / GOT-OCR2 / DeepSeek-OCR) on GPU"


_ENGINES = {
    "none": NullOcrEngine,
    "tesseract": TesseractOcrEngine,
    "rapidocr": RapidOcrEngine,
    "paddleocr": PaddleOcrEngine,
    "surya": SuryaOcrEngine,
    "vlm": VlmOcrEngine,
}


def get_ocr_engine(name: str) -> OcrEngine:
    return _ENGINES[name]()


def render_pdf_page(path: str, page_no: int, dpi: int = 200):
    """Rasterize a PDF page to a PIL image (PyMuPDF) so OCR can read scanned pages."""
    import fitz
    from PIL import Image
    doc = fitz.open(path)
    pix = doc[page_no - 1].get_pixmap(dpi=dpi)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def ocr_cascade(image, engine_names: list[str], quality_threshold: float = 0.5) -> dict:
    """Try engines in order; stop at the first good result; keep the best; flag if all poor."""
    tried: list[str] = []
    best = {"text": "", "confidence": 0.0, "quality": 0.0, "engine": None}
    for name in engine_names:
        engine = get_ocr_engine(name)
        if not engine.available():
            tried.append(f"{name}:unavailable")
            continue
        try:
            text, conf = engine.ocr(image)
        except NotImplementedError:
            tried.append(f"{name}:not_wired")
            continue
        q = extraction_quality(text)
        tried.append(f"{name}:q={q:.2f},conf={conf:.2f}")
        if q > best["quality"]:
            best = {"text": text, "confidence": conf, "quality": q, "engine": name}
        if q >= quality_threshold and conf >= 0.5:
            break
    needs_review = best["quality"] < quality_threshold or best["confidence"] < 0.5
    return {**best, "needs_review": needs_review, "tried": tried}


def extract_page_text(
    born_text: str, image_loader, cascade: list[str], quality_threshold: float = 0.5
) -> dict:
    """Born-digital text if it's good; otherwise escalate to the OCR cascade (lazy render)."""
    if extraction_quality(born_text) >= quality_threshold:
        return {"text": born_text, "was_ocr": False, "confidence": None,
                "needs_review": False, "engine": None, "warning": None, "tried": []}
    if not cascade or image_loader is None:
        return {"text": born_text, "was_ocr": False, "confidence": None,
                "needs_review": True, "engine": None,
                "warning": "poor text and no OCR cascade configured -> human review", "tried": []}
    r = ocr_cascade(image_loader(), cascade, quality_threshold)
    warning = (
        f"OCR low quality (best={r['engine']} q={r['quality']:.2f}) -> human review"
        if r["needs_review"] else None
    )
    return {"text": r["text"], "was_ocr": True, "confidence": r["confidence"],
            "needs_review": r["needs_review"], "engine": r["engine"],
            "warning": warning, "tried": r["tried"]}
