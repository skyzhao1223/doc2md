"""Document kind detection from magic bytes (with filename fallback)."""

from __future__ import annotations

# Recognised kinds
PDF = "pdf"
DOCX = "docx"
PPTX = "pptx"
XLSX = "xlsx"
EPUB = "epub"
HTML = "html"
IMAGE = "image"
TEXT = "text"          # plain text / markdown / csv / json / xml
LEGACY_OFFICE = "legacy-office"  # .doc/.xls/.ppt binary formats (unsupported)
UNKNOWN = "unknown"

# kinds markitdown can convert when written to a temp file with this suffix
OFFICE_KINDS = {DOCX: ".docx", PPTX: ".pptx", XLSX: ".xlsx", EPUB: ".epub", HTML: ".html", TEXT: ".txt"}

_EXTENSION_MAP = {
    ".pdf": PDF,
    ".docx": DOCX,
    ".pptx": PPTX,
    ".xlsx": XLSX,
    ".epub": EPUB,
    ".html": HTML,
    ".htm": HTML,
    ".png": IMAGE,
    ".jpg": IMAGE,
    ".jpeg": IMAGE,
    ".webp": IMAGE,
    ".bmp": IMAGE,
    ".tif": IMAGE,
    ".tiff": IMAGE,
    ".txt": TEXT,
    ".md": TEXT,
    ".markdown": TEXT,
    ".csv": TEXT,
    ".json": TEXT,
    ".xml": TEXT,
    ".doc": LEGACY_OFFICE,
    ".xls": LEGACY_OFFICE,
    ".ppt": LEGACY_OFFICE,
}

_IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", IMAGE),
    (b"\xff\xd8\xff", IMAGE),                      # jpeg
    (b"GIF87a", IMAGE),
    (b"GIF89a", IMAGE),
    (b"BM", IMAGE),                                 # bmp
    (b"II*\x00", IMAGE),                            # tiff little-endian
    (b"MM\x00*", IMAGE),                            # tiff big-endian
)


def _zip_kind(data: bytes, filename: str) -> str:
    """Disambiguate OOXML / EPUB containers by peeking at entry names."""
    head = data[: min(len(data), 65536)]
    if b"META-INF/container.xml" in head:
        return EPUB
    if b"word/" in head:
        return DOCX
    if b"ppt/" in head:
        return PPTX
    if b"xl/" in head:
        return XLSX
    # fall back to extension
    return _from_extension(filename) or UNKNOWN


def _from_extension(filename: str) -> str | None:
    if not filename:
        return None
    name = filename.rsplit("/", 1)[-1].lower()
    for ext, kind in _EXTENSION_MAP.items():
        if name.endswith(ext):
            return kind
    return None


def _looks_textual(data: bytes) -> bool:
    sample = data[:4096]
    lowered = sample.lstrip().lower()
    if lowered.startswith(b"<!doctype html") or lowered.startswith(b"<html"):
        return True
    # control bytes other than \t \n \r mean binary content
    if any(b < 32 and b not in (9, 10, 13) for b in sample):
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def detect_kind(data: bytes, filename: str = "", content_type: str = "") -> str:
    """Detect the document kind of ``data``.

    Uses magic bytes first, then filename extension, then content-type.
    """
    if data.startswith(b"%PDF"):
        return PDF
    if data.startswith(b"PK\x03\x04") or data.startswith(b"PK\x05\x06"):
        return _zip_kind(data, filename)
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        return LEGACY_OFFICE
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return IMAGE
    for sig, kind in _IMAGE_SIGNATURES:
        if data.startswith(sig):
            return kind

    ext_kind = _from_extension(filename)
    if ext_kind:
        return ext_kind

    ct = (content_type or "").split(";")[0].strip().lower()
    if ct == "application/pdf":
        return PDF
    if ct.startswith("image/"):
        return IMAGE
    if ct in ("text/html", "application/xhtml+xml"):
        return HTML

    if _looks_textual(data):
        return HTML if (b"<html" in data[:4096].lower()) else TEXT
    return UNKNOWN


def suffix_for(kind: str, filename: str = "") -> str:
    """Best temp-file suffix for a detected kind."""
    if kind in OFFICE_KINDS:
        return OFFICE_KINDS[kind]
    ext_kind = _from_extension(filename)
    if ext_kind == kind and filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    if kind == PDF:
        return ".pdf"
    if kind == IMAGE:
        return ".png"
    return ".bin"
