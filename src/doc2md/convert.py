"""Core conversion logic: PDF -> Markdown (PyMuPDF4LLM), Office -> Markdown (MarkItDown)."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field

from . import detect
from .cache import cache


class ConversionError(RuntimeError):
    """Raised for expected, user-explainable conversion failures."""


@dataclass
class PdfResult:
    markdown: str
    page_count: int
    is_scanned: bool
    toc: list = field(default_factory=list)


def parse_pages(pages: str, page_count: int) -> list[int] | None:
    """Parse a 1-based page spec like ``"1,3-5"`` into 0-based indices.

    Returns ``None`` when the spec is empty (meaning: all pages).
    Raises :class:`ConversionError` for invalid specs.
    """
    spec = (pages or "").strip()
    if not spec:
        return None
    selected: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                start, end = int(bounds[0]), int(bounds[1])
            except ValueError:
                raise ConversionError(f"Invalid page range {part!r}; use e.g. '2-5'.")
            if start < 1 or end > page_count or start > end:
                raise ConversionError(
                    f"Page range {part!r} out of bounds (document has {page_count} pages)."
                )
            selected.extend(range(start - 1, end))
        else:
            try:
                num = int(part)
            except ValueError:
                raise ConversionError(f"Invalid page number {part!r}.")
            if num < 1 or num > page_count:
                raise ConversionError(
                    f"Page {num} out of bounds (document has {page_count} pages)."
                )
            selected.append(num - 1)
    if not selected:
        raise ConversionError(f"No valid pages in spec {pages!r}.")
    # de-duplicate, keep order
    seen = set()
    unique = []
    for idx in selected:
        if idx not in seen:
            seen.add(idx)
            unique.append(idx)
    return unique


def open_pdf(data: bytes, password: str = ""):
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ConversionError(f"Cannot open PDF: {exc}")
    if doc.needs_pass:
        if password:
            if not doc.authenticate(password):
                raise ConversionError("PDF password is incorrect.")
        else:
            raise ConversionError(
                "This PDF is password-protected. Pass the password via the "
                "'password' parameter."
            )
    return doc


def _detect_scanned(doc) -> bool:
    """Heuristic: sample up to 10 pages; scanned PDFs have ~no embedded text."""
    sample_pages = min(doc.page_count, 10)
    if sample_pages == 0:
        return False
    step = max(1, doc.page_count // sample_pages)
    checked = 0
    chars = 0
    for i in range(0, doc.page_count, step):
        try:
            chars += len(doc[i].get_text("text").strip())
        except Exception:
            pass
        checked += 1
        if checked >= sample_pages:
            break
    return checked > 0 and (chars / checked) < 10


def pdf_to_markdown(data: bytes, pages: list[int] | None = None, password: str = "") -> PdfResult:
    """Convert PDF bytes to Markdown. Results for full-document conversions
    are cached by content hash so pagination continuation is cheap."""
    cache_key = None
    if pages is None:
        cache_key = cache.content_key(data)
        cached = cache.get(cache_key)
        if cached is not None:
            # cached value stores page_count and is_scanned in a header line
            first, _, rest = cached.partition("\n\x00\n")
            try:
                page_count, is_scanned = first.split("|", 1)
                return PdfResult(rest, int(page_count), is_scanned == "1", [])
            except ValueError:  # pragma: no cover - corrupted cache entry
                pass

    import pymupdf4llm

    doc = open_pdf(data, password)
    try:
        page_count = doc.page_count
        is_scanned = _detect_scanned(doc)
        toc = [list(entry) for entry in (doc.get_toc() or [])]
        if is_scanned:
            raise ConversionError(
                "This PDF appears to be scanned (no embedded text layer). "
                "Use the ocr_document tool to extract its text."
            )
        try:
            # use_ocr=False: keep conversion deterministic; scanned content is
            # handled explicitly by our own ocr_document tool instead.
            try:
                markdown = pymupdf4llm.to_markdown(
                    doc, pages=pages, show_progress=False, use_ocr=False
                )
            except TypeError:
                # very old pymupdf4llm versions don't know use_ocr
                markdown = pymupdf4llm.to_markdown(doc, pages=pages, show_progress=False)
        except Exception as exc:
            raise ConversionError(f"PDF conversion failed: {exc}")
        if not (markdown or "").strip():
            raise ConversionError(
                "Conversion produced no text. The document may be empty or scanned; "
                "try ocr_document."
            )
    finally:
        doc.close()

    if cache_key is not None:
        cache.set(cache_key, f"{page_count}|{'1' if is_scanned else '0'}\n\x00\n{markdown}")
    return PdfResult(markdown, page_count, is_scanned, toc)


def _markitdown_instance():
    from markitdown import MarkItDown

    return MarkItDown(enable_plugins=False)


def document_to_markdown(data: bytes, kind: str, filename: str = "") -> str:
    """Convert DOCX/PPTX/XLSX/HTML/EPUB/TEXT bytes to Markdown via MarkItDown."""
    cache_key = cache.content_key(data)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if kind == detect.LEGACY_OFFICE:
        raise ConversionError(
            "Legacy binary Office formats (.doc/.xls/.ppt) are not supported. "
            "Re-save the file as .docx/.xlsx/.pptx first."
        )
    suffix = detect.suffix_for(kind, filename)
    if suffix == ".bin":
        raise ConversionError(
            f"Unsupported document type {kind!r}. Supported: PDF, DOCX, PPTX, "
            "XLSX, EPUB, HTML, CSV/JSON/XML/TXT, and images (via ocr_document)."
        )

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        try:
            result = _markitdown_instance().convert(tmp_path)
            markdown = (result.text_content or "").strip()
        except Exception as exc:
            raise ConversionError(f"Document conversion failed: {exc}")
        if not markdown:
            raise ConversionError(
                "Conversion produced no text. If this is a scanned document, "
                "use the ocr_document tool."
            )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    cache.set(cache_key, markdown)
    return markdown


def slice_markdown(markdown: str, offset: int, max_chars: int) -> tuple[str, bool, int, int]:
    """Slice converted markdown for paginated delivery.

    Returns ``(chunk, truncated, next_offset, total_chars)``.
    """
    total = len(markdown)
    offset = max(0, min(offset, total))
    end = min(offset + max_chars, total)
    chunk = markdown[offset:end]
    truncated = end < total
    return chunk, truncated, end, total
