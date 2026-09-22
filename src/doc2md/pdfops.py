"""PDF operations: split, merge, and embedded-image extraction."""

from __future__ import annotations

import base64

from .convert import ConversionError, open_pdf, parse_pages

MAX_PARTS = 20
MAX_PART_BYTES = 5 * 1024 * 1024
MAX_MERGE_INPUTS = 10
MAX_MERGED_BYTES = 10 * 1024 * 1024
MAX_IMAGES = 50
MAX_IMAGE_B64_BYTES = 2 * 1024 * 1024


def parse_ranges(spec: str, page_count: int) -> list[tuple[int, int]]:
    """Parse '1-3,5,8-10' into inclusive 1-based (start, end) tuples."""
    spec = (spec or "").strip()
    if not spec:
        raise ConversionError("'ranges' is required, e.g. '1-3,5,8-10'.")
    ranges: list[tuple[int, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                start, end = int(bounds[0]), int(bounds[1])
            except ValueError:
                raise ConversionError(f"Invalid range {part!r}; use e.g. '2-5'.")
        else:
            try:
                start = end = int(part)
            except ValueError:
                raise ConversionError(f"Invalid page number {part!r}.")
        if start < 1 or end > page_count or start > end:
            raise ConversionError(
                f"Range {part!r} out of bounds (document has {page_count} pages)."
            )
        ranges.append((start, end))
    if not ranges:
        raise ConversionError(f"No valid ranges in {spec!r}.")
    if len(ranges) > MAX_PARTS:
        raise ConversionError(f"Too many parts: {len(ranges)} (max {MAX_PARTS}).")
    return ranges


def _insert_range(out, src, start0: int, end0: int) -> None:
    """Copy a 0-based inclusive page range; supports old and new PyMuPDF APIs."""
    try:
        out.insert_pdf(src, from_page=start0, to_page=end0)
    except TypeError:
        out.insert_pdf(src, from_=start0, to=end0)


def split_pdf(data: bytes, ranges_spec: str, password: str = "") -> dict:
    """Split a PDF into parts; each part ≤5 MB is returned as base64."""
    import pymupdf

    src = open_pdf(data, password)
    try:
        ranges = parse_ranges(ranges_spec, src.page_count)
        parts: list[dict] = []
        for start, end in ranges:
            out = pymupdf.open()
            try:
                _insert_range(out, src, start - 1, end - 1)
                blob = out.tobytes()
            finally:
                out.close()
            part: dict = {
                "range": f"{start}-{end}" if start != end else str(start),
                "page_count": end - start + 1,
                "size_bytes": len(blob),
            }
            if len(blob) <= MAX_PART_BYTES:
                part["file_base64"] = base64.b64encode(blob).decode()
            else:
                part["file_base64"] = None
                part["note"] = (
                    f"Part exceeds the {MAX_PART_BYTES // (1024 * 1024)} MB response "
                    "limit; use a narrower range."
                )
            parts.append(part)
        return {
            "page_count": src.page_count,
            "part_count": len(parts),
            "parts": parts,
        }
    finally:
        src.close()


def merge_pdfs(documents: list[bytes]) -> dict:
    """Merge PDF byte strings (in order) into a single PDF."""
    import pymupdf

    if len(documents) < 2:
        raise ConversionError("Provide at least 2 PDFs to merge.")
    if len(documents) > MAX_MERGE_INPUTS:
        raise ConversionError(
            f"Too many inputs: {len(documents)} (max {MAX_MERGE_INPUTS})."
        )
    out = pymupdf.open()
    sources: list[dict] = []
    try:
        for i, data in enumerate(documents):
            if not data.startswith(b"%PDF"):
                raise ConversionError(f"Input #{i + 1} is not a PDF.")
            doc = open_pdf(data)
            try:
                if doc.needs_pass:
                    raise ConversionError(
                        f"Input #{i + 1} is password-protected; merge only accepts "
                        "unencrypted PDFs."
                    )
                out.insert_pdf(doc)
                sources.append({"index": i + 1, "page_count": doc.page_count})
            finally:
                doc.close()
        blob = out.tobytes()
    finally:
        out.close()

    result: dict = {
        "input_count": len(documents),
        "page_count": sum(s["page_count"] for s in sources),
        "size_bytes": len(blob),
        "sources": sources,
    }
    if len(blob) <= MAX_MERGED_BYTES:
        result["file_base64"] = base64.b64encode(blob).decode()
    else:
        result["file_base64"] = None
        result["note"] = (
            f"Merged PDF exceeds the {MAX_MERGED_BYTES // (1024 * 1024)} MB response limit."
        )
    return result


def extract_images(
    data: bytes,
    pages: str = "",
    password: str = "",
    max_images: int = 20,
    include_base64: bool = False,
) -> dict:
    """List (and optionally export) images embedded in a PDF."""
    doc = open_pdf(data, password)
    try:
        indices = parse_pages(pages, doc.page_count)
        if indices is None:
            indices = list(range(doc.page_count))
        max_images = max(1, min(int(max_images or 20), MAX_IMAGES))

        images: list[dict] = []
        truncated = False
        seen_xrefs: set[int] = set()
        for pno in indices:
            for info in doc[pno].get_images(full=True):
                xref = info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                if len(images) >= max_images:
                    truncated = True
                    break
                try:
                    pix = doc.extract_image(xref)
                except Exception:
                    continue
                blob = pix.get("image") or b""
                if not blob:
                    continue
                ext = str(pix.get("ext") or "bin").lower()
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                item: dict = {
                    "page": pno + 1,
                    "index": len(images) + 1,
                    "width": pix.get("width"),
                    "height": pix.get("height"),
                    "ext": ext,
                    "mime": mime,
                    "size_bytes": len(blob),
                }
                if include_base64:
                    if len(blob) <= MAX_IMAGE_B64_BYTES:
                        item["base64"] = base64.b64encode(blob).decode()
                    else:
                        item["base64"] = None
                        item["note"] = "Image exceeds the 2 MB export limit."
                images.append(item)
            if truncated:
                break
        return {
            "page_count": doc.page_count,
            "image_count": len(images),
            "truncated": truncated,
            "images": images,
        }
    finally:
        doc.close()
