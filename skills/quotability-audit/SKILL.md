---
name: quotability-audit
description: Quote gate of the Citation Funnel audit. Tests whether a machine can lift clean, attributable facts from a website, by validating structured data (JSON-LD presence, parse validity, Organization and Offer coverage, sameAs) and by running a question probe that checks whether the questions people actually ask AI assistants about a brand (what is it, what does it cost, how do I contact them, who is behind it) are answerable from machine-readable text. Site-type aware: applies the schema a store/blog/local business/SaaS site actually needs, flags structured-vs-visible price mismatches, checks local-business address and hours, and heading hierarchy. Use when a site is crawlable and rendered but still never quoted correctly in AI answers.
license: MIT
compatibility: Requires Python 3.8+. Reads a crawl cache produced by the audit-orchestrator skill.
allowed-tools: Bash(python3:*) Read
---

# Quotability Audit

Being reachable and readable is not enough; a page is cited when a machine can
extract a specific fact and attribute it with confidence. This skill tests
extraction directly instead of checklisting.

## When to use

As the third gate of the Citation Funnel audit, or standalone when assistants
find the site but answer brand questions vaguely, wrongly, or from third
parties.

## Inputs

A crawl cache directory containing `manifest.json`, produced by
`audit-orchestrator/scripts/crawl_site.py`.

## Procedure

1. Run `python3 scripts/check_quotability.py --cache <cache-dir>`.
2. Structured-data pass: every JSON-LD block is extracted and parsed. Invalid
   JSON-LD is a high-severity finding on its own, because parsers discard the
   whole block silently, which is worse than honest absence. Then coverage:
   Organization or LocalBusiness anchor entity, sameAs profile links, Offer
   data on commercial sites.
3. Question probe pass: each canonical brand question is tested against the
   crawled text and schema. WHAT (a quotable one-sentence self-description in
   h1, first paragraphs, or meta description), PRICE (currency amounts or
   Offer schema; only probed when the site shows commercial intent, to avoid
   false positives on non-commercial sites), CONTACT (phone, email, or
   PostalAddress as text), WHO (an about page or founding facts). Every failed
   probe becomes a finding whose evidence states exactly what was searched.
4. Extraction-shape pass: exactly one h1 per page, unique titles, meta
   description, and density of quotable 25 to 90 word paragraph blocks
   (passages with clear claims and statistics are what generative engines
   lift, per the Princeton GEO findings).
5. The full probe list, patterns, and severity rules are in
   [references/checks.md](references/checks.md); a copy-paste JSON-LD starter
   is in [references/jsonld-templates.md](references/jsonld-templates.md).

## Output

JSON on stdout: `{"module": "quotability", "findings": [...], "proactive":
[...], "stats": {"jsonld_entities": [...], "quotable_paragraphs": N}}`.
