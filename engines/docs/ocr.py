"""OCR cascade (MASTER_PLAN J.2) with repo-owned backend seams."""

from __future__ import annotations

import importlib.util
import re
import shutil
from typing import Protocol

from engines.docs.rapidocr_adapter import RapidOcrAdapter

_WORD = re.compile(r"[A-Za-z\u0600-\u06FF]{2,}")
_HANGUL = re.compile(r"[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]")


def extraction_quality(text: str) -> float:
    """0..1 quality score for OCR output."""
    cleaned = (text or "").strip()
    if not cleaned:
        return 0.0
    words = _WORD.findall(cleaned)
    if not words:
        return 0.0
    alnum_ratio = sum(char.isalnum() or char.isspace() for char in cleaned) / len(cleaned)
    word_ratio = sum(len(word) for word in words) / len(cleaned)
    score = 0.5 * min(1.0, len(words) / 5) + 0.25 * alnum_ratio + 0.25 * word_ratio
    return round(min(1.0, score), 3)


def detect_ocr_language_hint(text: str, default_langs: str = "eng+ara") -> str:
    if _HANGUL.search(text or ""):
        return "kor+eng"
    return default_langs


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
        return (
            shutil.which("tesseract") is not None
            and importlib.util.find_spec("pytesseract") is not None
        )

    def ocr(self, image) -> tuple[str, float]:
        import pytesseract

        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.langs,
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractError:
            data = pytesseract.image_to_data(
                image,
                lang="eng",
                output_type=pytesseract.Output.DICT,
            )
        words: list[str] = []
        confs: list[float] = []
        for text, conf in zip(data["text"], data["conf"], strict=False):
            if text.strip():
                words.append(text)
                try:
                    numeric_conf = float(conf)
                except (ValueError, TypeError):
                    continue
                if numeric_conf >= 0:
                    confs.append(numeric_conf / 100.0)
        return " ".join(words), (sum(confs) / len(confs) if confs else 0.0)


class RapidOcrEngine:
    name = "rapidocr"

    def __init__(self):
        self._adapter = RapidOcrAdapter()

    def available(self) -> bool:
        return self._adapter.available()

    def ocr(self, image) -> tuple[str, float]:
        result = self._adapter.ocr(image)
        return result.text, result.confidence


class _AdapterEngine:
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
    module = ""
    install = "wire a VLM OCR server on GPU"


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
    """Rasterize a PDF page to a PIL image so OCR can read scanned pages."""
    import fitz
    from PIL import Image

    document = fitz.open(path)
    pix = document[page_no - 1].get_pixmap(dpi=dpi)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def ocr_cascade(
    image,
    engine_names: list[str],
    quality_threshold: float = 0.5,
    lang_hint: str | None = None,
) -> dict:
    """Try engines in order, keep the best result, and flag low-confidence OCR."""
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
        quality = extraction_quality(text)
        tried.append(f"{name}:q={quality:.2f},conf={conf:.2f}")
        if quality > best["quality"]:
            best = {"text": text, "confidence": conf, "quality": quality, "engine": name}
        if quality >= quality_threshold and conf >= 0.5:
            break
    needs_review = best["quality"] < quality_threshold or best["confidence"] < 0.5
    return {**best, "needs_review": needs_review, "tried": tried, "lang_hint": lang_hint}


def extract_page_text(
    born_text: str,
    image_loader,
    cascade: list[str],
    quality_threshold: float = 0.5,
    *,
    ocr_langs: str = "eng+ara",
) -> dict:
    """Use born-digital text if good, else escalate to the OCR cascade."""
    if extraction_quality(born_text) >= quality_threshold:
        return {
            "text": born_text,
            "was_ocr": False,
            "confidence": None,
            "needs_review": False,
            "engine": None,
            "warning": None,
            "tried": [],
        }
    if not cascade or image_loader is None:
        return {
            "text": born_text,
            "was_ocr": False,
            "confidence": None,
            "needs_review": True,
            "engine": None,
            "warning": "poor text and no OCR cascade configured -> human review",
            "tried": [],
        }

    lang_hint = detect_ocr_language_hint(born_text, default_langs=ocr_langs)
    result = ocr_cascade(image_loader(), cascade, quality_threshold, lang_hint=lang_hint)
    warning = None
    if lang_hint.startswith("kor") and result["engine"] is None:
        warning = "Korean OCR unavailable -> human review"
    elif result["needs_review"]:
        warning = f"OCR low quality (best={result['engine']} q={result['quality']:.2f}) -> human review"
    return {
        "text": result["text"],
        "was_ocr": True,
        "confidence": result["confidence"],
        "needs_review": result["needs_review"],
        "engine": result["engine"],
        "warning": warning,
        "tried": result["tried"],
    }
