"""Tests for detection, conversion, tables, search, pagination and cache."""

from __future__ import annotations

import time

import pytest

from doc2md import detect
from doc2md.cache import ConversionCache
from doc2md.convert import (
    ConversionError,
    document_to_markdown,
    parse_pages,
    pdf_to_markdown,
    slice_markdown,
)
from doc2md.tables import document_info, extract_tables, search_document


# --- detection -------------------------------------------------------------


def test_detect_kinds(sample_pdf, sample_docx, sample_png_bytes):
    assert detect.detect_kind(sample_pdf) == "pdf"
    assert detect.detect_kind(sample_docx) == "docx"
    assert detect.detect_kind(sample_png_bytes) == "image"
    assert detect.detect_kind(b"\xd0\xcf\x11\xe0garbage") == "legacy-office"
    assert detect.detect_kind(b"<html><body>hi</body></html>") == "html"
    assert detect.detect_kind(b"just plain text") == "text"
    assert detect.detect_kind(b"\x00\x01\x02binary", filename="x.pdf") == "pdf"
    assert detect.detect_kind(b"\x00\x01\x02binary") == "unknown"


# --- pdf conversion ---------------------------------------------------------


def test_pdf_to_markdown(sample_pdf):
    result = pdf_to_markdown(sample_pdf)
    assert result.page_count == 2
    assert not result.is_scanned
    assert "Doc2md Sample Report" in result.markdown
    assert "zebracat" in result.markdown
    # table content survives in some markdown/html table form
    assert "Widget" in result.markdown


def test_pdf_selected_pages(sample_pdf):
    result = pdf_to_markdown(sample_pdf, pages=[1])  # 0-based: second page
    assert "Second page content" in result.markdown
    assert "Doc2md Sample Report" not in result.markdown


def test_scanned_pdf_rejected_with_hint(scanned_pdf):
    with pytest.raises(ConversionError, match="scanned"):
        pdf_to_markdown(scanned_pdf)


def test_parse_pages():
    assert parse_pages("", 10) is None
    assert parse_pages("1,3-5", 10) == [0, 2, 3, 4]
    assert parse_pages("2", 10) == [1]
    with pytest.raises(ConversionError):
        parse_pages("0", 10)
    with pytest.raises(ConversionError):
        parse_pages("11", 10)
    with pytest.raises(ConversionError):
        parse_pages("a-b", 10)


def test_slice_markdown():
    text = "abcdefghij"
    chunk, truncated, nxt, total = slice_markdown(text, 0, 4)
    assert (chunk, truncated, nxt, total) == ("abcd", True, 4, 10)
    chunk, truncated, nxt, total = slice_markdown(text, 8, 4)
    assert (chunk, truncated, nxt, total) == ("ij", False, 10, 10)


# --- office conversion ------------------------------------------------------


def test_docx_to_markdown(sample_docx):
    markdown = document_to_markdown(sample_docx, "docx")
    assert "Hello Docx" in markdown
    assert "Paragraph text" in markdown


def test_legacy_office_rejected():
    with pytest.raises(ConversionError, match="Legacy"):
        document_to_markdown(b"\xd0\xcf\x11\xe0fake", "legacy-office")


# --- tables / search / info -------------------------------------------------


def test_extract_tables(sample_pdf):
    out = extract_tables(sample_pdf, fmt="markdown")
    assert out["table_count"] >= 1
    first = out["tables"][0]
    assert first["page"] == 1
    assert "Widget" in first["content"]
    assert "|" in first["content"]

    out_csv = extract_tables(sample_pdf, fmt="csv")
    assert "," in out_csv["tables"][0]["content"]

    out_json = extract_tables(sample_pdf, fmt="json")
    rows = out_json["tables"][0]["content"]
    assert any("Widget" in [str(c) for c in row] for row in rows)


def test_search_document(sample_pdf):
    out = search_document(sample_pdf, "zebracat")
    assert out["match_count"] >= 1
    assert out["matches"][0]["page"] == 1
    assert "zebracat" in out["matches"][0]["snippet"].lower()

    assert search_document(sample_pdf, "nonexistentwordxyz")["match_count"] == 0


def test_document_info(sample_pdf):
    info = document_info(sample_pdf, "pdf")
    assert info["kind"] == "pdf"
    assert info["page_count"] == 2
    assert info["is_scanned"] is False


# --- cache ------------------------------------------------------------------


def test_cache_ttl_and_lru():
    c = ConversionCache(ttl=0.05, max_entries=2, max_bytes=10_000)
    c.set("a", "x" * 10)
    assert c.get("a") == "x" * 10
    time.sleep(0.08)
    assert c.get("a") is None

    c.set("k1", "v1")
    c.set("k2", "v2")
    c.set("k3", "v3")  # evicts oldest (k1)
    assert c.get("k1") is None
    assert c.get("k3") == "v3"
