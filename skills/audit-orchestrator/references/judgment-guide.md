# Judgment pass: how to review script findings before reporting

The scripts assert only what a static fetch can prove, but static proof still
needs context. Review every finding against its evidence and the cached pages
before including it. False positives cost more credibility than misses.

## Common overrides

- F-RENDER-001/002 (thin homepage): a deliberately minimal brand page or a
  link-in-bio style site can be under the word threshold and still say what it
  is. If the h1 plus one sentence genuinely state what the brand does, drop the
  finding and keep only the quotability probes.
- F-QUOTE-011 (no price): consulting firms, agencies, and enterprise products
  legitimately price by quote. Downgrade to a proactive recommendation
  (publish starting-at ranges) instead of a defect when the market convention
  is quote-based.
- F-QUOTE-012 (no contact): some sites route all contact through a form by
  policy. The mechanism still holds (a form is not quotable), but downgrade to
  medium-low and phrase the fix as adding one text line of contact info.
- F-TRUST-011 (multiple phone numbers): multi-location businesses correctly
  show several numbers. Check whether the numbers are labeled per location
  before reporting; if they are, drop it.
- F-ENGAGE-004 (heavy page): if fetch time in the cache manifest is fast
  despite size, keep it as low severity; the proxy did not confirm.
- Blocked training bots only (GPTBot, ClaudeBot, Google-Extended): never a
  defect. It is a policy trade-off and stays in proactive notes.

## More false-positive scenarios (worked examples)

These are the calls that most often separate a careful audit from a noisy one.
Each names the finding, the situation, and the correct judgment.

- F-QUOTE-030 (schema price not in visible text): on many stores the price is
  rendered per variant by JavaScript, or shown inside a promotional image, while
  the JSON-LD price is correct. Before calling it a mismatch, check a product
  page: if the price simply loads client-side, this is a render-parity note
  (expose the price as text), not a contradiction. Only report a true mismatch
  when a different number is visible.
- F-QUOTE-005 (missing the schema this site type needs): a brand-new store, or a
  site on a platform that has not enabled Product schema, can still list products
  and prices in plain text. Keep the finding, but at medium — the facts are
  quotable even without schema; schema would only make them lift more cleanly.
- F-REACH-050 (login or paywall): a SaaS product legitimately gates its app at
  /app or /dashboard while its marketing, pricing, and docs pages stay open.
  Gating the product is not a visibility defect. Report this only when the wall
  sits in front of content that should be public (marketing, pricing, articles).
- F-QUOTE-006 (local business missing hours): appointment-only and always-open
  businesses may have no fixed hours. Look for "by appointment", "24/7", or
  "open 24 hours" in the text before flagging; if present, drop the hours part
  and keep only address / NAP.
- F-RENDER-013 (load-more or infinite scroll): a blog or catalogue index that
  loads older items on scroll is fine if each item has its own crawlable URL and
  appears in the sitemap. Verify the sitemap first; if items are individually
  reachable, downgrade to a low-severity note about the index page only.
- F-ENGAGE-008 (key page not linked from the homepage): the homepage nav may be
  a JavaScript mega-menu the static parser cannot expand, so a "missing" link is
  not proof of a buried page. Confirm the link truly is absent (check the raw
  HTML and the footer) before reporting; when in doubt, downgrade.
- Freshness on evergreen pages (F-TRUST-*): an About, contact, or legal page
  unchanged for years is not stale, and a footer copyright year is often a
  template. Reserve the stale-content flag for pages whose value depends on
  recency — pricing, product, and news — not for evergreen pages.
- Entity identity (legal vs brand name): a footer or schema reading "Acme
  Technologies Pvt Ltd" while the title says "Acme" is normal legal-vs-brand
  naming, not a name conflict. Flag only genuinely different names that a machine
  could not reconcile.

## Rules for your own additions

You may add findings the scripts cannot see (for example, obviously
contradictory copy, offensive auto-translated text, a hero image that renders
as broken). Every added finding must follow the same schema, must cite
concrete evidence from the cached pages, and must state the mechanism. Never
add a finding you cannot evidence from the crawl cache or an off-site probe.

## Severity discipline

Do not raise severities to make the report look thorough, and do not stack
multiple findings on one root cause. If the homepage is a JS shell, the
missing structured data on that same shell is a consequence; report the shell
as critical and note the dependency in its evidence instead of double counting.
