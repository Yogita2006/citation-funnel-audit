# Quotability checks: the question probe and structured-data rules

## Why probe questions instead of checklisting tags

A checklist ("has schema? has FAQ?") measures artifacts. The probe measures
the outcome those artifacts exist for: can a machine answer the questions
people actually ask an assistant about a brand, using only this site's
machine-readable surface? Every failed probe is by construction a real user
query the brand currently loses.

## The canonical probes

1. WHAT is this brand? Searched: homepage h1, first three paragraphs, meta
   description, Organization description. Pass: 12+ words of plain-language
   self-description. Failing this is high severity; it is the single most
   common reason assistants skip or misdescribe small brands.
2. WHAT does it cost? Searched: currency patterns in all sampled text, Offer
   or AggregateOffer schema. Only probed when the site shows commercial
   intent (pricing/shop/order/menu vocabulary or a pricing page), which keeps
   nonprofits and portfolios from being falsely flagged.
3. HOW do I contact them / WHERE are they? Searched: phone and email regex in
   text, PostalAddress and ContactPoint schema. Contact details rendered as
   images or inside JS widgets fail this probe, correctly.
4. WHO is behind it? Searched: an about-role page in the crawl, founding and
   team vocabulary anywhere in text.

Probes 2 to 4 report at medium severity with confidence medium, because
legitimate exceptions exist (quote-based pricing, form-only contact policies).
The orchestrator's judgment guide lists the overrides.

## Structured data rules

- Broken JSON-LD (F-QUOTE-001) is high severity and ranks above missing
  JSON-LD in urgency per unit effort: the site already invested in the markup
  and gets zero value from it, since parsers discard invalid blocks silently.
- No structured data at all (F-QUOTE-002): high. Recommend starting with one
  Organization block plus the page-type entity per template.
- Missing Organization anchor (F-QUOTE-003) and missing sameAs (F-QUOTE-004):
  medium; these are the identity hooks the trust gate depends on.

## Extraction shape

- One h1 per page naming the topic.
- Unique 50 to 60 character titles; the title is the citation label.
- Quotable blocks: 25 to 90 word paragraphs, each answering one question,
  ideally with a number in it. The Princeton GEO study (Aggarwal et al., KDD
  2024) measured up to 30 to 40 percent citation-visibility gains from adding
  statistics, quotations, and citations to content; the block structure is
  what lets an engine lift them.
- FAQ content with FAQPage schema is the highest-leverage proactive move:
  it publishes answers pre-shaped like assistant queries.

## New in 1.1 (site-type aware)

- F-QUOTE-005 missing the structured-data type the detected site type needs (e.g. an ecommerce site with no Product/Offer, a blog with no Article). Only fires when some schema exists but the page-type entity is absent, so it never double-counts F-QUOTE-002.
- F-QUOTE-006 local business missing address or opening hours as text or LocalBusiness schema. Only runs when the site is classified local_business. Powers "near me" and "open now" answers.
- F-QUOTE-023 weak heading hierarchy: skipped levels (h1 then h3) or a long homepage with no h2 sections. Low severity.
- F-QUOTE-030 structured price not shown to visitors: a JSON-LD price that appears nowhere in the visible text is hidden or contradicts the displayed price (the classic schema-vs-page mismatch). Medium.
- The PRICE probe (F-QUOTE-011) now uses the detected site profile's `commercial` flag instead of a keyword guess, which removes false positives on documentation and content sites.
