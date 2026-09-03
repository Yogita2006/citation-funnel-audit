# Reach checks: agents, rules, and severities

## AI crawler user agents by function (2026)

Blocking different agents has different consequences. The script encodes this
taxonomy; keep it current as vendors add agents.

- Retrieval and answer indexing (blocking removes the site from live AI
  answers): OAI-SearchBot, Claude-SearchBot, PerplexityBot, Amazonbot.
- User-triggered fetch (blocking breaks "look at this site" requests):
  ChatGPT-User, Claude-User, Perplexity-User, MistralAI-User.
- Training corpus collection (blocking is a legitimate content-control choice;
  trade-off is long-term model familiarity with the brand): GPTBot, ClaudeBot,
  anthropic-ai, Google-Extended, Applebot-Extended, CCBot, Meta-ExternalAgent,
  Bytespider.

## Checks and severity rationale

- F-REACH-001/002 homepage unreachable or non-200: critical. Nothing
  downstream can compensate.
- F-REACH-010 robots.txt 5xx: high. Googlebot and others treat a robots.txt
  server error as "assume disallowed" and throttle or stop crawling.
- F-REACH-011 `Disallow: /` for `*`: critical. Locks out every compliant
  crawler including all AI agents.
- F-REACH-012 explicit blocks of retrieval or user-fetch agents: high. The
  most common self-inflicted wound: sites copied anti-AI robots.txt templates
  in 2023-2024 and never revisited them after AI answers became a traffic
  source.
- F-REACH-020 noindex: critical on the homepage, high elsewhere. The most
  common root cause is a staging flag that shipped to production.
- F-REACH-030 redirect chains over 2 hops: medium. Answer-engine fetchers run
  on tight timeouts; each hop adds latency and failure surface.
- F-REACH-031 conflicting canonicals: medium. Splits identity signals across
  URLs.
- F-REACH-040 no sitemap: medium. Not fatal for small sites, but sitemaps are
  the only reliable discovery path for pages weak in internal linking, and
  lastmod is a freshness input.

## Deliberately not defects

- Missing llms.txt: proactive note only. As of 2026 no major provider has
  confirmed consuming it in production, and Google explicitly says it is not
  used for its AI features. Recommending it as a fix would be
  mechanism-unsound; it is offered as an optional, cheap curated index.
- Blocking training-only bots: proactive note only, as above.
- Missing robots.txt entirely: crawlers default to full access; suggest adding
  one for the Sitemap line, nothing more.

## New in 1.1

- F-REACH-050 login wall or paywall gating main content: high on key pages, else medium. Detected from gating phrases ("subscribe to continue reading", "members only") or `isAccessibleForFree:false`. Unauthenticated fetchers cannot pass it, so the content is unreadable and uncitable. A plain "Log in" nav link alone does not trigger it.
