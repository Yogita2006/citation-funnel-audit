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
