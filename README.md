# doc2md

**Turn any document into clean Markdown — built for AI agents.**

`doc2md` is an MCP server that converts **PDF, DOCX, PPTX, XLSX, EPUB, HTML,
CSV/JSON/XML** and **scanned files (OCR)** into agent-ready Markdown. Pass a
public URL or base64 content; **no API key, no account, no local
dependencies** for the agent side.

Most document-conversion MCP servers only run locally over stdio. `doc2md` is
designed to be **deployed remotely** (Streamable HTTP) so any agent — Claude,
ChatGPT, Cursor, Glama Chat, your own pipelines — can hand it a URL and get
Markdown back in one call.

## Why agents love it

- **URL-first** — `{"url": "https://…/report.pdf"}` is all it takes; base64 supported for local files
- **Tables survive** — PDF tables are extracted as Markdown/CSV/JSON, not flattened into noise
- **Pagination built in** — large documents return in chunks with a `offset` continuation hint, so context windows stay healthy
- **Scanned? No problem** — automatic detection, with a dedicated OCR tool (RapidOCR, offline, no cloud OCR API)
- **Cheap inspection first** — `get_document_info` and `search_document` let agents find the right pages before converting anything
- **Safe to expose** — SSRF protection (private/loopback/link-local IPs rejected on every redirect hop), 30 MB download cap, password-PDF support

## Tools

| Tool | What it does |
| --- | --- |
| `convert_pdf_to_markdown` | PDF → Markdown with headings, tables, lists and reading order preserved. `pages` selection + `offset`/`max_chars` pagination. |
| `convert_document_to_markdown` | Universal one-call converter: auto-detects DOCX/PPTX/XLSX/EPUB/HTML/CSV/PDF and returns Markdown. Falls back to OCR for scanned PDFs and images. |
| `extract_pdf_tables` | Structural table extraction → `markdown`, `csv` or `json` rows, with page numbers and dimensions. |
| `read_pdf_pages` | Plain text of specific pages — the cheapest way to read a known location. |
| `get_document_info` | Format, page count, metadata, table of contents, scanned/encrypted flags. |
| `search_document` | Full-text keyword search with page numbers + snippets. |
| `ocr_document` | OCR for scanned PDFs and images (PNG/JPEG/WebP/BMP/TIFF), up to 30 pages per call. |
| `split_pdf` | Cut a PDF into parts by page range (`'1-3,5,8-10'`); each part returned as base64 (≤5 MB). |
| `merge_pdfs` | Merge 2–10 PDFs (URLs or base64) into one document, returned as base64 (≤10 MB). |
| `extract_pdf_images` | List/export embedded images (figures, charts, scans) with page, dimensions, format; optional base64 (≤2 MB each). |

Plus a `summarize_document` **prompt template** for clients that surface MCP prompts.

## Quickstart

### Hosted (zero install)

Deploy your own instance on [Glama](https://glama.ai/mcp/hosting) in one click
from the registry, or run the Docker image below, then point any MCP client at
the Streamable HTTP endpoint:

```json
{
  "mcpServers": {
    "doc2md": {
      "type": "streamable-http",
      "url": "https://glama.ai/endpoints/<your-profile>/mcp"
    }
  }
}
```

### Claude Desktop / Cursor (local)

```json
{
  "mcpServers": {
    "doc2md": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/skyzhao1223/doc2md#egg=doc2md-mcp[ocr]", "doc2md"]
    }
  }
}
```

### Docker

```bash
docker build -t doc2md .
docker run --rm -i doc2md                      # stdio
docker run --rm -p 8000:8000 \
  -e DOC2MD_TRANSPORT=streamable-http doc2md   # HTTP endpoint
```

### From source

```bash
git clone https://github.com/skyzhao1223/doc2md && cd doc2md
uv sync --extra ocr --extra dev
uv run doc2md          # stdio server
uv run pytest          # test suite
```

## Example session

```
agent → get_document_info {"url": "https://arxiv.org/pdf/1706.03762"}
      ← {kind: "pdf", page_count: 15, is_scanned: false, toc: [...]}

agent → search_document {"url": "...", "query": "BLEU"}
      ← matches on pages 8, 9, 10 with snippets

agent → read_pdf_pages {"url": "...", "pages": "8-9"}
      ← plain text of exactly those pages
```

## Limits

| Limit | Value |
| --- | --- |
| Download / base64 size | 30 MB |
| Default response size | 40,000 chars (max 200,000), with `offset` continuation |
| OCR pages per call | 30 (renders at 200 dpi) |
| Table scan depth | first 100 pages per call, 50 tables max |
| Split | ≤20 parts per call, base64 included for parts ≤5 MB |
| Merge | ≤10 inputs, merged output ≤10 MB |
| Image export | ≤50 images per call, base64 for images ≤2 MB |
| URL fetch | public http(s) only, ≤5 redirects, SSRF-filtered |

## Self-hosting notes

- Transport: `DOC2MD_TRANSPORT=stdio` (default) or `streamable-http` / `sse`
  with `DOC2MD_HOST` / `DOC2MD_PORT`. Glama hosting wraps stdio automatically.
- OCR is optional: install the `ocr` extra (or use the Docker image, which
  includes it). Without OCR, all other tools still work and OCR calls return
  an actionable error.
- Conversion results are cached in memory (content-hash keyed, 30 min TTL) so
  paginated reads of the same document don't re-convert. Nothing is written
  to disk persistently; documents are processed in memory and dropped.

## Development

```bash
uv sync --extra dev --extra ocr
uv run pytest            # 40+ tests: detection, conversion, tables, split/merge, SSRF, in-process MCP smoke tests
```

Layout: `src/doc2md/{server,convert,tables,pdfops,ocr,fetch,detect,cache}.py`.

## Security

- **SSRF protection**: every URL (including each redirect hop) must resolve to
  public unicast IPs only; `file:`, `ftp:` and other schemes are rejected.
- **Size caps** on downloads, base64 payloads and OCR page counts.
- **No persistence**: documents live in memory for the duration of a call.
- Runs as a non-root user in the official Docker image.

## License

**AGPL-3.0-or-later** — see [LICENSE](LICENSE). The AGPL choice is driven by
[PyMuPDF](https://pymupdf.readthedocs.io/) (used via
[PyMuPDF4LLM](https://github.com/pymupdf/PyMuPDF4LLM) for high-quality PDF →
Markdown), which is AGPL itself. If you operate a modified version of this
server over a network, you must offer your users its source.

## Roadmap

- [ ] Formula / LaTeX extraction quality pass
- [x] `split_pdf`, `merge_pdfs` utility tools (v0.2.0)
- [x] Image extraction via `extract_pdf_images` with base64 export (v0.2.0)
- [ ] PyPI release (`doc2md-mcp`)
- [ ] Batch/webhook conversion jobs for very large documents
