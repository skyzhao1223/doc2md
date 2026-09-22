"""Tests for split / merge / image extraction."""

from __future__ import annotations

import base64

import pytest

from doc2md.convert import ConversionError
from doc2md.pdfops import extract_images, merge_pdfs, parse_ranges, split_pdf


def test_parse_ranges():
    assert parse_ranges("1-2,4", 10) == [(1, 2), (4, 4)]
    with pytest.raises(ConversionError):
        parse_ranges("", 10)
    with pytest.raises(ConversionError):
        parse_ranges("5-3", 10)
    with pytest.raises(ConversionError):
        parse_ranges("9-11", 10)
    with pytest.raises(ConversionError):
        parse_ranges(",".join(str(i) for i in range(1, 25)), 30)  # >20 parts


def test_split_pdf(sample_pdf):
    out = split_pdf(sample_pdf, "1,2")
    assert out["page_count"] == 2
    assert out["part_count"] == 2
    for part in out["parts"]:
        assert part["page_count"] == 1
        raw = base64.b64decode(part["file_base64"])
        assert raw.startswith(b"%PDF")
    # each part is a valid single-page PDF readable by our own reader
    first = base64.b64decode(out["parts"][0]["file_base64"])
    info_pages = _page_count(first)
    assert info_pages == 1


def test_split_then_merge_roundtrip(sample_pdf):
    parts = split_pdf(sample_pdf, "1,2")["parts"]
    merged = merge_pdfs([base64.b64decode(p["file_base64"]) for p in parts])
    assert merged["page_count"] == 2
    assert merged["input_count"] == 2
    blob = base64.b64decode(merged["file_base64"])
    assert blob.startswith(b"%PDF")
    assert _page_count(blob) == 2


def test_merge_rejects_bad_input(sample_pdf):
    with pytest.raises(ConversionError):
        merge_pdfs([sample_pdf])
    with pytest.raises(ConversionError):
        merge_pdfs([sample_pdf, b"not a pdf"])


def test_extract_images_metadata(scanned_pdf):
    out = extract_images(scanned_pdf)
    assert out["image_count"] >= 1
    img = out["images"][0]
    assert img["page"] == 1
    assert img["width"] > 0 and img["height"] > 0
    assert "base64" not in img  # metadata-only by default


def test_extract_images_with_base64(scanned_pdf):
    out = extract_images(scanned_pdf, include_base64=True)
    img = out["images"][0]
    assert img["base64"]
    raw = base64.b64decode(img["base64"])
    assert len(raw) == img["size_bytes"]


def _page_count(blob: bytes) -> int:
    import pymupdf

    doc = pymupdf.open(stream=blob, filetype="pdf")
    try:
        return doc.page_count
    finally:
        doc.close()
