---
name: trust-signals-audit
description: Trust gate of the Citation Funnel audit. Checks whether a machine would believe and repeat what it reads on a website, covering machine-visible freshness (dateModified, sitemap lastmod, stale copyright years), entity disambiguation (consistent brand naming across schema, Open Graph and titles, sameAs corroboration links), and internal fact consistency (contradictory phone numbers). Use when a brand is found by AI assistants but described with stale, wrong, or mixed-up information.
license: MIT
compatibility: Requires Python 3.8+. Reads a crawl cache produced by the audit-orchestrator skill.
allowed-tools: Bash(python3:*) Read
---

# Trust Signals Audit

Machines repeat facts that look current, corroborated, and unambiguous. This
skill checks the trust surface a static fetch can prove: what the site itself
declares about its freshness and identity.

## When to use

As the fourth gate of the Citation Funnel audit, or standalone when assistants
describe the brand with outdated facts, or confuse it with another entity of a
similar name.

## Inputs

A crawl cache directory containing `manifest.json`, produced by
`audit-orchestrator/scripts/crawl_site.py`.

## Procedure

1. Run `python3 scripts/check_trust.py --cache <cache-dir>`.
2. Freshness pass: newest datePublished or dateModified in structured data,
   sitemap lastmod ages, and footer copyright years. Absence of any
   machine-readable date is itself a finding; declared dates older than 18
   months escalate it. The fix guidance is always to refresh content honestly,
   never to fake dates.
3. Identity pass: Organization schema name versus og:site_name versus title
   suffix must agree on one canonical brand string; sameAs or footer links to
   official off-site profiles (LinkedIn, Wikipedia or Wikidata, Crunchbase,
   GitHub, social) must exist so the site is not an uncorroborated island.
4. Consistency pass: hard facts that appear multiple times must agree; more
   than two distinct phone numbers across pages is flagged for review.
5. Severity rules and rationale are in [references/checks.md](references/checks.md).

## Output

JSON on stdout: `{"module": "trust", "findings": [...], "proactive": [...],
"stats": {"newest_declared_date": ..., "linked_profiles": [...]}}`.
