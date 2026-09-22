# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.2.1] - 2026-09-22

### Added

- MCP tool annotations on all 10 tools (`readOnlyHint`, `destructiveHint`,
  `idempotentHint`, `openWorldHint`) — machine-readable behaviour disclosure
  for MCP clients and registry scoring (Glama TDQS Behavior dimension).

### Fixed

- PyPI metadata: license is now the SPDX expression `AGPL-3.0-or-later`
  (PEP 639) instead of the full license text.

## [0.2.0] - 2026-09-22

### Added

- New tools: `split_pdf` (ranges → base64 parts, 5 MB each), `merge_pdfs`
  (URLs or base64 inputs, 10 MB merged output), `extract_pdf_images`
  (metadata + optional base64 export, 2 MB per image).
- Multi-stage Dockerfile: slimmer runtime image (bytecode caches trimmed).

### Fixed

- Disabled pymupdf4llm's implicit auto-OCR (`use_ocr=False`) for
  deterministic conversions; scanned documents are routed through the
  explicit `ocr_document` tool instead. Fixes `'RapidOCR' object has no
  attribute 'text_detector'` on PDFs containing images with
  rapidocr-onnxruntime 1.4.x.

## [0.1.0] - 2026-09-22

### Added

- Initial release.
- Tools: `convert_pdf_to_markdown`, `convert_document_to_markdown`,
  `extract_pdf_tables`, `read_pdf_pages`, `get_document_info`,
  `search_document`, `ocr_document`.
- Prompt template: `summarize_document`.
- URL-first input with SSRF protection, redirect validation and 30 MB cap;
  base64 input for local files.
- Paginated output (`offset` / `max_chars`) with content-hash conversion cache.
- Optional offline OCR via RapidOCR (extra `ocr`; bundled in Docker image).
- Dockerfile (non-root, python:3.11-slim) and Glama hosting metadata
  (`glama.json`).
- Test suite: detection, conversion, tables, search, pagination, SSRF,
  in-process MCP smoke tests.
