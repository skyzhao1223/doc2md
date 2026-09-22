# Launch posts — copy/paste drafts

Placeholder to fill after Glama deployment:
`GLAMA_URL` = your public server page, e.g. `https://glama.ai/mcp/servers/skyzhao1223/doc2md`

---

## 1. Reddit — r/mcp (also cross-postable to r/ClaudeAI, r/LocalLLaMA)

**Title:**
I built a keyless MCP server that turns any document URL into clean Markdown (PDF tables survive, scanned files get OCR)

**Body:**

Hey everyone,

I kept hitting the same wall with document-heavy agent workflows: every "PDF to Markdown" MCP server either runs locally only (stdio, install half of PyPI), needs an API key for a conversion SaaS, or flattens tables into noise.

So I built **doc2md** — open source (AGPL), and designed to be *hosted*: you pass a URL, you get Markdown. No key, no account.

What it does:

- `convert_pdf_to_markdown` — headings, lists and **real tables** preserved (PyMuPDF4LLM under the hood). Large files page through with `offset`/`max_chars` so your context window survives.
- `convert_document_to_markdown` — one tool for DOCX / PPTX / XLSX / EPUB / HTML / CSV / PDF, auto-detected.
- `extract_pdf_tables` — tables as Markdown, CSV or JSON rows, with page numbers.
- `search_document` + `read_pdf_pages` + `get_document_info` — cheap ways to find and read exactly the pages you need instead of converting a 300-page manual.
- `ocr_document` — offline OCR (RapidOCR) for scanned PDFs, receipts, screenshots. No cloud OCR API.
- `split_pdf` / `merge_pdfs` / `extract_pdf_images` — the PDF plumbing agents keep needing.

Security stuff, because it's meant to be exposed: SSRF protection on every URL and redirect hop (private/loopback/link-local IPs rejected), 30 MB caps, non-root container, no persistence — documents are processed in memory and dropped.

- GitHub: https://github.com/skyzhao1223/doc2md
- Hosted instance (deploy your own in one click via Glama): GLAMA_URL
- 34 tests + CI on Python 3.10–3.12, Docker smoke test included.

Feedback welcome — especially on conversion quality vs. other tools you've tried. Roadmap: formula/LaTeX extraction pass and batch jobs.

---

## 2. Glama Discord — #showcase (short version)

**doc2md** — keyless document→Markdown MCP server, built for remote hosting 📄

Pass a URL, get clean Markdown: PDF (tables preserved!), DOCX/PPTX/XLSX/EPUB/HTML, offline OCR for scans, split/merge/search tools. SSRF-safe, 30 MB caps, non-root Docker, AGPL, 34 tests + CI.

GitHub: https://github.com/skyzhao1223/doc2md
On Glama: GLAMA_URL

Would love feedback from the team — happy to write up the "URL-first vs local-stdio" design tradeoffs if useful.

---

## 3. X / Twitter thread (optional)

1/ Shipped doc2md: an open-source MCP server that turns any document URL into clean Markdown — no API key, built to be hosted. 📄→✨

2/ Most doc-conversion MCP servers are local-only (stdio). Agents in the cloud can't use them. doc2md takes {"url": "..."} and returns Markdown: PDF tables preserved, DOCX/PPTX/XLSX/EPUB/HTML auto-detected.

3/ Big files don't blow up your context: paginated output with offset continuation, plus search_document + read_pdf_pages to read only what you need.

4/ Scanned PDF? ocr_document runs offline RapidOCR — no cloud OCR bill. Also split/merge PDFs and export embedded figures.

5/ SSRF-hardened (every redirect hop IP-checked), 30 MB caps, non-root container, AGPL. 34 tests, CI on 3.10–3.12.

GitHub: https://github.com/skyzhao1223/doc2md
Deploy in one click on @glama_ai: GLAMA_URL

---

## Posting checklist

- [ ] Fill in GLAMA_URL after the deployment goes public
- [ ] Post Reddit on a weekday morning US time (best r/mcp traffic)
- [ ] Discord: check the channel rules first; some servers want a role/opt-in
- [ ] Reply to every comment in the first 24h (ranking signal + goodwill)
- [ ] After 1 week: post follow-up with tool-call analytics learnings ("what agents actually call most")
