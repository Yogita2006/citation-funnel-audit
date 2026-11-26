# Citation Funnel Audit

An Agent Skill Marketplace that audits any website for the two halves of the
modern visibility problem: whether AI assistants can find, trust, and cite the
brand (discoverability), and whether the humans who click through stay
(engagement).

## The idea

Most site audits are checklists. This marketplace instead models the pipeline
a single fact on a website must survive to end up inside an AI assistant's
answer, and audits each gate of that pipeline separately:

```
REACH      can AI crawlers and fetchers get in at all?          -> reach-audit
READ       does the content exist without running JavaScript?   -> render-parity-audit
QUOTE      can a machine lift a clean, attributable fact?       -> quotability-audit
TRUST      is it fresh, corroborated, and unambiguous?          -> trust-signals-audit
RETAIN     does the human who arrives from an answer stay?      -> engagement-audit
```

A failure at any gate zeroes out everything after it, which is why the report
scores the funnel per stage: it tells the owner not just what is wrong, but
where their fact supply chain breaks first.

The quotability gate adds the marketplace's signature check, the question
probe: instead of asking "does the site have schema markup?", it asks the
questions people actually put to assistants about any brand (what is it, what
does it cost, how do I contact them, who is behind it) and tests whether each
one is answerable from the site's machine-readable surface. Every failed probe
is, by construction, a real user query the brand currently loses.

## Site-type aware

Before scoring, the orchestrator classifies the site (ecommerce, SaaS, local
business, content, documentation, portfolio, or brochure) from its schema, URL
vocabulary, and on-page language, and writes that profile into the shared crawl
cache. Every gate then reads it, so checks are conditional instead of
one-size-fits-all: a blog is never told it lacks a Product schema, the price
probe runs only on commercial sites, and a local business is checked for the
address and opening hours that "near me" answers depend on. Getting the site
type wrong is the fastest way to generate false positives, so this step runs
first and feeds all five gates.

## Design decisions and trade-offs

A frontier model, given this brief, produces a flat checklist of common SEO/GEO
issues — that is the baseline every submission shares. The decisions below are
the layer added on top of that baseline; each was a deliberate choice with a
trade-off.

- **A funnel, not a list.** Findings are organised into five ordered gates a
  fact must survive to be cited (Reach, Read, Quote, Trust, Retain), each scored
  0-100. This turns "47 issues" into "the site drops out at Read", so the owner
  fixes the one gate that unblocks the rest. Trade-off: a fact can touch two
  gates, so each finding is attributed to the gate whose failure is the true cause.
- **Site-type detection over one checklist.** The site is classified and every
  check is made conditional on its type, so the tool generalises across verticals
  instead of over-fitting to specific sites. Trade-off: a hybrid site (blog plus
  store) is scored by its dominant type; the universal checks still run, so
  nothing is skipped, only some type-specific extras.
- **Priority and mechanism over volume.** Every finding carries a severity, a
  priority, and a one-line mechanism explaining why it matters in terms of how
  crawlers and assistants behave. Ranking by impact is what separates a useful
  report from a laundry list.
- **Say less, mean more.** A dedicated judgment pass exists to drop and downgrade
  false positives (a consulting firm with no price is not broken). The tool is
  tuned to under-report rather than over-report, because a false positive costs
  more credibility than a miss.
- **Recommend, never edit.** The output is an evidence-backed recommendation
  report; the marketplace never changes a live site, and assumes a downstream
  agent would apply any fix.
- **One crawl, shared by all gates.** The site is fetched once into a shared
  snapshot that all five gates read, cutting requests roughly five-fold and
  guaranteeing every gate reasons about the same bytes.
- **Restraint over volume.** The marketplace is six focused skills on the Python
  standard library — no browser automation, no third-party packages, nothing
  bundled that a static, one-pass audit cannot use. Doing less, deliberately,
  keeps it fast, portable, and easy for an evaluator to reason about.

## Layout

```
citation-funnel-audit/
  marketplace.json               manifest: five gate skills + one entrypoint
  skills/
    audit-orchestrator/          ENTRYPOINT: crawls once, runs every gate,
      SKILL.md                   merges findings into the single report
      scripts/crawl_site.py      polite read-only crawler (shared snapshot)
      scripts/detect_profile.py  site-type detection (writes profile.json)
      scripts/run_audit.py       pipeline runner and report merger
      references/                report schema, judgment guide, off-site probe
    reach-audit/                 gate 1: robots policy per AI agent class,
      SKILL.md, scripts/, references/    HTTP health, noindex, sitemap
    render-parity-audit/         gate 2: raw-HTML vs human view, JS shells,
      SKILL.md, scripts/, references/    facts locked in images and PDFs
    quotability-audit/           gate 3: JSON-LD validation + question probe
      SKILL.md, scripts/, references/
    trust-signals-audit/         gate 4: freshness, entity identity, sameAs,
      SKILL.md, scripts/, references/    internal fact consistency
    engagement-audit/            gate 5: first-screen orientation, CTA,
      SKILL.md, scripts/, references/    viewport, weight, broken links
  README.md
```

## How the entrypoint composes the skills

1. `crawl_site.py` fetches robots.txt, the homepage, the sitemap, and up to 8
   high-value pages (about, pricing, contact, product, faq, blog) into one
   cache directory. One crawl, GET only, robots.txt honored, 0.6s politeness
   delay, hard time budget. Every gate then analyzes the same snapshot, so
   modules never disagree about what the site said and the site is fetched
   exactly once.
2. `detect_profile.py` classifies the site type from the crawled snapshot and
   writes `profile.json` into the same cache, so every gate can tune its checks
   to the kind of site it is auditing.
3. `run_audit.py` resolves the sibling skills through `marketplace.json`, runs
   each gate's check script as a subprocess, and merges: deduplicate by stable
   finding id, sort by severity then id, count by severity, score the funnel,
   and emit `audit-report.json` (plus an optional human-readable markdown
   version).
4. The agent running the skill then performs a judgment pass (documented in
   the orchestrator's references): scripts assert only what a static fetch
   proves, and the agent reviews evidence, drops false positives using the
   override list, and optionally runs the off-site corroboration probe when
   the runtime has web search.

## What each skill contributes to the report

- reach-audit: whether the site is invisible by policy or by accident. Its
  key nuance: blocking training bots (GPTBot, ClaudeBot) is a legitimate
  choice and is never reported as a defect; blocking retrieval and user-fetch
  bots (OAI-SearchBot, Claude-SearchBot, PerplexityBot, ChatGPT-User) is what
  removes a site from live AI answers. It also flags login walls and paywalls,
  which block unauthenticated AI fetchers outright.
- render-parity-audit: the JavaScript gap. A page can be complete to a human
  and empty to the fetchers that compose AI answers; the module measures the
  words a non-JS reader actually receives, and catches content that loads only
  on scroll or a click and homepages whose message is locked inside a video.
- quotability-audit: structured-data validity (broken JSON-LD is flagged above
  missing JSON-LD, since parsers discard invalid blocks silently) plus the
  question probe described above. Site-type aware: it expects the schema each
  kind of site needs, flags a structured price that disagrees with the visible
  one, and checks local-business address and hours.
- trust-signals-audit: machine-visible freshness, one canonical brand string
  across schema, Open Graph and titles, sameAs corroboration links, and
  contradictions between the site's own pages.
- engagement-audit: the first thirty seconds of an arriving visitor, flagging
  only what markup proves (orientation block, viewport tag, broken links) and
  capping proxy checks at lower severity. It also flags key pages the homepage
  fails to link, a cheap click-depth proxy.

## Report

`audit-report.json` is a superset of the required schema: `site`,
`audited_at`, `summary` counts by severity, and `findings` with `id`,
`title`, `severity`, `evidence`, `suggested_action`. Added per finding:
`confidence`, `category`, and `mechanism` (one sentence on why the problem
matters in terms of how these systems behave). Added globally: the per-stage
`funnel` scores and `proactive_recommendations`, improvements beyond detected
defects, kept separate so they never inflate the findings count.

## Running it

```
cd skills/audit-orchestrator
python3 scripts/run_audit.py example.com --out audit-report.json --markdown audit-report.md
```

Python 3.8+ standard library only; no packages to install. A typical audit
finishes in 30 to 90 seconds, well inside the 5 minute budget.

## Dashboard, local web UI and compare mode

All three run the same audit engine and need no extra packages.

```
# interactive single-file HTML dashboard
python3 scripts/run_audit.py example.com --out audit-report.json --html audit-report.html

# local web UI: type a URL in the browser (binds to 127.0.0.1 only)
python3 scripts/serve.py            # then open http://127.0.0.1:8000

# two sites side by side
python3 scripts/compare.py your-site.com competitor.com --out compare.html
```

A gate that could not be evaluated because the site was unreachable is shown
as N/A in the dashboard and counts as 0 in a comparison.

## Guardrails

Recommend-only end to end: GET requests against public pages, an identifying
user agent, robots.txt honored for the audit's own crawl, politeness delays,
bounded page counts and time budgets, and no form submission, authentication,
or site mutation anywhere.
