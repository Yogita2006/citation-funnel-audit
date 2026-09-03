# Trust checks: freshness, identity, consistency

## Freshness (what a machine can actually see)

Machines cannot smell staleness; they read declared dates. Sources checked, in
order of authority: datePublished and dateModified in structured data, sitemap
lastmod, footer copyright year.

- F-TRUST-001 no machine-readable date anywhere: medium. The site may be
  perfectly current, but it cannot prove it, so retrieval systems preferring
  provably fresh sources rank a dated competitor above it.
- F-TRUST-002/003 newest declared date over 18 months old: medium. The 540-day
  threshold is deliberately generous; evergreen sites update rarely and should
  not be nagged at 6 months.
- F-TRUST-004 copyright year 2+ years behind: low. Cosmetic but widely read.
- The fix is always honest: refresh the content, then the dates. A faked
  dateModified with unchanged content is detectable (diffable) and burns trust
  with the exact systems the site is courting.

## Identity and disambiguation

Entity resolution works on string and link agreement. The site controls three
identity declarations: Organization schema name, og:site_name, and the title
suffix. They must be character-identical.

- F-TRUST-010 name disagreement between signals: medium. "Acme Labs" vs
  "Acme Labs Inc." vs "acmelabs" reads as three candidate entities.
- F-TRUST-012 no off-site profile links and no sameAs: medium. An island site
  offers corroborating systems nothing to agree with. The sameAs graph
  (LinkedIn, Wikidata, Crunchbase, GitHub, social) is the machine-checkable
  claim that all those profiles are one entity.
- Name-collision risk (brand name is a common word or shared with a bigger
  entity) cannot be proven from the site alone; it is handled by the
  orchestrator's off-site probe when web search is available.

## Internal consistency

- F-TRUST-011 more than two distinct phone numbers across pages: medium,
  confidence medium. Multi-location businesses are the legitimate exception;
  the judgment guide says to check labeling before reporting. The underlying
  rule generalizes: any hard fact (address, hours, founding year) stated
  differently in two places on the same site teaches machines to distrust both.

## Authorship

Author markup on articles is a proactive recommendation, not a defect:
unattributed content is common and survivable, but attributed content with
Person schema and credentials is weighted better by systems that model source
quality, and it humanizes the brand for the visitors who check.
