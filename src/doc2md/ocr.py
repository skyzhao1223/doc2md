"""OCR for scanned PDFs and images, backed by RapidOCR (ONNX Runtime).

RapidOCR is an *optional* dependency (extra ``ocr``). It is imported lazily
so the server still starts — and all non-OCR tools still work — when OCR is
not installed.
"""

from __future__ import annotations

import asyncio

from .convert import ConversionError, open_pdf, parse_pages
from .detect import IMAGE, PDF

_MAX_OCR_PAGES = 30
_RENDER_DPI = 200
_SEMAPHORE = asyncio.Semaphore(2)  # limit concurrent OCR on shared hosts

_engine = None


def ocr_available() -> bool:
    try:
        _get_engine()
        return True
    except ConversionError:
        return False


def _get_engine():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise ConversionError(
                "OCR support is not installed on this server. Install with "
                "pip install 'doc2md[ocr]' (or use the official Docker image, "
                "which includes OCR)."
            ) from exc
        _engine = RapidOCR()
    return _engine


def _run_ocr_on_bytes(engine, image_bytes: bytes) -> str:
    result, _elapse = engine(image_bytes)
    if not result:
        return ""
    lines = []
    for item in result:
        # item = [box, text, score]
        try:
            text = item[1]
        except (IndexError, TypeError):
            continue
        text = str(text).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _pdf_page_images(data: bytes, pages: str, password: str) -> list[tuple[int, bytes]]:
    doc = open_pdf(data, password)
    try:
        page_indices = parse_pages(pages, doc.page_count)
        if page_indices is None:
            page_indices = list(range(doc.page_count))
        if len(page_indices) > _MAX_OCR_PAGES:
            raise ConversionError(
                f"OCR is limited to {_MAX_OCR_PAGES} pages per call; you requested "
                f"{len(page_indices)}. Narrow the 'pages' parameter (e.g. '1-30')."
            )
        rendered: list[tuple[int, bytes]] = []
        for pno in page_indices:
            pix = doc[pno].get_pixmap(dpi=_RENDER_DPI)
            rendered.append((pno + 1, pix.tobytes("png")))
        return rendered
    finally:
        doc.close()


async def ocr_document(data: bytes, kind: str, pages: str = "", password: str = "") -> dict:
    """OCR a scanned PDF or an image; returns per-page plain text."""
    if kind not in (PDF, IMAGE):
        raise ConversionError(
            f"ocr_document accepts PDFs and images, got {kind!r}. For DOCX/PPTX/"
            "XLSX/HTML use convert_document_to_markdown instead."
        )

    async with _SEMAPHORE:
        engine = await asyncio.to_thread(_get_engine)
        if kind == IMAGE:
            text = await asyncio.to_thread(_run_ocr_on_bytes, engine, data)
            page_texts = [{"page": 1, "text": text}]
        else:
            rendered = await asyncio.to_thread(_pdf_page_images, data, pages, password)
            page_texts = []
            for pno, png in rendered:
                text = await asyncio.to_thread(_run_ocr_on_bytes, engine, png)
                page_texts.append({"page": pno, "text": text})

    full_text = "\n\n".join(
        f"## Page {p['page']}\n\n{p['text']}" for p in page_texts if p["text"].strip()
    )
    if not full_text.strip():
        return {
            "page_count": len(page_texts),
            "text": "",
            "pages": page_texts,
            "note": "No text was detected. The document may be blank or the image quality too low.",
        }
    return {"page_count": len(page_texts), "text": full_text, "pages": page_texts}
