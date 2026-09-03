---
name: reach-audit
description: Reach gate of the Citation Funnel audit. Checks whether AI crawlers and answer-engine fetchers can get into a website at all, including robots.txt policy per AI agent category (training vs retrieval vs user-fetch bots), HTTP health, noindex directives, redirect hygiene, canonicals, and sitemap availability, and login walls or paywalls that gate the main content from unauthenticated fetchers. Use when diagnosing why a site is entirely absent from AI assistants and search, or as the first gate of a full discoverability audit.
license: MIT
compatibility: Requires Python 3.8+. Reads a crawl cache produced by the audit-orchestrator skill.
allowed-tools: Bash(python3:*) Read
---

# Reach Audit

If the crawler is not let in, nothing else about the site matters. This skill
proves or rules out access-level causes of AI invisibility.

## When to use

As the first gate of the Citation Funnel audit, or standalone when a brand is
completely absent from AI answers and search results.

## Inputs

A crawl cache directory containing `manifest.json`, produced by
`audit-orchestrator/scripts/crawl_site.py`.

## Procedure

1. Run `python3 scripts/check_reach.py --cache <cache-dir>`.
2. The script checks, in order: homepage fetchability and status, robots.txt
   health (a 5xx robots.txt is treated by several crawlers as a full disallow),
   blanket `Disallow: /`, explicit blocks of AI retrieval and user-fetch agents
   (which remove the site from live AI answers) versus training-only agents
   (a legitimate policy choice, reported as informational), noindex via meta
   tag or X-Robots-Tag, redirect chain length, conflicting canonicals, and
   sitemap availability.
3. Review the JSON findings against the evidence. The distinction that
   prevents false positives here: blocking GPTBot or ClaudeBot alone is not a
   defect; blocking OAI-SearchBot, Claude-SearchBot, PerplexityBot, or the
   user-fetch agents is. The agent lists and severity rules are in
   [references/checks.md](references/checks.md).

## Output

JSON on stdout: `{"module": "reach", "findings": [...], "proactive": [...],
"stats": {...}}`. Each finding carries id, title, severity, confidence,
mechanism, evidence, and a suggested_action with priority.
