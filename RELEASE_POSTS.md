# Launch posts — copy/paste drafts

Glama directory page (live): https://glama.ai/mcp/servers/skyzhao1223/doc2md
PyPI (live): https://pypi.org/project/doc2md-mcp/

---

## 1. Reddit — r/mcp

> Post with the **Self-Promotion / Show & Tell** flair (check current flair list).
> Do NOT copy-paste this to r/LocalLLaMA (strict self-promo rules — write a
> technical deep-dive instead, e.g. "URL-first vs local-stdio MCP design").
> For r/ClaudeAI, rewrite as a Claude Desktop config tutorial.

**Title (pick one):**

- I built an MCP server that turns any document URL into clean Markdown — PDF tables survive, scanned files get offline OCR (AGPL, on PyPI)
- Show r/mcp: doc2md — URL-first document→Markdown MCP server (tables, OCR, split/merge), keyless and open source

**Body:**

**TL;DR:** `doc2md` is an open-source MCP server (AGPL) that converts PDF / DOCX / PPTX / XLSX / EPUB / HTML to clean Markdown from a **URL or base64** — tables preserved, offline OCR for scans, paginated output so your context window survives. Install with `uvx`, run the Docker image, or one-click deploy on Glama.

**Why I built it.** Document-heavy agent workflows keep hitting the same wall: cloud agents can't reach local-only stdio servers, conversion SaaS APIs mean keys + billing + upload policies, and naive PDF→text dumps flatten tables into noise. I wanted one tool where an agent just hands over a URL and gets Markdown back — deployable anywhere, keyless.

**The tools (10):**

- `convert_pdf_to_markdown` — headings, lists and **real tables** preserved (PyMuPDF4LLM under the hood). Large files page through with `offset`/`max_chars`.
- `convert_document_to_markdown` — one tool for DOCX / PPTX / XLSX / EPUB / HTML / CSV / PDF, auto-detected; scanned files fall back to OCR.
- `extract_pdf_tables` — tables as Markdown, CSV or JSON rows, with page numbers.
- `search_document` + `read_pdf_pages` + `get_document_info` — find and read exactly the pages you need instead of converting a 300-page manual.
- `ocr_document` — offline OCR (RapidOCR/ONNX) for scanned PDFs, receipts, screenshots. No cloud OCR API, no per-page bill.
- `split_pdf` / `merge_pdfs` / `extract_pdf_images` — the PDF plumbing agents keep needing.

**Real run against the Attention paper** (not a curated example, just `arxiv.org`):

```
get_document_info {"url": "https://arxiv.org/pdf/1706.03762"}
→ {"kind": "pdf", "page_count": 15, "is_scanned": false}

extract_pdf_tables {"url": "…", "pages": "8-9", "format": "markdown"}
→ | Model | BLEU EN⟶DE | Training Cost (FLOPs) |
  | ByteNet | 23.75 | … |
  | GNMT+RL | 24.6 | 2.3·10¹⁹ |
```

**Install (free, local):**

```json
{
  "mcpServers": {
    "doc2md": {
      "command": "uvx",
      "args": ["--from", "doc2md-mcp[ocr]", "doc2md"]
    }
  }
}
```

or `pip install "doc2md-mcp[ocr]"`, or the Docker image (`DOC2MD_TRANSPORT=streamable-http` for a remote endpoint).

**Honesty corner:** yes, the `[ocr]` extra pulls opencv + onnxruntime (~60 packages). That's the price of *fully offline* OCR. Skip the extra and core conversion still works — and every tool degrades with an actionable error instead of crashing. Also: all 10 tools declare MCP annotations (`readOnlyHint`, `idempotentHint`, …) so your client knows they're pure, retry-safe reads.

**Security, because it's meant to be exposed:** SSRF protection on every URL *and every redirect hop* (private/loopback/link-local IPs rejected), 30 MB caps, non-root container, no persistence — documents are processed in memory and dropped.

**Links:**

- GitHub (34 tests, CI on Python 3.10–3.12): https://github.com/skyzhao1223/doc2md
- PyPI: https://pypi.org/project/doc2md-mcp/
- Glama listing — one-click deploy **to your own Glama workspace** (their hosting is metered; local/Docker use is free): https://glama.ai/mcp/servers/skyzhao1223/doc2md

Feedback welcome — especially conversion quality vs. whatever you've tried. Roadmap: formula/LaTeX extraction pass, batch jobs. AGPL because PyMuPDF is AGPL; the repo is fully open.

---

## 2. Glama Discord — #showcase (short version)

**doc2md** — keyless document→Markdown MCP server, built for remote hosting 📄

Pass a URL, get clean Markdown: PDF (tables preserved!), DOCX/PPTX/XLSX/EPUB/HTML, offline OCR for scans, split/merge/search — 10 tools, all with MCP annotations. SSRF-safe, 30 MB caps, non-root Docker, AGPL, 34 tests + CI. TDQS: all A so far 🎉

- Run locally: `uvx --from 'doc2md-mcp[ocr]' doc2md`
- GitHub: https://github.com/skyzhao1223/doc2md
- On Glama: https://glama.ai/mcp/servers/skyzhao1223/doc2md

Happy to write up the "URL-first vs local-stdio" design tradeoffs if anyone's interested.

---

## 3. X / Twitter thread (optional)

1/ Shipped doc2md: an open-source MCP server that turns any document URL into clean Markdown — no API key, built to be hosted. 📄→✨

2/ Most doc-conversion MCP servers are local-only (stdio). Agents in the cloud can't use them. doc2md takes {"url": "..."} and returns Markdown: PDF tables preserved, DOCX/PPTX/XLSX/EPUB/HTML auto-detected.

3/ Big files don't blow up your context: paginated output with offset continuation, plus search_document + read_pdf_pages to read only what you need.

4/ Scanned PDF? ocr_document runs offline RapidOCR — no cloud OCR bill. Also split/merge PDFs and export embedded figures. All tools declare readOnly/idempotent MCP annotations.

5/ SSRF-hardened (every redirect hop IP-checked), 30 MB caps, non-root container, AGPL. 34 tests, CI on 3.10–3.12.

Install: uvx --from 'doc2md-mcp[ocr]' doc2md
GitHub: https://github.com/skyzhao1223/doc2md
On @glama_ai (one-click deploy): https://glama.ai/mcp/servers/skyzhao1223/doc2md

---

## Posting checklist

- [ ] Reddit: post on a weekday morning US time; pick the right flair
- [ ] Reddit: answer the top comments within the first few hours
- [ ] Discord: check channel rules first; some servers want a role/opt-in
- [ ] Do NOT copy-paste the Reddit text to r/LocalLLaMA or r/ClaudeAI — rewrite per community (see notes at the top)
- [ ] After 1 week: follow-up post with real numbers ("what agents actually call most", conversion stats, GitHub/PyPI traffic)
