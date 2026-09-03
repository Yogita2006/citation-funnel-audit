# Engagement checks: what a static fetch can honestly claim

Static analysis cannot see rendered layout, animation, or real performance, so
this gate follows one discipline: flag only what the markup itself proves, cap
severity where the check is a proxy, and hand everything else to proactive
recommendations.

## The arrival model

A visitor clicking through from an AI answer or search result differs from a
browsing visitor: they arrive mid-task, with a formed question, often on
mobile, and they grant the page a few seconds to confirm "the answer is
here." Every check below maps to a way that confirmation fails.

## Checks

- F-ENGAGE-001 first-screen orientation: high. Proven by document order in
  markup: an h1 plus a 12+ word explanatory paragraph must exist near the top.
  Slogan-only heroes ("Think different. Scroll down.") fail this correctly:
  they demand the visitor do the work the page should do.
- F-ENGAGE-002 no action wording anywhere: medium, confidence medium. The
  action vocabulary list is broad (get started, book, order, contact, demo,
  quote, download, donate, and similar); a page failing it offers no next step
  in any phrasing.
- F-ENGAGE-003 missing viewport meta: high. Binary and certain; without it,
  phones render a zoomed-out desktop page, and most assistant-referred
  traffic is mobile.
- F-ENGAGE-004 heavy homepage (HTML over 1.5 MB or 70+ script tags): medium,
  a latency proxy, not a measurement. The fix says to confirm with Lighthouse.
- F-ENGAGE-005 broken internal links found during the crawl: high. Directly
  proven, and it damages both halves of the funnel: humans hit dead ends,
  crawls truncate.
- F-ENGAGE-006 under 5 links total: medium. A page with no paths deeper
  converts interest into a bounce.
- F-ENGAGE-007 3+ paragraphs over 120 words: low. Copy that cannot be scanned
  loses web readers; severity stays low because taste varies by genre.

## Proactive only (never defects)

- Navigation over 40 links: consolidation suggestion.
- Cookie consent text leading the markup: keep the layer out of the first
  content screen.
- No site search on content-rich sites: recovery path for deep-linked
  visitors who land on the wrong page.
- H1 outside the 2 to 14 word range: headline sharpening.

## The context-retention connection

Sites increasingly receive visitors whose "referrer" is a conversation. The
page cannot see that conversation, so the page itself must restate context: a
clear self-description (which the quotability gate enforces) doubles as
orientation for the human. This is why the two halves of the audit reinforce
rather than merely coexist: the same plain, factual, front-loaded writing that
makes a machine cite the page makes a human stay on it.

## New in 1.1

- F-ENGAGE-008 key pages not linked from the homepage (buried): a cheap click-depth proxy. Fires only when the homepage nav is server-rendered (>=5 crawlable links) and an important page (pricing, product, contact, about) exists but no homepage link reaches it. Medium.
