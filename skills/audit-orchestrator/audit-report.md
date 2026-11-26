# Citation Funnel Audit: python.org

Audited at 2026-11-26T17:01:38Z. 4 findings (0 critical, 0 high, 4 medium, 0 low).

Detected site type: **content** (medium confidence). Checks are tuned to this type.

## Where the site falls out of the funnel

- `#########.`  90/100  Reach: can AI crawlers and fetchers get in?
- `##########` 100/100  Read: does the content exist without JavaScript?
- `########..`  80/100  Quote: can a machine lift a clean fact?
- `#########.`  90/100  Trust: is it fresh, corroborated, unambiguous?
- `##########` 100/100  Retain: does the arriving visitor stay?

## Findings (highest impact first)

### F-QUOTE-003 — No Organization or LocalBusiness entity declared

**Severity:** Medium

**Evidence:** JSON-LD types found: ['SearchAction', 'WebSite']. None establishes who the brand itself is.

**Why it matters:** The Organization entity is the anchor that ties every fact and page to one unambiguous brand identity (appendix concept D).

**Fix (priority medium):** Add one Organization (or LocalBusiness) JSON-LD block on the homepage with name, url, logo, description and sameAs links to official profiles.

### F-QUOTE-005 — Missing the structured-data type a content site needs

**Severity:** Medium

**Evidence:** Detected site type is content, but no matching schema was found (present: ['SearchAction', 'WebSite']).

**Why it matters:** Generic Organization schema names the brand but not its articles and authors; the page-type entity is what a machine lifts to answer questions about this kind of site.

**Fix (priority medium):** Add Article or BlogPosting with author and datePublished to the relevant pages, alongside the sitewide Organization block.

### F-REACH-040 — No usable XML sitemap found

**Severity:** Medium

**Evidence:** Tried https://python.org/sitemap.xml -> HTTP 404; robots.txt declares a sitemap: False.

**Why it matters:** Sitemaps are how crawlers find pages that navigation does not surface, and lastmod is a freshness signal.

**Fix (priority medium):** Publish /sitemap.xml with canonical URLs and lastmod dates, and declare it in robots.txt with a Sitemap: line.

### F-TRUST-001 — No machine-readable freshness signal anywhere

**Severity:** Medium

**Evidence:** No datePublished or dateModified in structured data and no lastmod dates in the sitemap across 9 sampled pages.

**Why it matters:** Systems prefer sources they can prove are current; with no dates they must assume the worst or trust a fresher competitor.

**Fix (priority medium):** Emit dateModified in Article or WebPage JSON-LD and lastmod in the sitemap, updated by the build pipeline, so machines can see the content is maintained.

## Beyond the defects: proactive improvements

- (medium) Blog or news pages carry no author markup. Add visible bylines plus Person schema with author credentials; attributed content is weighted as more trustworthy by retrieval systems.
- (low) Navigation exposes 64 links. Consider collapsing to 5 to 7 top-level choices; oversized menus measurably slow orientation.
- (low) No /llms.txt. This is optional: no major AI provider has confirmed using it, so treat it as a cheap, low-risk curated index for agent tooling, not a fix for visibility problems. Prioritize the actual findings first.
