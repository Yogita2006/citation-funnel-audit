# Render parity checks: thresholds and rationale

The module answers one question per page: if a machine fetches this URL and
does not execute JavaScript, how much of the human-visible substance does it
receive?

## Thresholds

- Homepage shell (F-RENDER-001): app root element (`#root`, `#app`, `#__next`,
  `#___gatsby` and friends) AND under 150 words of visible text. Both
  conditions required; the root element alone is not evidence, since many SSR
  frameworks keep the mount div while shipping full HTML.
- Mitigation: if a serialized state blob (`__NEXT_DATA__`, `window.__NUXT__`,
  `__INITIAL_STATE__`, RSC payload) is present, severity drops one level.
  Some pipelines mine those blobs, but treating that as reliable would be
  optimistic; the fix recommendation stays the same (real SSR or prerender).
- Thin homepage without shell (F-RENDER-002): under 120 words. Conservative on
  purpose; brochure minimalism with a real value sentence passes.
- Thin interior pages (F-RENDER-003): reported only when at least two key
  pages are under 120 words AND the homepage itself is healthy, so one root
  cause is not double counted.
- Alt text (F-RENDER-010): flagged when 5+ images sampled and over half lack
  alt. Below that sample size the signal is noise.
- PDF-locked facts (F-RENDER-011): only PDF links whose filename or anchor
  text matches menu, price, brochure, catalog, spec, rate. A whitepaper PDF is
  fine; a menu that exists only as PDF is the classic lost-fact case.
- Iframe content (F-RENDER-012): non-media iframes on a page that is also
  text-thin. Media embeds (video, maps, captcha, tag managers) are excluded.

## Reproducing the evidence

Every finding's numbers can be reproduced with:

```
curl -sL <url> | python3 -c "import sys,re,html; t=sys.stdin.read(); \
t=re.sub(r'(?s)<(script|style|template|noscript)[^>]*>.*?</\\1>','',t); \
print(len(html.unescape(re.sub(r'<[^>]+>',' ',t)).split()))"
```

That one-liner is what "words of visible text" means in the evidence strings.

## Why this gate matters

Answer-engine fetchers (the agents that grab pages while composing an AI
answer) read the HTTP response body. Rendering JavaScript at answer time is
expensive and rare. Search crawlers render more, but on a delay and budget.
The safe model, and the one this audit assumes, is: what is not in the initial
HTML does not exist for citation purposes.

## New in 1.1

- F-RENDER-013 content behind scroll or a click: medium. Load-more / infinite-scroll markup means items past the first batch are fetched by JS on interaction and never appear in a single crawl fetch. Fix is crawlable pagination.
- F-RENDER-014 homepage substance locked in a video: medium. A video embed on a text-thin homepage (<150 words) means the core message may be spoken, not written; a transcript makes it readable.
