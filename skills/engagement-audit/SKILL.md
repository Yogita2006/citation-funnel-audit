---
name: engagement-audit
description: Retain gate of the Citation Funnel audit. Checks whether a visitor who clicks through from an AI answer or search result is oriented and kept, covering first-screen orientation (headline plus explanatory sentence plus next step), call-to-action presence, mobile viewport, page weight, broken internal links, navigation depth including key pages the homepage fails to link, readability, and site search. Use when a site gets traffic but visitors bounce, or as the on-site engagement half of a full brand audit.
license: MIT
compatibility: Requires Python 3.8+. Reads a crawl cache produced by the audit-orchestrator skill.
allowed-tools: Bash(python3:*) Read
---

# Engagement Audit

A visitor arriving from an AI answer has a formed question and a low patience
budget. This skill checks the mechanics of the first thirty seconds that a
static fetch can prove, and flags only what the markup itself demonstrates.

## When to use

As the fifth gate of the Citation Funnel audit, or standalone when analytics
show arrivals but no engagement.

## Inputs

A crawl cache directory containing `manifest.json`, produced by
`audit-orchestrator/scripts/crawl_site.py`.

## Procedure

1. Run `python3 scripts/check_engagement.py --cache <cache-dir>`.
2. Orientation pass: does the homepage open, in document order, with an h1 and
   an explanatory paragraph of 12 or more words before navigation noise or
   consent text? A visitor must be able to confirm they are in the right place
   without scrolling.
3. Action pass: at least one button or link with action wording; missing
   viewport meta tag (mobile arrivals get a zoomed-out desktop page); homepage
   HTML weight and script count as a latency proxy.
4. Path pass: broken internal links among the crawled sample (each one ends a
   human session and truncates a machine crawl), too few or too many
   navigation links, walls of text over 120 words, and presence of site
   search on content-rich sites.
5. Static analysis cannot see rendered layout, so severities here are capped
   below the discoverability gates unless the markup itself proves the problem
   (a missing viewport tag or a broken link is proof; a suspected layout issue
   is not). Details in [references/checks.md](references/checks.md).

## Output

JSON on stdout: `{"module": "engagement", "findings": [...], "proactive":
[...], "stats": {"home_html_kb": N, "nav_links": N, "ctas_found": N}}`.
