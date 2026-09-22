"""PDF table extraction via PyMuPDF's structural table finder."""

from __future__ import annotations

import csv
import io

from .convert import ConversionError, open_pdf, parse_pages
from .detect import PDF


def _rows_to_markdown(rows: list[list]) -> str:
    """Build a GitHub-flavoured markdown table from extracted rows."""
    clean: list[list[str]] = []
    for row in rows:
        clean.append(
            [("" if cell is None else str(cell)).replace("\n", " ").replace("|", "\\|").strip() for cell in row]
        )
    if not clean:
        return ""
    width = max(len(r) for r in clean)
    clean = [r + [""] * (width - len(r)) for r in clean]
    header, *body = clean
    out = ["| " + " | ".join(header) + " |", "|" + "|".join([" --- "] * width) + "|"]
    for row in body:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def _rows_to_csv(rows: list[list]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(["" if cell is None else str(cell).replace("\n", " ") for cell in row])
    return buf.getvalue()


def extract_tables(
    data: bytes,
    pages: str = "",
    password: str = "",
    fmt: str = "markdown",
    max_tables: int = 50,
) -> dict:
    """Extract tables from a PDF.

    Returns a dict with ``page_count``, ``tables`` (list of
    ``{page, index, rows, columns, content}``) and ``truncated``.
    """
    fmt = (fmt or "markdown").lower()
    if fmt not in ("markdown", "csv", "json"):
        raise ConversionError("format must be one of: markdown, csv, json.")

    doc = open_pdf(data, password)
    try:
        page_indices = parse_pages(pages, doc.page_count)
        if page_indices is None:
            page_indices = list(range(doc.page_count))
        # cap the number of pages scanned to keep calls cheap
        if len(page_indices) > 100:
            page_indices = page_indices[:100]

        tables: list[dict] = []
        truncated = False
        for pno in page_indices:
            try:
                finder = doc[pno].find_tables()
                found = list(finder.tables)
            except Exception:
                found = []
            for i, tab in enumerate(found):
                if len(tables) >= max_tables:
                    truncated = True
                    break
                try:
                    rows = tab.extract()
                except Exception:
                    continue
                if not rows:
                    continue
                if fmt == "csv":
                    content = _rows_to_csv(rows)
                elif fmt == "json":
                    content = rows  # structured rows
                else:
                    content = _rows_to_markdown(rows)
                tables.append(
                    {
                        "page": pno + 1,
                        "index": i + 1,
                        "rows": len(rows),
                        "columns": max(len(r) for r in rows),
                        "content": content,
                    }
                )
            if truncated:
                break
        return {
            "page_count": doc.page_count,
            "table_count": len(tables),
            "truncated": truncated,
            "tables": tables,
        }
    finally:
        doc.close()


def search_document(
    data: bytes,
    query: str,
    password: str = "",
    max_results: int = 20,
) -> dict:
    """Full-text keyword search over PDF pages; returns snippets + page numbers."""
    query = (query or "").strip()
    if not query:
        raise ConversionError("query must not be empty.")
    max_results = max(1, min(max_results, 100))

    doc = open_pdf(data, password)
    try:
        needle = query.lower()
        matches: list[dict] = []
        for pno in range(doc.page_count):
            try:
                text = doc[pno].get_text("text")
            except Exception:
                continue
            lower = text.lower()
            start = lower.find(needle)
            while start != -1 and len(matches) < max_results:
                snippet_start = max(0, start - 100)
                snippet_end = min(len(text), start + len(query) + 160)
                snippet = text[snippet_start:snippet_end].replace("\n", " ").strip()
                matches.append(
                    {
                        "page": pno + 1,
                        "offset_in_page": start,
                        "snippet": ("…" if snippet_start > 0 else "") + snippet + ("…" if snippet_end < len(text) else ""),
                    }
                )
                start = lower.find(needle, start + len(query))
            if len(matches) >= max_results:
                break
        return {
            "query": query,
            "page_count": doc.page_count,
            "match_count": len(matches),
            "truncated": len(matches) >= max_results,
            "matches": matches,
        }
    finally:
        doc.close()


def document_info(data: bytes, kind: str, password: str = "") -> dict:
    """Metadata summary for a document (PDF gets rich info; others basic)."""
    if kind == PDF:
        doc = open_pdf(data, password)
        try:
            from .convert import _detect_scanned

            meta = doc.metadata or {}
            toc = [list(entry) for entry in (doc.get_toc() or [])]
            return {
                "kind": "pdf",
                "page_count": doc.page_count,
                "is_scanned": _detect_scanned(doc),
                "is_encrypted": bool(doc.is_encrypted),
                "metadata": {
                    k: v
                    for k, v in meta.items()
                    if k in ("title", "author", "subject", "keywords", "creator", "producer", "creationDate", "modDate") and v
                },
                "toc": toc[:100],
                "size_bytes": len(data),
            }
        finally:
            doc.close()

    return {
        "kind": kind,
        "size_bytes": len(data),
        "note": "Rich metadata is only available for PDFs; use convert_document_to_markdown to read the content.",
    }
