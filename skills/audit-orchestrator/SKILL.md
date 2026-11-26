---
name: audit-orchestrator
description: Entrypoint skill of the Citation Funnel marketplace. Given a website URL or domain, runs one polite read-only crawl, detects the site type so gate checks are conditional, executes the five gate audits (reach, render parity, quotability, trust signals, engagement) from the sibling skills, and merges their outputs into a single evidence-backed audit report with severities, prioritized fixes, and proactive recommendations. Use when asked to audit a website or brand for AI discoverability, AI visibility, why AI assistants do not cite it, or why visitors bounce.
license: MIT
compatibility: Requires Python 3.8+ and outbound HTTPS access. No third-party packages.
allowed-tools: Bash(python3:*) Read
---

# Citation Funnel Audit (entrypoint)

Audits a website through the pipeline a fact must survive to be cited by an AI
assistant and to keep the visitor who arrives:

Reach (crawler can get in) -> Read (content exists without JavaScript) ->
Quote (a clean fact can be extracted) -> Trust (fresh, corroborated,
unambiguous) -> Retain (the human who clicks through stays).

Each gate is a sibling skill in this marketplace. This skill composes them and
emits the one final report.

## Design principles

- Generalizes across verticals. Every check encodes a general best practice and
  is conditioned on the detected site type (ecommerce, SaaS, local business,
  content, documentation, portfolio, brochure), never tuned to specific URLs, so
  it holds on unseen sites in any industry.
- Priority over volume. Findings are ranked by severity and real-world impact so
  the change that moves brand visibility most is first, not a flat laundry list.
- Recommend, never edit. The output is an evidence-backed recommendation report;
  the marketplace never alters a live site.
- Portable and lightweight. Pure Python standard library, no third-party
  packages, and provider-agnostic: no dependence on any specific model, API, or
  hosted tool.

## When to use

The user asks to audit a website or brand for AI discoverability or visibility,
asks why AI assistants ignore or misrepresent a brand, or why visitors who
arrive do not engage.

## Inputs

- Required: a URL or bare domain, e.g. `example.com`.
- Optional: `--max-pages N` (default 8), an output path.

## Procedure

1. Run the full pipeline with one command from this skill's directory:

   ```
   python3 scripts/run_audit.py <url> --out audit-report.json --markdown audit-report.md
   ```

   The script crawls once into a shared cache (robots.txt honored, GET only,
   0.6s delay, hard time budget), then runs `detect_profile.py` to classify the
   site type (ecommerce, SaaS, local business, content, documentation,
   portfolio, brochure) and write `profile.json` into that cache so every gate
   can make its checks conditional. It then locates the sibling skills through
   `marketplace.json`, runs each gate's check script against the same cached
   snapshot, deduplicates, sorts by severity then id, and writes the report
   (which includes the detected `site_profile`). Typical runtime is under 60
   seconds.

2. Read `audit-report.json` and verify it is well formed: `site`, `audited_at`,
   a `summary` with counts by severity, and `findings` where every finding has
   `id`, `title`, `severity`, `evidence`, `suggested_action`.

3. Judgment pass (you, the agent): scripts only assert what a static fetch can
   prove, so review each finding's evidence and drop or downgrade anything the
   page context contradicts. False positives cost more than misses. Typical
   overrides are listed in [references/judgment-guide.md](references/judgment-guide.md).

4. Optional enrichment, only if the runtime offers web search: follow
   [references/offsite-probe.md](references/offsite-probe.md) to check how the
   brand is described off site and whether its name is ambiguous. Append any
   confirmed issues as findings with ids `F-OFFSITE-...`. Skip silently if no
   search tool exists; the report is complete without it.

5. Present the result: lead with the funnel table (where the site drops out),
   then findings ordered by severity and priority (highest-impact first) with
   evidence and fix, then the proactive recommendations. The JSON report is the contract; the markdown file is the
   readable version for a non-expert.

## Output

`audit-report.json` following [references/report-schema.md](references/report-schema.md).
It is a superset of the contest's required schema: each finding adds
`confidence`, `category` and `mechanism` (why the problem matters, tied to how
crawlers and assistants actually work), plus a `funnel` section with a 0 to 100
score per gate and a `proactive_recommendations` list for improvements beyond
detected defects.

## Guardrails

Recommend-only. Every step is a read-only GET against public pages. Never
submit forms, authenticate, or attempt to change the site. Respect robots.txt
for the audit's own crawl. If a site blocks the auditor itself, report that as
the finding rather than working around it.
