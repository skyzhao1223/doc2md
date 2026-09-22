# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
