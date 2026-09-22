"""doc2md MCP server — convert documents to Markdown for AI agents.

Runs over stdio by default (Glama and other hosts wrap it into Streamable
HTTP automatically). Set DOC2MD_TRANSPORT=streamable-http and DOC2MD_PORT to
serve HTTP directly when self-hosting.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import os
from functools import partial
from typing import Annotated

from pydantic import Field

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from . import detect
from .convert import (
    ConversionError,
    document_to_markdown,
    parse_pages,
    pdf_to_markdown,
    slice_markdown,
    open_pdf,
)
from .fetch import FetchError, MAX_DOWNLOAD_BYTES, fetch_url
from .ocr import ocr_document as run_ocr
from .tables import (
    document_info as build_document_info,
    extract_tables as extract_tables_impl,
    search_document as search_document_impl,
)

DEFAULT_MAX_CHARS = 40_000
HARD_MAX_CHARS = 200_000

mcp = FastMCP(
    "doc2md",
    instructions=(
        "doc2md converts documents to clean Markdown for AI agents. Pass a public "
        "http(s) URL or base64-encoded file content — no API key required. "
        "Supports PDF (text + tables), DOCX, PPTX, XLSX, EPUB, HTML, CSV/JSON/XML "
        "and scanned documents/images via OCR. Typical flow: get_document_info to "
        "inspect, convert_pdf_to_markdown (with 'pages' for large files) to read, "
        "extract_pdf_tables for tabular data, ocr_document for scanned files."
    ),
)

UrlParam = Annotated[
    str,
    Field(
        description=(
            "Public http(s) URL of the document to fetch and convert. "
            "Leave empty when passing file_base64 instead."
        )
    ),
]
Base64Param = Annotated[
    str,
    Field(
        description=(
            "Base64-encoded file content (for documents not reachable by URL). "
            f"Decoded size limit: {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB. "
            "Leave empty when passing url instead."
        )
    ),
]
FilenameParam = Annotated[
    str,
    Field(
        description=(
            "Original filename with extension (e.g. 'report.docx'). Used as a "
            "format hint when content type cannot be detected automatically."
        )
    ),
]
PagesParam = Annotated[
    str,
    Field(description="1-based page selection like '1,3-5'. Empty means all pages."),
]
PasswordParam = Annotated[
    str, Field(description="Password for encrypted PDFs. Empty for normal files.")
]


async def _load_source(url: str, file_base64: str, filename: str) -> tuple[bytes, str]:
    """Resolve tool input to (document bytes, detected kind)."""
    url = (url or "").strip()
    file_base64 = (file_base64 or "").strip()
    if bool(url) == bool(file_base64):
        raise ToolError(
            "Provide exactly one source: either 'url' (http/https link) or "
            "'file_base64' (base64-encoded content)."
        )
    content_type = ""
    if url:
        try:
            data, content_type, _final_url = await fetch_url(url)
        except FetchError as exc:
            raise ToolError(f"Failed to fetch URL: {exc}")
        filename_hint = filename or _filename_from_url(_final_url)
    else:
        try:
            data = base64.b64decode(file_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ToolError(f"file_base64 is not valid base64: {exc}")
        if len(data) > MAX_DOWNLOAD_BYTES:
            raise ToolError(
                f"Decoded file exceeds the {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB limit."
            )
        filename_hint = filename

    kind = detect.detect_kind(data, filename_hint, content_type)
    if kind == detect.UNKNOWN:
        raise ToolError(
            "Could not detect the document format. Pass 'filename' with an "
            "extension (e.g. 'report.pdf') as a hint. Supported: PDF, DOCX, "
            "PPTX, XLSX, EPUB, HTML, CSV/JSON/XML/TXT, images."
        )
    return data, kind


def _filename_from_url(url: str) -> str:
    from urllib.parse import urlparse, unquote

    path = urlparse(url).path
    if not path or "/" not in path:
        return ""
    return unquote(path.rsplit("/", 1)[-1])


def _require_pdf(kind: str, data: bytes) -> None:
    if kind != detect.PDF:
        raise ToolError(
            f"This tool works on PDFs, but the source was detected as '{kind}'. "
            "Use convert_document_to_markdown for other formats."
        )


def _clamp_max_chars(max_chars: int) -> int:
    return max(1_000, min(int(max_chars or DEFAULT_MAX_CHARS), HARD_MAX_CHARS))


def _truncate_footer(tool: str, offset: int, end: int, total: int) -> str:
    return (
        f"\n\n---\n> **doc2md**: output truncated — showing characters "
        f"{offset}–{end} of {total}. Call `{tool}` again with the same source "
        f"and `offset={end}` to continue reading."
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def convert_pdf_to_markdown(
    url: UrlParam = "",
    file_base64: Base64Param = "",
    filename: FilenameParam = "",
    pages: PagesParam = "",
    password: PasswordParam = "",
    offset: Annotated[int, Field(description="Character offset to resume a truncated conversion (from a previous response footer).")] = 0,
    max_chars: Annotated[int, Field(description=f"Maximum characters to return (default {DEFAULT_MAX_CHARS}, max {HARD_MAX_CHARS}).")] = DEFAULT_MAX_CHARS,
) -> str:
    """Convert a PDF document to clean Markdown, preserving headings, tables,
    lists and reading order. Use this whenever an agent needs to *read* a PDF:
    reports, papers, invoices, manuals, slide exports. Accepts a public URL or
    base64 content; no API key needed.

    For large PDFs, convert selected pages ('pages': '1,3-5') or page through
    the output with 'offset'/'max_chars'. Scanned PDFs are rejected with a
    hint to use ocr_document instead.
    """
    data, kind = await _load_source(url, file_base64, filename)
    _require_pdf(kind, data)
    max_chars = _clamp_max_chars(max_chars)
    try:
        doc = await asyncio.to_thread(partial(open_pdf, data, password))
        page_count = doc.page_count
        doc.close()
        page_indices = parse_pages(pages, page_count) if pages.strip() else None
        result = await asyncio.to_thread(partial(pdf_to_markdown, data, page_indices, password))
    except ConversionError as exc:
        raise ToolError(str(exc))

    chunk, truncated, end, total = slice_markdown(result.markdown, int(offset or 0), max_chars)
    if truncated:
        chunk += _truncate_footer("convert_pdf_to_markdown", int(offset or 0), end, total)
    return chunk


@mcp.tool()
async def convert_document_to_markdown(
    url: UrlParam = "",
    file_base64: Base64Param = "",
    filename: FilenameParam = "",
    pages: PagesParam = "",
    password: PasswordParam = "",
    offset: Annotated[int, Field(description="Character offset to resume a truncated conversion.")] = 0,
    max_chars: Annotated[int, Field(description=f"Maximum characters to return (default {DEFAULT_MAX_CHARS}, max {HARD_MAX_CHARS}).")] = DEFAULT_MAX_CHARS,
) -> str:
    """Convert almost any document to Markdown in one call: DOCX, PPTX, XLSX,
    EPUB, HTML, CSV/JSON/XML/TXT and PDF are auto-detected from the URL or
    base64 content. This is the universal 'just give me the text' tool — use
    it when the file format is unknown or mixed.

    Images and scanned PDFs are routed to OCR automatically when the server
    has OCR installed. Legacy .doc/.xls/.ppt binaries are not supported.
    """
    data, kind = await _load_source(url, file_base64, filename)
    max_chars = _clamp_max_chars(max_chars)
    try:
        if kind == detect.PDF:
            doc = await asyncio.to_thread(partial(open_pdf, data, password))
            page_count = doc.page_count
            doc.close()
            page_indices = parse_pages(pages, page_count) if pages.strip() else None
            result = await asyncio.to_thread(partial(pdf_to_markdown, data, page_indices, password))
            markdown = result.markdown
        elif kind == detect.IMAGE:
            ocr_out = await run_ocr(data, kind, pages, password)
            markdown = ocr_out.get("text", "")
        elif kind in detect.OFFICE_KINDS:
            markdown = await asyncio.to_thread(partial(document_to_markdown, data, kind, filename))
        else:
            raise ConversionError(f"Unsupported document kind '{kind}'.")
    except ConversionError as exc:
        message = str(exc)
        # scanned PDF: transparently try OCR before giving up
        if kind == detect.PDF and "scanned" in message:
            try:
                ocr_out = await run_ocr(data, kind, pages, password)
                if ocr_out.get("text", "").strip():
                    markdown = ocr_out["text"]
                else:
                    raise ToolError(message)
            except ConversionError:
                raise ToolError(message)
        else:
            raise ToolError(message)

    if not markdown.strip():
        raise ToolError("Conversion produced no readable text.")
    chunk, truncated, end, total = slice_markdown(markdown, int(offset or 0), max_chars)
    if truncated:
        chunk += _truncate_footer("convert_document_to_markdown", int(offset or 0), end, total)
    return chunk


@mcp.tool()
async def extract_pdf_tables(
    url: UrlParam = "",
    file_base64: Base64Param = "",
    filename: FilenameParam = "",
    pages: PagesParam = "",
    password: PasswordParam = "",
    format: Annotated[str, Field(description="Output format for each table: 'markdown' (default), 'csv' or 'json'.")] = "markdown",
    max_tables: Annotated[int, Field(description="Maximum number of tables to return (default 50).")] = 50,
) -> dict:
    """Extract data tables from a PDF with structure preserved — returns each
    table's page number, dimensions and content as Markdown, CSV or JSON rows.
    Ideal for financial statements, spec sheets, price lists and any document
    where tables matter more than prose. Scans up to 100 pages per call.
    """
    data, kind = await _load_source(url, file_base64, filename)
    _require_pdf(kind, data)
    try:
        return await asyncio.to_thread(
            partial(extract_tables_impl, data, pages, password, format, int(max_tables or 50))
        )
    except ConversionError as exc:
        raise ToolError(str(exc))


@mcp.tool()
async def read_pdf_pages(
    url: UrlParam = "",
    file_base64: Base64Param = "",
    filename: FilenameParam = "",
    pages: Annotated[str, Field(description="1-based pages to read, e.g. '4' or '10-14'. Required.")] = "",
    password: PasswordParam = "",
) -> str:
    """Read the plain text of specific PDF pages — the cheapest way to inspect
    a known location in a large PDF (e.g. after finding page numbers with
    search_document or get_document_info). Returns text per page without
    Markdown table reconstruction. 'pages' is required.
    """
    data, kind = await _load_source(url, file_base64, filename)
    _require_pdf(kind, data)
    if not (pages or "").strip():
        raise ToolError("The 'pages' parameter is required, e.g. pages='2-5'.")

    def _read() -> str:
        doc = open_pdf(data, password)
        try:
            indices = parse_pages(pages, doc.page_count)
            assert indices is not None
            parts = []
            for pno in indices:
                text = doc[pno].get_text("text").strip()
                parts.append(f"## Page {pno + 1}\n\n{text if text else '(no embedded text — page may be scanned; use ocr_document)'}")
            return "\n\n".join(parts)
        finally:
            doc.close()

    try:
        return await asyncio.to_thread(_read)
    except ConversionError as exc:
        raise ToolError(str(exc))


@mcp.tool()
async def get_document_info(
    url: UrlParam = "",
    file_base64: Base64Param = "",
    filename: FilenameParam = "",
    password: PasswordParam = "",
) -> dict:
    """Inspect a document before converting it: detected format, page count,
    title/author metadata, table of contents (PDF), whether the file is
    scanned (needs OCR) or encrypted. Call this first for unknown or large
    documents to plan which pages to convert.
    """
    data, kind = await _load_source(url, file_base64, filename)
    try:
        return await asyncio.to_thread(partial(build_document_info, data, kind, password))
    except ConversionError as exc:
        raise ToolError(str(exc))


@mcp.tool()
async def search_document(
    url: UrlParam = "",
    file_base64: Base64Param = "",
    filename: FilenameParam = "",
    query: Annotated[str, Field(description="Case-insensitive text to search for.")] = "",
    password: PasswordParam = "",
    max_results: Annotated[int, Field(description="Maximum matches to return (default 20, max 100).")] = 20,
) -> dict:
    """Full-text keyword search inside a PDF: returns every match with its
    page number and a surrounding text snippet. Use it to locate information
    in large PDFs (manuals, contracts, filings) before reading the exact
    pages with read_pdf_pages — much cheaper than converting the whole file.
    """
    data, kind = await _load_source(url, file_base64, filename)
    _require_pdf(kind, data)
    try:
        return await asyncio.to_thread(
            partial(search_document_impl, data, query, password, int(max_results or 20))
        )
    except ConversionError as exc:
        raise ToolError(str(exc))


@mcp.tool()
async def ocr_document(
    url: UrlParam = "",
    file_base64: Base64Param = "",
    filename: FilenameParam = "",
    pages: PagesParam = "",
    password: PasswordParam = "",
) -> dict:
    """OCR a scanned PDF or image (PNG/JPEG/WebP/BMP/TIFF) and return the
    recognised text per page. Use this when a PDF has no embedded text layer
    (convert_pdf_to_markdown will tell you) or when extracting text from
    screenshots, photos of documents, receipts and forms. Limited to 30
    pages per call — narrow with 'pages'.
    """
    data, kind = await _load_source(url, file_base64, filename)
    try:
        return await run_ocr(data, kind, pages, password)
    except ConversionError as exc:
        raise ToolError(str(exc))


# ---------------------------------------------------------------------------
# Prompt (adds the Prompts capability for MCP clients that surface templates)
# ---------------------------------------------------------------------------


@mcp.prompt()
def summarize_document(url: str) -> str:
    """Summarize a document located at a URL using the doc2md conversion tools."""
    return (
        f"Summarize the document at {url}.\n\n"
        "Steps:\n"
        "1. Call get_document_info to learn the format, page count and whether it is scanned.\n"
        "2. Call convert_document_to_markdown (use pages/offset for large files; ocr_document if scanned).\n"
        "3. Produce: a 3-5 sentence executive summary, key points as bullets, "
        "and any tables or figures worth reproducing in Markdown."
    )


def main() -> None:
    transport = os.environ.get("DOC2MD_TRANSPORT", "stdio").lower()
    if transport in ("streamable-http", "sse"):
        mcp.settings.host = os.environ.get("DOC2MD_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("DOC2MD_PORT", "8000"))
        mcp.run(transport=transport)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
