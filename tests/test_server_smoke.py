"""End-to-end smoke test: in-process MCP client <-> FastMCP server."""

from __future__ import annotations

import base64
import json

import pytest

EXPECTED_TOOLS = {
    "convert_pdf_to_markdown",
    "convert_document_to_markdown",
    "extract_pdf_tables",
    "read_pdf_pages",
    "get_document_info",
    "search_document",
    "ocr_document",
    "split_pdf",
    "merge_pdfs",
    "extract_pdf_images",
}


def _connect():
    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )
    from doc2md.server import mcp as fastmcp

    return connect(fastmcp._mcp_server)


def _text(result) -> str:
    return "\n".join(
        block.text for block in result.content if getattr(block, "type", "") == "text"
    )


def _structured(result) -> dict:
    content = getattr(result, "structuredContent", None)
    if content is not None:
        return content
    return json.loads(_text(result))


@pytest.mark.anyio
async def test_tools_are_listed_with_descriptions(sample_pdf):
    async with _connect() as session:
        listed = await session.list_tools()
        tools = {t.name: t for t in listed.tools}
        assert EXPECTED_TOOLS <= set(tools)
        for name in EXPECTED_TOOLS:
            assert tools[name].description and len(tools[name].description) > 40


@pytest.mark.anyio
async def test_convert_pdf_via_base64(sample_pdf):
    b64 = base64.b64encode(sample_pdf).decode()
    async with _connect() as session:
        result = await session.call_tool(
            "convert_pdf_to_markdown",
            {"file_base64": b64, "filename": "sample.pdf"},
        )
        assert not result.isError
        assert "Doc2md Sample Report" in _text(result)


@pytest.mark.anyio
async def test_convert_document_docx(sample_docx):
    b64 = base64.b64encode(sample_docx).decode()
    async with _connect() as session:
        result = await session.call_tool(
            "convert_document_to_markdown",
            {"file_base64": b64, "filename": "hello.docx"},
        )
        assert not result.isError
        assert "Hello Docx" in _text(result)


@pytest.mark.anyio
async def test_pagination_truncation(sample_pdf):
    b64 = base64.b64encode(sample_pdf).decode()
    async with _connect() as session:
        first = await session.call_tool(
            "convert_pdf_to_markdown",
            {"file_base64": b64, "filename": "sample.pdf", "max_chars": 1000},
        )
        text = _text(first)
        if "output truncated" in text:
            assert "offset=1000" in text


@pytest.mark.anyio
async def test_info_and_search(sample_pdf):
    b64 = base64.b64encode(sample_pdf).decode()
    async with _connect() as session:
        info = _structured(
            await session.call_tool("get_document_info", {"file_base64": b64})
        )
        assert info["page_count"] == 2
        assert info["kind"] == "pdf"

        found = _structured(
            await session.call_tool(
                "search_document", {"file_base64": b64, "query": "zebracat"}
            )
        )
        assert found["match_count"] >= 1

        pages = await session.call_tool(
            "read_pdf_pages", {"file_base64": b64, "pages": "2"}
        )
        assert "Second page content" in _text(pages)


@pytest.mark.anyio
async def test_tables(sample_pdf):
    b64 = base64.b64encode(sample_pdf).decode()
    async with _connect() as session:
        out = _structured(
            await session.call_tool(
                "extract_pdf_tables", {"file_base64": b64, "format": "markdown"}
            )
        )
        assert out["table_count"] >= 1
        assert "Widget" in out["tables"][0]["content"]


@pytest.mark.anyio
async def test_error_paths(sample_pdf):
    async with _connect() as session:
        # no source at all
        result = await session.call_tool("get_document_info", {})
        assert result.isError

        # both sources
        result = await session.call_tool(
            "get_document_info",
            {"url": "https://example.com/a.pdf", "file_base64": "AAAA"},
        )
        assert result.isError

        # SSRF-blocked URL
        result = await session.call_tool(
            "get_document_info", {"url": "http://127.0.0.1:8080/a.pdf"}
        )
        assert result.isError
        assert "Refusing" in _text(result) or "Failed to fetch" in _text(result)


@pytest.mark.anyio
async def test_ocr_image(sample_png_bytes):
    pytest.importorskip("rapidocr_onnxruntime")
    b64 = base64.b64encode(sample_png_bytes).decode()
    async with _connect() as session:
        result = await session.call_tool(
            "ocr_document", {"file_base64": b64, "filename": "page.png"}
        )
        assert not result.isError
        out = _structured(result)
        assert "Doc2md" in out.get("text", "") or "Sample" in out.get("text", "")


@pytest.mark.anyio
async def test_split_and_merge_via_mcp(sample_pdf):
    b64 = base64.b64encode(sample_pdf).decode()
    async with _connect() as session:
        split = _structured(
            await session.call_tool(
                "split_pdf", {"file_base64": b64, "ranges": "1,2"}
            )
        )
        assert split["part_count"] == 2

        merged = _structured(
            await session.call_tool(
                "merge_pdfs",
                {"files_base64": [p["file_base64"] for p in split["parts"]]},
            )
        )
        assert merged["page_count"] == 2
        assert merged["file_base64"]

        # error path: neither urls nor files
        bad = await session.call_tool("merge_pdfs", {})
        assert bad.isError


@pytest.mark.anyio
async def test_extract_images_via_mcp(scanned_pdf):
    b64 = base64.b64encode(scanned_pdf).decode()
    async with _connect() as session:
        out = _structured(
            await session.call_tool(
                "extract_pdf_images", {"file_base64": b64, "include_base64": True}
            )
        )
        assert out["image_count"] >= 1
        assert out["images"][0]["base64"]
