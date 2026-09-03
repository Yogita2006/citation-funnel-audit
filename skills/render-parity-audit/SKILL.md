---
name: render-parity-audit
description: Read gate of the Citation Funnel audit. Measures the gap between what a human sees in a browser and what a non-JavaScript fetcher receives in raw HTML, detecting client-side app shells with no crawlable text, thin key pages, facts locked in images without alt text, core content trapped in PDFs, iframe-embedded content, content revealed only by scroll or a load-more click, and a homepage whose substance is locked inside a video. Use when a site looks complete to humans but AI assistants and crawlers seem to know nothing that is on it.
license: MIT
compatibility: Requires Python 3.8+. Reads a crawl cache produced by the audit-orchestrator skill.
allowed-tools: Bash(python3:*) Read
---

# Render Parity Audit

AI retrieval fetchers read the raw HTML response and generally do not execute
JavaScript. A page that assembles its content client side is complete to a
person and empty to the machine. This skill measures that gap.

## When to use

As the second gate of the Citation Funnel audit, or standalone when a visually
complete site produces AI answers that miss facts plainly visible on screen.

## Inputs

A crawl cache directory containing `manifest.json`, produced by
`audit-orchestrator/scripts/crawl_site.py`.

## Procedure

1. Run `python3 scripts/check_render.py --cache <cache-dir>`.
2. The script computes, per page, the visible text word count outside scripts
   and styles, then flags: a homepage that is a framework shell (app root
   element plus under 150 words; downgraded one level if a serialized state
   blob like `__NEXT_DATA__` still carries the content), key interior pages
   under 120 words, a majority of images without alt text, PDF links whose
   names suggest core content (menus, price lists, specs), and non-media
   iframes carrying the main content of a thin page.
3. Review evidence before accepting findings. Word-count thresholds are
   deliberately conservative; a minimal landing page with 130 real words is
   not a shell. Thresholds and rationale are in
   [references/checks.md](references/checks.md).

## Output

JSON on stdout: `{"module": "render", "findings": [...], "proactive": [...],
"stats": {"pages": [per-page word counts and sizes]}}`. The per-page stats
table doubles as the evidence a developer needs to reproduce the measurement
with `curl`.
