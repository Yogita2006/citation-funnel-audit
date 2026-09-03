# Citation Funnel Audit: example.com

Audited at 2026-09-03T05:42:34Z. 8 findings (0 critical, 2 high, 6 medium, 0 low).

Detected site type: **brochure** (low confidence). Checks are tuned to this type.

## Where the site falls out of the funnel

- `#########.`  90/100  Reach: can AI crawlers and fetchers get in?
- `#######...`  75/100  Read: does the content exist without JavaScript?
- `#####.....`  55/100  Quote: can a machine lift a clean fact?
- `########..`  80/100  Trust: is it fresh, corroborated, unambiguous?
- `#########.`  90/100  Retain: does the arriving visitor stay?

## Findings (highest impact first)

### F-QUOTE-002  [HIGH] No structured data anywhere on sampled pages

Evidence: 0 JSON-LD blocks and no microdata across 1 pages (https://example.com/).

Why it matters: Schema markup is how a machine picks the exact fact out of the page without guessing (appendix concepts A and C).

Fix (high priority): Add JSON-LD to every page: Organization (with name, url, logo, sameAs) sitewide, plus the type matching each page (Product with Offer, FAQPage, Article, LocalBusiness).

### F-RENDER-002  [HIGH] Homepage has very little machine-readable text

Evidence: Only 21 words of visible text in the raw HTML of https://example.com/.

Why it matters: A machine can only quote what it can read as text (appendix concept C).

Fix (high priority): State plainly in HTML text who the brand is, what it offers, for whom, and where. Every fact that matters must exist as text, not only inside images or video.

### F-ENGAGE-006  [MEDIUM] Homepage offers almost no paths deeper into the site

Evidence: No nav element links and fewer than 5 total links found in homepage markup.

Why it matters: A single-exit page converts an interested visitor into a bounce statistic.

Fix (medium priority): Add a simple persistent navigation covering the pages that answer buyer questions: product or services, pricing, about, contact.

### F-QUOTE-012  [MEDIUM] Probe failed: 'How do I contact them?' has no extractable answer

Evidence: No phone number, email address, or PostalAddress or ContactPoint schema found in the text of 1 sampled pages. Contact details may exist only inside images, JavaScript widgets, or forms.

Why it matters: A fact that is only in a form or an image cannot be quoted into an answer (appendix concept C).

Fix (medium priority): Publish contact details as selectable HTML text on a /contact page and mirror them in ContactPoint or LocalBusiness JSON-LD.

### F-QUOTE-013  [MEDIUM] Probe failed: 'Who is behind this brand?' has no extractable answer

Evidence: No about page was discoverable from homepage navigation or the sitemap sample, and no founding or team facts appear in sampled text.

Why it matters: Background facts drive trust in both assistants and humans; when absent, assistants fill the gap from third-party sources or say nothing.

Fix (medium priority): Add an /about page stating in plain text who runs the brand, since when, where, and what makes it different; link it from the main navigation.

### F-REACH-040  [MEDIUM] No usable XML sitemap found

Evidence: Tried https://example.com/sitemap.xml -> HTTP 404; robots.txt declares a sitemap: False.

Why it matters: Sitemaps are how crawlers find pages that navigation does not surface, and lastmod is a freshness signal.

Fix (medium priority): Publish /sitemap.xml with canonical URLs and lastmod dates, and declare it in robots.txt with a Sitemap: line.

### F-TRUST-001  [MEDIUM] No machine-readable freshness signal anywhere

Evidence: No datePublished or dateModified in structured data and no lastmod dates in the sitemap across 1 sampled pages.

Why it matters: Systems prefer sources they can prove are current; with no dates they must assume the worst or trust a fresher competitor.

Fix (medium priority): Emit dateModified in Article or WebPage JSON-LD and lastmod in the sitemap, updated by the build pipeline, so machines can see the content is maintained.

### F-TRUST-012  [MEDIUM] Site is an island: no links to any off-site brand profile

Evidence: No links to LinkedIn, Wikipedia, Wikidata, Crunchbase, GitHub or social profiles anywhere in sampled pages, and no sameAs in schema.

Why it matters: A claim that exists in exactly one place is fragile; corroboration across independent sources is what makes machines repeat it (appendix concept D).

Fix (medium priority): Link official profiles in the footer and declare them in Organization sameAs. Then keep name, description and address identical across those profiles.

## Beyond the defects: proactive improvements

- (medium) The homepage has no meta description. Add a 150 to 160 character summary stating what the brand is and for whom; assistants and search previews reuse it verbatim.
- (medium) No FAQ content or FAQPage schema found. Publishing the 10 questions customers actually ask, each answered in 2 to 4 sentences with FAQPage JSON-LD, creates ready-made citation targets shaped exactly like assistant queries.
- (low) No robots.txt found (HTTP 404). Crawlers default to full access, so nothing is blocked, but adding one with a Sitemap line gives crawlers an explicit map and an explicit welcome.
- (low) No /llms.txt. This is optional: no major AI provider has confirmed using it, so treat it as a cheap, low-risk curated index for agent tooling, not a fix for visibility problems. Prioritize the actual findings first.
- (low) No Open Graph tags on the homepage. Add og:site_name, og:title, og:description and og:image; they are read by far more systems than social networks alone and reinforce the brand entity.
