# Audit report schema

The JSON report is the contract. It is a strict superset of the contest's
required floor: every required field is present, plus fields that make the
report actionable and auditable.

```json
{
  "site": "example.com",
  "audited_at": "2026-09-20T14:32:00Z",
  "summary": {
    "total_findings": 6,
    "critical": 1,
    "high": 2,
    "medium": 2,
    "low": 1
  },
  "funnel": [
    {"stage": "reach", "question": "Reach: can AI crawlers and fetchers get in?", "score": 100, "findings": 0},
    {"stage": "render", "question": "Read: does the content exist without JavaScript?", "score": 55, "findings": 1}
  ],
  "findings": [
    {
      "id": "F-RENDER-001",
      "title": "Homepage is a JavaScript shell with almost no crawlable text",
      "severity": "critical",
      "confidence": "high",
      "category": "render",
      "mechanism": "Assistants build answers from what a simple fetch returns; content assembled only after page load is invisible to them.",
      "evidence": "Raw HTML of https://example.com/ contains only 23 words of visible text outside scripts.",
      "suggested_action": {
        "summary": "Server-render or statically prerender every public page so the complete text arrives in the initial HTML response.",
        "priority": "critical"
      }
    }
  ],
  "proactive_recommendations": [
    {"id": "P-QUOTE-002", "summary": "Publish the 10 questions customers actually ask, each answered in 2 to 4 sentences with FAQPage JSON-LD.", "priority": "medium"}
  ],
  "audit_meta": {
    "marketplace": "citation-funnel-audit/1.0.0",
    "pages_crawled": 9,
    "module_stats": {},
    "elapsed_seconds": 42.0,
    "read_only": true
  }
}
```

## Field rules

- `severity` is one of critical, high, medium, low. Meaning:
  - critical: this alone can make the site invisible to AI systems (blanket
    robots disallow, noindex on the homepage, non-200 homepage, empty JS shell).
  - high: a major loss of citations or visitors, but not total (retrieval bots
    blocked, no structured data at all, broken JSON-LD, key pages empty to
    machines, broken internal links, no mobile viewport).
  - medium: measurable drag (missing sitemap, failed question probes, entity
    inconsistency, staleness, missing CTA).
  - low: worth fixing, small individual effect (stale copyright year, walls of
    text, weak chunking).
- `confidence` is high or medium. Medium means the check is heuristic; the
  agent's judgment pass and the reader should weigh it accordingly.
- `mechanism` states in one sentence why the problem matters in terms of how
  crawlers and assistants behave. Never omit it; it is what makes the report
  educational rather than a scold list.
- `evidence` must contain the measured numbers and the URLs involved, so a
  developer can reproduce the observation with curl.
- `funnel[].score` is 100 minus severity weights (critical 45, high 25,
  medium 10, low 4), floored at 0. It exists to show where the site drops out
  of the pipeline, not as a marketing grade.
- `proactive_recommendations` are improvements not tied to a detected defect.
  They never inflate the findings count.
- Findings are ordered by severity, then by id. Ids are stable check
  identifiers, so two runs on the same snapshot produce the same report.
