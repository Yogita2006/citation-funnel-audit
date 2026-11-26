#!/usr/bin/env python3
"""Quote gate: can a machine lift a clean, attributable fact off the page?

Two instruments:
1. Structured data: extract and validate every JSON-LD block (broken JSON-LD
   is worse than none), check the types that matter for a brand.
2. Question probe: the questions people actually ask assistants about any
   brand (what is it, what does it cost, where is it, how do I contact it,
   who is it for) are tested against the site's machine-readable text. Every
   unanswerable probe is a finding with the search space as evidence.

Reads the crawl cache and prints findings as JSON.
"""

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser

SEV_PRIORITY = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}


def finding(fid, title, severity, evidence, action, mechanism, confidence="high"):
    return {
        "id": fid, "title": title, "severity": severity, "confidence": confidence,
        "category": "quotability", "mechanism": mechanism, "evidence": evidence,
        "suggested_action": {"summary": action, "priority": SEV_PRIORITY[severity]},
    }


class Extractor(HTMLParser):
    SKIP = {"style", "template", "svg", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.metas = {}
        self.headings = []          # (level, text)
        self.paragraphs = []
        self.jsonld_raw = []
        self.has_microdata = False
        self._mode = []             # tag context stack
        self._buf = None
        self._in_title = False
        self._in_script = None      # None | "jsonld" | "js"

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "itemscope" in a or any(k == "itemprop" for k, _v in attrs):
            self.has_microdata = True
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name:
                self.metas[name] = a.get("content", "")
        elif tag == "script":
            t = (a.get("type") or "").lower()
            self._in_script = "jsonld" if "ld+json" in t else "js"
            if self._in_script == "jsonld":
                self.jsonld_raw.append("")
        elif tag in ("h1", "h2", "h3", "h4", "p", "li"):
            self._mode.append(tag)
            self._buf = []
        elif tag in self.SKIP:
            self._mode.append("skip")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._in_script = None
        elif self._mode and (self._mode[-1] == tag or self._mode[-1] == "skip"):
            mode = self._mode.pop()
            if self._buf is not None and mode in ("h1", "h2", "h3", "h4", "p", "li"):
                text = re.sub(r"\s+", " ", " ".join(self._buf)).strip()
                if text:
                    if mode.startswith("h"):
                        self.headings.append((mode, text))
                    else:
                        self.paragraphs.append(text)
            self._buf = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_script == "jsonld":
            self.jsonld_raw[-1] += data
        elif self._in_script is None and self._buf is not None and "skip" not in self._mode:
            self._buf.append(data)


def parse(html):
    e = Extractor()
    try:
        e.feed(html)
    except Exception:
        pass
    return e


def load_pages(cache):
    with open(os.path.join(cache, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    pages = []
    for rec in manifest.get("pages", []):
        if not rec.get("file"):
            continue
        path = os.path.join(cache, rec["file"])
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                html = f.read()
            if rec.get("status") == 200 and html:
                pages.append((rec, parse(html)))
    return manifest, pages


def flatten_jsonld(node, out):
    if isinstance(node, dict):
        if "@type" in node:
            out.append(node)
        for v in node.values():
            flatten_jsonld(v, out)
    elif isinstance(node, list):
        for v in node:
            flatten_jsonld(v, out)


def load_profile(cache):
    """Read the site profile written by detect_profile.py, if present."""
    p = os.path.join(cache, "profile.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


# Phone matches require a phone-ish keyword nearby so dates, prices, and code
# samples never count as contact details.
PHONE_RE = re.compile(r"(?:phone|call us|call|tel|fax)\W{0,15}\+?\d[\d ().-]{7,}\d", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PRICE_RE = re.compile(r"(?:[$€£₹]\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:USD|EUR|INR|GBP)\b|\bfree\b.{0,20}\bplan\b)", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    args = ap.parse_args()
    manifest, pages = load_pages(args.cache)
    profile = load_profile(args.cache)
    findings, proactive = [], []
    if not pages:
        print(json.dumps({"module": "quotability", "findings": [], "proactive": [],
                          "stats": {"note": "no fetchable pages in cache"}}))
        return 0

    site = manifest.get("site", "")
    all_text = " ".join(p for _r, e in pages for p in ([e.title] + e.paragraphs + [t for _l, t in e.headings]))
    urls_checked = [r["final_url"] for r, _e in pages]

    # 1. JSON-LD extraction and validation across all pages.
    entities, broken = [], []
    for rec, e in pages:
        for raw in e.jsonld_raw:
            raw = raw.strip()
            if not raw:
                continue
            try:
                flatten_jsonld(json.loads(raw), entities)
            except ValueError as err:
                broken.append((rec["final_url"], str(err)[:80]))
    types = {str(ent.get("@type")) for ent in entities}

    if broken:
        findings.append(finding(
            "F-QUOTE-001", "Invalid JSON-LD blocks that parsers silently discard", "high",
            "%d JSON-LD block(s) fail to parse, e.g. on %s (%s). Invalid blocks are dropped whole, so the markup might as well not exist." % (
                len(broken), broken[0][0], broken[0][1]),
            "Fix the JSON syntax (validate with schema.org validator or 'python3 -m json.tool') and add a JSON-LD lint step to the site build.",
            "Structured data is the highest-precision channel for facts; a syntax error silently zeroes it."))
    has_structured = bool(entities) or any(e.has_microdata for _r, e in pages)
    if not has_structured and not broken:
        findings.append(finding(
            "F-QUOTE-002", "No structured data anywhere on sampled pages", "high",
            "0 JSON-LD blocks and no microdata across %d pages (%s)." % (len(pages), ", ".join(urls_checked[:4])),
            "Add JSON-LD to every page: Organization (with name, url, logo, sameAs) sitewide, plus the type matching each page (Product with Offer, FAQPage, Article, LocalBusiness).",
            "Schema markup is how a machine picks the exact fact out of the page without guessing (appendix concepts A and C)."))
    elif has_structured:
        if not any("Organization" in t or "LocalBusiness" in t for t in types):
            findings.append(finding(
                "F-QUOTE-003", "No Organization or LocalBusiness entity declared", "medium",
                "JSON-LD types found: %s. None establishes who the brand itself is." % (sorted(types) or ["none"]),
                "Add one Organization (or LocalBusiness) JSON-LD block on the homepage with name, url, logo, description and sameAs links to official profiles.",
                "The Organization entity is the anchor that ties every fact and page to one unambiguous brand identity (appendix concept D)."))
        org = next((ent for ent in entities if "Organization" in str(ent.get("@type")) or "LocalBusiness" in str(ent.get("@type"))), None)
        if org and not org.get("sameAs"):
            findings.append(finding(
                "F-QUOTE-004", "Organization schema has no sameAs links", "medium",
                "The Organization block on the site declares no sameAs profiles.",
                "Add sameAs URLs for official LinkedIn, Wikipedia or Wikidata, Crunchbase and social profiles to the Organization JSON-LD.",
                "sameAs is the machine-readable proof that this site and those profiles are the same entity, which resolves name collisions (appendix concept D)."))

        # Site-type-appropriate schema: schema exists, but not the page-type
        # entity this kind of site is quoted for (only meaningful with a profile).
        type_schema = {
            "ecommerce": ({"product", "offer", "aggregateoffer"}, "Product with an Offer (price, priceCurrency, availability)"),
            "saas": ({"softwareapplication", "webapplication", "service", "offer", "product"}, "SoftwareApplication (or Service) plus Offer for pricing"),
            "content": ({"article", "blogposting", "newsarticle"}, "Article or BlogPosting with author and datePublished"),
            "documentation": ({"techarticle", "howto", "faqpage"}, "TechArticle or HowTo"),
        }
        stype = profile.get("type")
        if stype in type_schema:
            wanted, human = type_schema[stype]
            if not ({t.lower() for t in types} & wanted):
                findings.append(finding(
                    "F-QUOTE-005", "Missing the structured-data type a %s site needs" % stype, "medium",
                    "Detected site type is %s, but no matching schema was found (present: %s)." % (stype, sorted(types) or ["none"]),
                    "Add %s to the relevant pages, alongside the sitewide Organization block." % human,
                    "Generic Organization schema names the brand but not its %s; the page-type entity is what a machine lifts to answer questions about this kind of site." % (
                        "products and offers" if stype in ("ecommerce", "saas") else "articles and authors"),
                    confidence="medium"))

    # 1b. Local businesses have type-specific must-haves: address and hours.
    if profile.get("type") == "local_business":
        has_address = any("PostalAddress" in json.dumps(ent, default=str) for ent in entities) or (
            bool(re.search(r"\b\d{5,6}\b", all_text)) and
            bool(re.search(r"street|road|avenue|\blane\b|nagar|sector|suite|floor|building", all_text, re.I)))
        has_hours = any("OpeningHours" in json.dumps(ent, default=str) for ent in entities) or \
            bool(re.search(r"opening hours|hours\s*[:]|mon(day)?\W.{0,20}(am|pm|clos)|open\b.{0,15}\bclos", all_text, re.I))
        if not has_address or not has_hours:
            missing = " and ".join(x for x, ok in [("street address", has_address), ("opening hours", has_hours)] if not ok)
            findings.append(finding(
                "F-QUOTE-006", "Local business is missing %s as machine-readable data" % missing, "medium",
                "This looks like a local business, but %s could not be extracted from text or LocalBusiness schema across %d pages." % (missing, len(pages)),
                "Publish full NAP (name, address, phone) and opening hours as HTML text and in LocalBusiness JSON-LD (PostalAddress + OpeningHoursSpecification); keep them identical to your Google Business Profile.",
                "'Near me', 'open now' and 'where is' queries are answered from address and hours; without them a local business loses exactly the questions it most needs to win.",
                confidence="medium"))

    # 2. Question probe: is each canonical brand question answerable from text?
    home_e = next((e for r, e in pages if r["role"] == "home"), pages[0][1])
    roles = {r["role"] for r, _e in pages}

    # WHAT: does the homepage state what the brand is in plain text?
    h1_text = " ".join(t for l, t in home_e.headings if l == "h1")
    meta_desc = home_e.metas.get("description", "")
    first_paras = " ".join(home_e.paragraphs[:3])
    what_material = (h1_text + " " + meta_desc + " " + first_paras).strip()
    if len(what_material.split()) < 12:
        findings.append(finding(
            "F-QUOTE-010", "Probe failed: 'What is %s?' has no extractable answer" % site, "high",
            "Homepage h1 plus meta description plus first paragraphs total %d words; nothing states what the brand does in one quotable sentence." % len(what_material.split()),
            "Put a one-sentence plain-language definition of the brand (what it is, for whom, where) in the h1 or first paragraph and mirror it in the meta description and Organization description.",
            "Assistants quote the clearest self-description they can extract; if none exists they skip the brand or guess (appendix concept B)."))

    # PRICE: only probe when the site is commercial in nature. Prefer the
    # detected site type; fall back to a vocabulary heuristic when absent.
    if profile.get("type"):
        commercial = bool(profile.get("commercial"))
    else:
        commercial = bool(re.search(r"pricing|buy|order|shop|plan|subscribe|book now|add to cart|menu", all_text, re.I)) or "pricing" in roles
    if commercial:
        price_found = bool(PRICE_RE.search(all_text)) or any("Offer" in str(t) for t in types)
        if not price_found:
            findings.append(finding(
                "F-QUOTE-011", "Probe failed: 'What does it cost?' has no extractable answer", "medium",
                "No currency amounts in text and no Offer schema across %d sampled pages, although the site sells or takes orders." % len(pages),
                "Publish at least indicative prices as HTML text and Offer or AggregateOffer JSON-LD; if prices vary, state ranges or starting-at values.",
                "Price is a top assistant query; sites that state it get quoted, sites that hide it behind 'contact us' get omitted.",
                confidence="medium"))

    # CONTACT and WHERE: phone, email, or address reachable as text or markup.
    raw_all = ""
    for rec in manifest.get("pages", []):
        if rec.get("file"):
            path = os.path.join(args.cache, rec["file"])
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    raw_all += f.read()
    contact_found = bool(PHONE_RE.search(all_text) or EMAIL_RE.search(all_text)) \
        or bool(re.search(r"href=[\"'](tel|mailto):", raw_all, re.I)) \
        or any("PostalAddress" in json.dumps(ent, default=str) for ent in entities) \
        or any("ContactPoint" in str(ent.get("@type")) for ent in entities)
    if not contact_found:
        findings.append(finding(
            "F-QUOTE-012", "Probe failed: 'How do I contact them?' has no extractable answer", "medium",
            "No phone number, email address, or PostalAddress or ContactPoint schema found in the text of %d sampled pages. Contact details may exist only inside images, JavaScript widgets, or forms." % len(pages),
            "Publish contact details as selectable HTML text on a /contact page and mirror them in ContactPoint or LocalBusiness JSON-LD.",
            "A fact that is only in a form or an image cannot be quoted into an answer (appendix concept C).",
            confidence="medium"))

    # WHO: an about page or organization story reachable from the crawl.
    if "about" not in roles and not re.search(r"\babout us\b|\bour story\b|\bfounded\b", all_text, re.I):
        findings.append(finding(
            "F-QUOTE-013", "Probe failed: 'Who is behind this brand?' has no extractable answer", "medium",
            "No about page was discoverable from homepage navigation or the sitemap sample, and no founding or team facts appear in sampled text.",
            "Add an /about page stating in plain text who runs the brand, since when, where, and what makes it different; link it from the main navigation.",
            "Background facts drive trust in both assistants and humans; when absent, assistants fill the gap from third-party sources or say nothing.",
            confidence="medium"))

    # 2b. Structured price must also be visible to humans: a schema price that
    # appears nowhere in the page text is hidden or contradicts the shown price.
    schema_prices = []
    for ent in entities:
        for key in ("price", "lowPrice", "highPrice"):
            v = ent.get(key)
            if isinstance(v, (str, int, float)):
                digits = re.sub(r"[^\d]", "", str(v))
                if len(digits) >= 2:
                    schema_prices.append((str(v), digits))
    if schema_prices:
        text_digits = re.sub(r"[^\d]", " ", all_text)
        shown = [p for p, d in schema_prices if re.search(r"(?<!\d)%s(?!\d)" % re.escape(d), text_digits)]
        if not shown:
            listed = ", ".join(sorted({p for p, _d in schema_prices}))
            findings.append(finding(
                "F-QUOTE-030", "Structured-data price is not shown to visitors", "medium",
                "JSON-LD declares price(s) %s, but none of those amounts appear in the visible page text. Either the price is image/JS-only, or the schema price disagrees with the displayed price." % listed[:120],
                "Make the JSON-LD Offer price identical to the price shown as HTML text on the page; never let the two drift apart.",
                "Assistants may quote the schema price while a human sees a different number; a visible/structured mismatch misprices you in answers and burns trust.",
                confidence="medium"))

    # 3. Quotable-block density and heading hygiene.
    h1_count = sum(1 for l, _t in home_e.headings if l == "h1")
    if h1_count == 0:
        findings.append(finding(
            "F-QUOTE-020", "Homepage has no h1 heading", "medium",
            "0 h1 elements found in homepage HTML.",
            "Give every page exactly one h1 that names the page topic in plain language.",
            "The h1 is the strongest single hint about what a page answers; extractors weight it heavily."))
    # Heading hierarchy: skipped levels, or no sub-structure on a long page.
    levels_seq = [l for l, _t in home_e.headings]
    home_body_words = len(" ".join(home_e.paragraphs).split())
    if h1_count >= 1:
        has_h2 = "h2" in levels_seq
        jumped, seen_h2 = False, False
        for l in levels_seq:
            if l == "h2":
                seen_h2 = True
            elif l in ("h3", "h4") and not seen_h2:
                jumped = True
                break
        if jumped or (not has_h2 and home_body_words > 250):
            findings.append(finding(
                "F-QUOTE-023", "Weak heading hierarchy on the homepage", "low",
                "Heading levels in document order: %s. %s" % (
                    levels_seq or ["none"],
                    "Sub-headings jump past h2." if jumped else "A content-rich page uses only an h1 with no h2 sections."),
                "Structure each page as one h1 then h2 (and h3) sections in order with no skipped levels; each section heading should name the question it answers.",
                "Heading order is how machines segment a page into extractable topic blocks; a flat or skipped hierarchy blurs where one answer ends and the next begins.",
                confidence="medium"))
    quotable = [p for _r, e in pages for p in e.paragraphs if 25 <= len(p.split()) <= 90]
    if len(quotable) < 3 and len(all_text.split()) > 300:
        findings.append(finding(
            "F-QUOTE-021", "Text is not chunked into quotable answers", "low",
            "Only %d paragraphs of 25 to 90 words across sampled pages; content is fragmented into slogans or fused into walls of text." % len(quotable),
            "Restructure key pages into heading-plus-short-paragraph blocks where each block answers one question in 2 to 4 sentences, with concrete numbers where possible.",
            "Answer engines lift self-contained passages; research on generative engines shows passages with statistics and clear claims are cited far more often.",
            confidence="medium"))

    # 4. Title and meta description hygiene.
    titles = [(r["final_url"], (e.title or "").strip()) for r, e in pages]
    empty_titles = [u for u, t in titles if not t]
    dupe = len({t for _u, t in titles if t}) < len([t for _u, t in titles if t])
    if empty_titles or dupe:
        findings.append(finding(
            "F-QUOTE-022", "Missing or duplicated page titles", "medium",
            "Pages without a title: %s. Duplicated titles across different pages: %s." % (empty_titles[:3] or "none", dupe),
            "Give every page a unique title of roughly 50 to 60 characters naming the brand and the page topic.",
            "The title is the first fact retrieval systems read and the label under which the page is cited."))
    if not meta_desc:
        proactive.append({
            "id": "P-QUOTE-001",
            "summary": "The homepage has no meta description. Add a 150 to 160 character summary stating what the brand is and for whom; assistants and search previews reuse it verbatim.",
            "priority": "medium"})
    if not any("FAQPage" in str(t) for t in types) and not any(
            t.endswith("?") for _l, t in [h for _r, e in pages for h in e.headings]):
        proactive.append({
            "id": "P-QUOTE-002",
            "summary": "No FAQ content or FAQPage schema found. Publishing the 10 questions customers actually ask, each answered in 2 to 4 sentences with FAQPage JSON-LD, creates ready-made citation targets shaped exactly like assistant queries.",
            "priority": "medium"})

    print(json.dumps({"module": "quotability", "findings": findings, "proactive": proactive,
                      "stats": {"jsonld_entities": sorted(types), "pages_checked": len(pages),
                                "quotable_paragraphs": len(quotable)}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
