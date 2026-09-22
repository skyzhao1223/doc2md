"""Shared fixtures: generated sample documents (no network needed)."""

from __future__ import annotations

import io

import pytest


@pytest.fixture(scope="session")
def sample_pdf() -> bytes:
    """Two-page PDF: heading + paragraph + a drawn 3x3 table on page 1."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Doc2md Sample Report", fontsize=18)
    page.insert_text(
        (72, 120),
        "This paragraph contains the keyword zebracat for search tests.",
        fontsize=11,
    )

    # draw a 3x3 table with cell text so find_tables() detects it
    x0, y0, col_w, row_h = 72, 200, 120, 24
    rows, cols = 3, 3
    for r in range(rows + 1):
        y = y0 + r * row_h
        page.draw_line((x0, y), (x0 + cols * col_w, y))
    for c in range(cols + 1):
        x = x0 + c * col_w
        page.draw_line((x, y0), (x, y0 + rows * row_h))
    data = [
        ["Name", "Qty", "Price"],
        ["Widget", "2", "9.99"],
        ["Gadget", "5", "24.50"],
    ]
    for r, row in enumerate(data):
        for c, cell in enumerate(row):
            page.insert_text((x0 + c * col_w + 6, y0 + r * row_h + 16), cell, fontsize=10)

    page2 = doc.new_page()
    page2.insert_text((72, 72), "Second page content.", fontsize=11)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture(scope="session")
def scanned_pdf(sample_png_page: bytes) -> bytes:
    """A PDF whose only page is a full-page image (no text layer)."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, pixmap=sample_png_page)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture(scope="session")
def sample_png_page(sample_pdf: bytes):
    """PNG rendering of the first sample page (image-only PDF fixture + OCR)."""
    import pymupdf

    doc = pymupdf.open(stream=sample_pdf, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=150)
    png = pix
    doc.close()
    return png


@pytest.fixture(scope="session")
def sample_png_bytes(sample_png_page) -> bytes:
    return sample_png_page.tobytes("png")


@pytest.fixture(scope="session")
def sample_docx() -> bytes:
    from docx import Document

    d = Document()
    d.add_heading("Hello Docx", level=1)
    d.add_paragraph("Paragraph text for docx conversion tests.")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture
def anyio_backend():
    return "asyncio"
