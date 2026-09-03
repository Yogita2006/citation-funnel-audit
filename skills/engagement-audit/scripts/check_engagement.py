#!/usr/bin/env python3
"""Retain gate: when a human clicks through from an AI answer, do they stay?

Checks the first-impression mechanics a static fetch can prove: whether the
first screen of text orients the visitor (what, for whom, next step), mobile
viewport, page weight, navigation and internal-link health, readability, and
a clear next action. Reads the crawl cache and prints findings as JSON.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
from html.parser import HTMLParser

SEV_PRIORITY = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}


def finding(fid, title, severity, evidence, action, mechanism, confidence="high"):
    return {
        "id": fid, "title": title, "severity": severity, "confidence": confidence,
        "category": "engagement", "mechanism": mechanism, "evidence": evidence,
        "suggested_action": {"summary": action, "priority": SEV_PRIORITY[severity]},
    }


class PageView(HTMLParser):
    SKIP = {"script", "style", "template", "svg", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas = {}
        self.title = ""
        self.h1 = []
        self.paragraphs = []
        self.links = []          # (href, text)
        self.buttons = []
        self.nav_links = []
        self.ordered_text = []   # visible text in document order
        self._stack = []
        self._in_nav = 0
        self._anchor = None
        self._buf = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            n = (a.get("name") or a.get("property") or "").lower()
            if n:
                self.metas[n] = a.get("content", "")
        elif tag == "title":
            self._in_title = True
        elif tag in self.SKIP:
            self._stack.append("skip")
        elif tag == "nav":
            self._in_nav += 1
        elif tag == "a":
            self._anchor = [a.get("href", ""), ""]
        elif tag == "button":
            self._buf = []
            self._stack.append("button")
        elif tag in ("h1", "p"):
            self._buf = []
            self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "nav" and self._in_nav:
            self._in_nav -= 1
        elif tag == "a" and self._anchor is not None:
            href, text = self._anchor
            self.links.append((href, text.strip()))
            if self._in_nav:
                self.nav_links.append((href, text.strip()))
            self._anchor = None
        elif self._stack and self._stack[-1] in ("skip", "button", "h1", "p") and tag in (
                "script", "style", "template", "svg", "noscript", "button", "h1", "p"):
            mode = self._stack.pop()
            if self._buf is not None and mode in ("button", "h1", "p"):
                text = re.sub(r"\s+", " ", " ".join(self._buf)).strip()
                if text:
                    if mode == "button":
                        self.buttons.append(text)
                    elif mode == "h1":
                        self.h1.append(text)
                    else:
                        self.paragraphs.append(text)
            self._buf = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if "skip" in self._stack:
            return
        t = data.strip()
        if not t:
            return
        self.ordered_text.append(t)
        if self._buf is not None:
            self._buf.append(data)
        if self._anchor is not None:
            self._anchor[1] += " " + t


def parse(html):
    v = PageView()
    try:
        v.feed(html)
    except Exception:
        pass
    return v


ACTION_RE = re.compile(
    r"\b(get started|start free|sign up|book|order|buy|shop|contact|subscribe|"
    r"request|try|demo|download|reserve|apply|donate|call us|get a quote|learn more)\b", re.I)
NOISE_RE = re.compile(r"cookie|consent|accept all|privacy policy|newsletter", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    args = ap.parse_args()
    with open(os.path.join(args.cache, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    findings, proactive = [], []

    pages = []
    for rec in manifest.get("pages", []):
        if rec.get("file"):
            path = os.path.join(args.cache, rec["file"])
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    html = f.read()
                if rec.get("status") == 200 and html:
                    pages.append((rec, html, parse(html)))
    if not pages:
        print(json.dumps({"module": "engagement", "findings": [], "proactive": [],
                          "stats": {"note": "no fetchable pages in cache"}}))
        return 0

    home_rec, home_html, home = next(
        ((r, h, v) for r, h, v in pages if r["role"] == "home"), pages[0])

    # 1. First-screen orientation: what greets the visitor in document order?
    first_chunk = " ".join(home.ordered_text)[:1200]
    noise_leads = NOISE_RE.search(first_chunk[:300])
    has_h1 = bool(home.h1)
    h1_ok = has_h1 and 2 <= len(home.h1[0].split()) <= 14
    support_para = any(len(p.split()) >= 12 for p in home.paragraphs[:4])
    if not has_h1 or not support_para:
        findings.append(finding(
            "F-ENGAGE-001", "First screen does not tell the visitor what this is", "high",
            "Homepage %s: h1 present: %s; an explanatory paragraph of 12 or more words near the top: %s. A visitor arriving from an AI answer gets no confirmation they are in the right place." % (
                home_rec["final_url"], has_h1, support_para),
            "Open the page with a headline naming what the brand does, one supporting sentence for whom and why, and one primary action, all visible before scrolling.",
            "Visitors from AI answers arrive with a formed question; if the first screen does not confirm the answer is here, they return to the assistant within seconds."))
    elif has_h1 and not h1_ok:
        proactive.append({
            "id": "P-ENGAGE-001",
            "summary": "The homepage h1 ('%s...') is %d words. Aim for a 2 to 14 word headline that names the offering rather than a slogan or a paragraph." % (
                home.h1[0][:60], len(home.h1[0].split())),
            "priority": "low"})
    if noise_leads:
        proactive.append({
            "id": "P-ENGAGE-002",
            "summary": "Cookie or consent text dominates the top of the homepage markup. Keep the consent layer visually and structurally out of the first content screen so orientation survives it.",
            "priority": "low"})

    # 2. Clear next action on the homepage.
    ctas = [t for t in home.buttons if ACTION_RE.search(t)] + \
           [t for _h, t in home.links if t and ACTION_RE.search(t)]
    if not ctas:
        findings.append(finding(
            "F-ENGAGE-002", "No visible next step anywhere on the homepage", "medium",
            "No button or link with action wording (get started, contact, book, buy, download and similar) found in homepage markup.",
            "Add one primary call to action above the fold and repeat it after each major section; make the visitor's next step a decision they never have to search for.",
            "Engagement dies at the moment a convinced visitor cannot see what to do next.",
            confidence="medium"))

    # 3. Mobile viewport.
    if "viewport" not in home.metas:
        findings.append(finding(
            "F-ENGAGE-003", "No mobile viewport meta tag", "high",
            "The homepage lacks <meta name=\"viewport\">, so phones render the desktop layout zoomed out.",
            "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> and verify key templates on a phone.",
            "Most assistant-referred traffic is mobile; an unreadable first paint is an instant bounce."))

    # 4. Page weight and script load as a latency proxy.
    html_kb = len(home_html) // 1024
    script_count = home_html.lower().count("<script")
    if html_kb > 1500 or script_count > 70:
        findings.append(finding(
            "F-ENGAGE-004", "Homepage payload is unusually heavy", "medium",
            "HTML alone is %d KB with %d script tags before any assets load." % (html_kb, script_count),
            "Cut unused scripts and inline payloads, lazy-load below-the-fold media, and measure with Lighthouse; target first contentful paint under 2 seconds on mobile.",
            "Every second of load costs a measurable share of arrivals, and slow fetches also cause AI fetchers to time out.",
            confidence="medium"))

    # 5. Internal navigation health across the crawled sample.
    broken = [(r["url"], r.get("status")) for r in manifest.get("pages", [])
              if r.get("role") != "home" and isinstance(r.get("status"), int) and r["status"] >= 400]
    if broken:
        findings.append(finding(
            "F-ENGAGE-005", "%d internal links from the homepage or sitemap are broken" % len(broken), "high",
            "Examples: %s." % ", ".join("%s -> HTTP %s" % (u, s) for u, s in broken[:3]),
            "Fix or redirect the broken URLs and add a link checker to the deploy pipeline.",
            "Broken paths end sessions for humans and truncate crawls for machines; both halves of the funnel lose."))

    nav_count = len({h for h, _t in home.nav_links if h})
    if nav_count == 0 and len({h for h, _t in home.links if h}) < 5:
        findings.append(finding(
            "F-ENGAGE-006", "Homepage offers almost no paths deeper into the site", "medium",
            "No nav element links and fewer than 5 total links found in homepage markup.",
            "Add a simple persistent navigation covering the pages that answer buyer questions: product or services, pricing, about, contact.",
            "A single-exit page converts an interested visitor into a bounce statistic.",
            confidence="medium"))
    elif nav_count > 40:
        proactive.append({
            "id": "P-ENGAGE-003",
            "summary": "Navigation exposes %d links. Consider collapsing to 5 to 7 top-level choices; oversized menus measurably slow orientation." % nav_count,
            "priority": "low"})

    # 6. Readability of body copy.
    walls = [p for _r, _h, v in pages for p in v.paragraphs if len(p.split()) > 120]
    if len(walls) >= 3:
        findings.append(finding(
            "F-ENGAGE-007", "Body copy runs in walls of text", "low",
            "%d paragraphs longer than 120 words across sampled pages." % len(walls),
            "Break long paragraphs at one idea each, add subheadings every few paragraphs, and front-load the conclusion of each section.",
            "Scanning is how web reading works; unscannable copy loses the reader before the argument lands."))

    # 7. Context retention for returning or deep-linked visitors.
    has_search = bool(re.search(r"type=[\"']search|role=[\"']search|<input[^>]+search", home_html, re.I))
    if not has_search and len(manifest.get("pages", [])) > 5:
        proactive.append({
            "id": "P-ENGAGE-004",
            "summary": "No site search detected. On content-rich sites, search is how a deep-linked visitor recovers when they land on the wrong page; consider adding it to the header.",
            "priority": "low"})

    # 8. Buried important pages: key pages the homepage does not link to (a
    # cheap click-depth proxy, trusted only when the nav is server-rendered).
    home_hrefs = " ".join(h for h, _t in home.links if h)
    if len({h for h, _t in home.links if h}) >= 5:
        buried = []
        for rec in manifest.get("pages", []):
            if rec.get("role") in ("pricing", "product", "contact", "about"):
                path = urllib.parse.urlsplit(rec.get("final_url") or "").path.rstrip("/")
                seg = path.rsplit("/", 1)[-1]
                if len(path) > 1 and path not in home_hrefs and (not seg or seg not in home_hrefs):
                    buried.append((rec.get("role"), rec.get("final_url")))
        if buried:
            findings.append(finding(
                "F-ENGAGE-008", "Key pages are not linked from the homepage", "medium",
                "These important pages exist but no homepage link points to them: %s. A visitor who lands on the homepage cannot reach them in one click." % (
                    ", ".join("%s (%s)" % (r, u) for r, u in buried[:3])),
                "Link product or services, pricing, about and contact directly from the homepage header or hero, not only from the footer or the sitemap.",
                "Every extra click between the landing page and the answer sheds visitors, and pages the homepage never links are discovered weakly by crawlers too.",
                confidence="medium"))

    print(json.dumps({"module": "engagement", "findings": findings, "proactive": proactive,
                      "stats": {"home_html_kb": html_kb, "script_tags": script_count,
                                "nav_links": nav_count, "ctas_found": len(ctas)}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
