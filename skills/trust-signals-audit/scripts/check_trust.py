#!/usr/bin/env python3
"""Trust gate: would a machine believe and repeat what it read here?

Checks the freshness signals a machine can see (dates in schema, sitemap
lastmod, copyright years), entity disambiguation (consistent naming,
sameAs, og:site_name), and cross-page consistency of hard facts (phone
numbers). Reads the crawl cache and prints findings as JSON.
"""

import argparse
import datetime
import json
import os
import re
import sys
from html.parser import HTMLParser

SEV_PRIORITY = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}


def finding(fid, title, severity, evidence, action, mechanism, confidence="high"):
    return {
        "id": fid, "title": title, "severity": severity, "confidence": confidence,
        "category": "trust", "mechanism": mechanism, "evidence": evidence,
        "suggested_action": {"summary": action, "priority": SEV_PRIORITY[severity]},
    }


class MetaExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas = {}
        self.jsonld_raw = []
        self.text_parts = []
        self.title = ""
        self._in_script = None
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name:
                self.metas[name] = a.get("content", "")
        elif tag == "script":
            t = (a.get("type") or "").lower()
            self._in_script = "jsonld" if "ld+json" in t else "js"
            if self._in_script == "jsonld":
                self.jsonld_raw.append("")
        elif tag == "title":
            self._in_title = True
        elif tag in ("style", "svg", "template", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = None
        elif tag == "title":
            self._in_title = False
        elif tag in ("style", "svg", "template", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_script == "jsonld":
            self.jsonld_raw[-1] += data
        elif self._in_script is None and not self._skip:
            if data.strip():
                self.text_parts.append(data.strip())


def parse(html):
    e = MetaExtractor()
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
    p = os.path.join(cache, "profile.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def phones_in_page(html, text):
    """High-precision phone extraction: tel: links, or numbers immediately
    after phone-ish keywords. Avoids matching dates, prices, and code."""
    found = set()
    for m in re.finditer(r"href=[\"']tel:([^\"']+)", html or "", re.I):
        digits = re.sub(r"\D", "", m.group(1))
        if len(digits) >= 7:
            found.add(digits[-10:])
    for m in re.finditer(r"(?:phone|call us|call|tel|fax)\W{0,15}(\+?\d[\d ().-]{7,}\d)",
                         text or "", re.I):
        raw = m.group(1)
        if "\n" in raw or "  " in raw:
            continue
        digits = re.sub(r"\D", "", raw)
        if 10 <= len(digits) <= 13:
            found.add(digits[-10:])
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    args = ap.parse_args()
    manifest, pages = load_pages(args.cache)
    profile = load_profile(args.cache)
    findings, proactive = [], []
    if not pages:
        print(json.dumps({"module": "trust", "findings": [], "proactive": [],
                          "stats": {"note": "no fetchable pages in cache"}}))
        return 0

    now = datetime.datetime.now(datetime.timezone.utc)
    this_year = now.year
    all_text = " ".join(t for _r, e in pages for t in e.text_parts)

    entities = []
    for _r, e in pages:
        for raw in e.jsonld_raw:
            try:
                flatten_jsonld(json.loads(raw.strip()), entities)
            except Exception:
                pass

    # 1. Freshness: machine-visible dates.
    date_fields = []
    for ent in entities:
        for key in ("dateModified", "datePublished"):
            v = ent.get(key)
            if isinstance(v, str):
                date_fields.append((key, v))
    newest = None
    for _k, v in date_fields:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
        if m:
            try:
                d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                newest = max(newest, d) if newest else d
            except ValueError:
                pass

    sitemap = manifest.get("sitemap") or {}
    lastmod_ages = []
    sitemap_file = os.path.join(args.cache, "sitemap.xml")
    if os.path.exists(sitemap_file):
        with open(sitemap_file, encoding="utf-8") as f:
            for m in re.finditer(r"<lastmod>\s*(\d{4})-(\d{2})-(\d{2})", f.read()):
                try:
                    d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    lastmod_ages.append((now.date() - d).days)
                except ValueError:
                    pass

    if newest is None and not lastmod_ages:
        findings.append(finding(
            "F-TRUST-001", "No machine-readable freshness signal anywhere", "medium",
            "No datePublished or dateModified in structured data and no lastmod dates in the sitemap across %d sampled pages." % len(pages),
            "Emit dateModified in Article or WebPage JSON-LD and lastmod in the sitemap, updated by the build pipeline, so machines can see the content is maintained.",
            "Systems prefer sources they can prove are current; with no dates they must assume the worst or trust a fresher competitor.",
            confidence="medium"))
    elif newest and (now.date() - newest).days > 540:
        findings.append(finding(
            "F-TRUST-002", "Newest declared content date is %s" % newest.isoformat(), "medium",
            "The most recent datePublished or dateModified in structured data is %d days old." % (now.date() - newest).days,
            "Review and update cornerstone pages, then update their dateModified honestly. Do not fake dates; refresh the content itself.",
            "Stale declared dates tell assistants the site may describe a business that no longer exists in that form."))
    elif lastmod_ages and min(lastmod_ages) > 540:
        findings.append(finding(
            "F-TRUST-003", "Every sitemap lastmod is over 18 months old", "medium",
            "Freshest lastmod in sitemap.xml is %d days old across %d dated URLs." % (min(lastmod_ages), len(lastmod_ages)),
            "Regenerate the sitemap on deploy with true modification dates.",
            "A sitemap whose newest entry is ancient signals an abandoned site to every crawler that reads it."))

    # 2. Stale copyright year: cheap but widely read staleness cue.
    # Ranges like "(c) 2001-2026" count by their end year.
    years = []
    for m in re.finditer(r"(?:©|&copy;|copyright)[^0-9\n]{0,40}(20\d{2})(?:\s*[-–]\s*(20\d{2}))?",
                         all_text, re.I):
        years.append(int(m.group(2) or m.group(1)))
    if years and max(years) <= this_year - 2:
        findings.append(finding(
            "F-TRUST-004", "Footer copyright stuck at %d" % max(years), "low",
            "Copyright year %d found while the current year is %d." % (max(years), this_year),
            "Render the copyright year dynamically.",
            "Trivial to fix and one of the first staleness cues both humans and extraction heuristics notice."))

    # 3. Entity disambiguation: consistent identity across signals.
    home_rec, home_e = next(((r, e) for r, e in pages if r["role"] == "home"), pages[0])
    og_site = home_e.metas.get("og:site_name", "")
    org = next((ent for ent in entities if "Organization" in str(ent.get("@type"))
                or "LocalBusiness" in str(ent.get("@type"))), None)
    schema_name = (org or {}).get("name", "")
    names = {n.strip().lower() for n in (og_site, schema_name) if n and n.strip()}
    if len(names) > 1:
        findings.append(finding(
            "F-TRUST-010", "Brand is named inconsistently across identity signals", "medium",
            "og:site_name says '%s' while Organization schema says '%s'." % (og_site, schema_name),
            "Pick one canonical brand string and use it identically in Organization name, og:site_name, the title suffix, and the footer.",
            "Machines resolve entities by string agreement; every variant spelling splits the identity and invites mix-ups with similarly named entities (appendix concept D)."))
    if not og_site and not home_e.metas.get("og:title"):
        proactive.append({
            "id": "P-TRUST-001",
            "summary": "No Open Graph tags on the homepage. Add og:site_name, og:title, og:description and og:image; they are read by far more systems than social networks alone and reinforce the brand entity.",
            "priority": "low"})

    # 4. Hard-fact consistency: phone numbers must agree across pages.
    per_page_phones = {}
    raw_by_url = {}
    for rec in manifest.get("pages", []):
        if rec.get("file"):
            p = os.path.join(args.cache, rec["file"])
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    raw_by_url[rec.get("final_url")] = f.read()
    for r, e in pages:
        found = phones_in_page(raw_by_url.get(r["final_url"], ""), " ".join(e.text_parts))
        if found:
            per_page_phones[r["final_url"]] = found
    distinct = set().union(*per_page_phones.values()) if per_page_phones else set()
    if len(distinct) > 2:
        findings.append(finding(
            "F-TRUST-011", "Multiple different phone numbers across the site", "medium",
            "%d distinct numbers appear across %d pages. If some are outdated, machines cannot tell which is real." % (
                len(distinct), len(per_page_phones)),
            "Keep exactly one current phone number (or one per location, clearly labeled) sourced from a single template include, and matching the number in LocalBusiness schema and business listings.",
            "Contradicting facts inside the site itself is the strongest possible signal that any one of them might be wrong (appendix concept D).",
            confidence="medium"))

    # 5. Corroboration surface: does the site point to its off-site identity?
    social_hosts = ("linkedin.com", "wikipedia.org", "wikidata.org", "crunchbase.com",
                    "instagram.com", "facebook.com", "x.com", "twitter.com", "youtube.com", "github.com")
    site_html_all = "".join(raw_by_url.values())
    linked_profiles = {h for h in social_hosts if h in site_html_all}
    if not linked_profiles and not (org or {}).get("sameAs"):
        findings.append(finding(
            "F-TRUST-012", "Site is an island: no links to any off-site brand profile", "medium",
            "No links to LinkedIn, Wikipedia, Wikidata, Crunchbase, GitHub or social profiles anywhere in sampled pages, and no sameAs in schema.",
            "Link official profiles in the footer and declare them in Organization sameAs. Then keep name, description and address identical across those profiles.",
            "A claim that exists in exactly one place is fragile; corroboration across independent sources is what makes machines repeat it (appendix concept D)."))

    # 6. Authorship on article-like pages.
    is_content_site = profile.get("type") == "content"
    article_pages = [r for r, _e in pages if r["role"] == "news"]
    if (article_pages or is_content_site) and not any("author" in json.dumps(ent, default=str).lower() for ent in entities):
        proactive.append({
            "id": "P-TRUST-002",
            "summary": "Blog or news pages carry no author markup. Add visible bylines plus Person schema with author credentials; attributed content is weighted as more trustworthy by retrieval systems.",
            "priority": "medium"})

    print(json.dumps({"module": "trust", "findings": findings, "proactive": proactive,
                      "stats": {"jsonld_entities_found": len(entities),
                                "newest_declared_date": newest.isoformat() if newest else None,
                                "linked_profiles": sorted(linked_profiles)}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
