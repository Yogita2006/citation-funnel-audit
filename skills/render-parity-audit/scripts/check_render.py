#!/usr/bin/env python3
"""Read gate: does the content exist for a machine that does not run JavaScript?

AI retrieval fetchers and most crawlers read the raw HTML response. This module
measures how much human-visible substance survives in that raw HTML: empty SPA
shells, text locked in images, content trapped in PDFs or iframes.
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
        "category": "render", "mechanism": mechanism, "evidence": evidence,
        "suggested_action": {"summary": action, "priority": SEV_PRIORITY[severity]},
    }


class PageStats(HTMLParser):
    """Single-pass extraction of what a non-JS reader can see."""
    SKIP = {"script", "style", "template", "noscript", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts = []
        self.noscript_parts = []
        self.script_srcs = []
        self.inline_script_bytes = 0
        self.images = []            # (src, has_alt_text)
        self.iframes = []
        self.links = []             # (href, anchor_text)
        self.h1 = []
        self._stack = []
        self._anchor = None
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self._stack.append(tag)
            if tag == "script":
                self._in_script = True
                if a.get("src"):
                    self.script_srcs.append(a["src"])
        elif tag == "img":
            self.images.append((a.get("src", ""), bool((a.get("alt") or "").strip())))
        elif tag == "iframe":
            self.iframes.append(a.get("src", ""))
        elif tag == "a":
            self._anchor = [a.get("href", ""), ""]
        elif tag == "h1":
            self._stack.append("h1capture")

    def handle_endtag(self, tag):
        if self._stack and (self._stack[-1] == tag or (tag == "h1" and self._stack[-1] == "h1capture")):
            self._stack.pop()
        if tag == "script":
            self._in_script = False
        if tag == "a" and self._anchor is not None:
            self.links.append(tuple(self._anchor))
            self._anchor = None

    def handle_data(self, data):
        if self._in_script:
            self.inline_script_bytes += len(data)
            return
        skipping = [s for s in self._stack if s in self.SKIP]
        if skipping:
            if skipping[-1] == "noscript" or "noscript" in skipping:
                self.noscript_parts.append(data)
            return
        text = data.strip()
        if not text:
            return
        self.text_parts.append(text)
        if self._anchor is not None:
            self._anchor[1] += " " + text
        if "h1capture" in self._stack:
            self.h1.append(text)

    @property
    def visible_text(self):
        return " ".join(self.text_parts)


def parse_page(html):
    p = PageStats()
    try:
        p.feed(html)
    except Exception:
        pass
    return p


def load_pages(cache):
    with open(os.path.join(cache, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    pages = []
    for rec in manifest.get("pages", []):
        if not rec.get("file"):
            continue
        path = os.path.join(cache, rec["file"])
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            html = f.read()
        if rec.get("status") == 200 and html:
            pages.append((rec, html))
    return manifest, pages


SPA_SHELL_RE = re.compile(r"<div[^>]+id=[\"'](root|app|__next|___gatsby|q-app|svelte)[\"']", re.I)
STATE_JSON_RE = re.compile(r"__NEXT_DATA__|window\.__NUXT__|__INITIAL_STATE__|self\.__next_f", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    args = ap.parse_args()
    manifest, pages = load_pages(args.cache)
    findings, proactive = [], []
    if not pages:
        print(json.dumps({"module": "render", "findings": [], "proactive": [],
                          "stats": {"note": "no fetchable pages in cache"}}))
        return 0

    thin_pages, stats_rows = [], []
    for rec, html in pages:
        p = parse_page(html)
        words = len(p.visible_text.split())
        stats_rows.append({"url": rec["final_url"], "role": rec["role"], "words_no_js": words,
                           "html_kb": round(len(html) / 1024), "scripts": len(p.script_srcs)})
        if words < 120:
            thin_pages.append((rec, html, p, words))

    # 1. SPA shell: the page a machine receives is essentially empty.
    home = next(((rec, html) for rec, html in pages if rec["role"] == "home"), pages[0])
    home_rec, home_html = home
    hp = parse_page(home_html)
    home_words = len(hp.visible_text.split())
    is_shell = SPA_SHELL_RE.search(home_html) and home_words < 150
    if is_shell:
        mitigated = bool(STATE_JSON_RE.search(home_html))
        findings.append(finding(
            "F-RENDER-001", "Homepage is a JavaScript shell with almost no crawlable text",
            "critical" if not mitigated else "high",
            "Raw HTML of %s contains only %d words of visible text outside scripts; a client-side app root element is present%s. A human with JavaScript sees a full page; a fetcher that does not execute JavaScript sees an empty frame." % (
                home_rec["final_url"], home_words,
                ", though a serialized state blob exists that some crawlers can partially mine" if mitigated else ""),
            "Server-render or statically prerender every public page so the complete text arrives in the initial HTML response. In Next.js or Nuxt, enable SSR or SSG for public routes; otherwise add prerendering at the edge.",
            "Assistants build answers from what a simple fetch returns; content assembled only after page load is invisible to them (appendix concept C)."))
    elif home_words < 120 and home_rec.get("status") == 200:
        findings.append(finding(
            "F-RENDER-002", "Homepage has very little machine-readable text", "high",
            "Only %d words of visible text in the raw HTML of %s." % (home_words, home_rec["final_url"]),
            "State plainly in HTML text who the brand is, what it offers, for whom, and where. Every fact that matters must exist as text, not only inside images or video.",
            "A machine can only quote what it can read as text (appendix concept C)."))

    # 2. Thin interior pages (only when the homepage itself is not the story).
    if not is_shell and home_words >= 120:
        thin_interior = [(r, w) for (r, _h, _p, w) in thin_pages if r["role"] != "home"]
        if len(thin_interior) >= 2:
            listing = "; ".join("%s (%d words)" % (r["final_url"], w) for r, w in thin_interior[:4])
            findings.append(finding(
                "F-RENDER-003", "%d key pages carry almost no crawlable text" % len(thin_interior), "high",
                "Pages with under 120 words of raw-HTML text: %s." % listing,
                "Ensure product, pricing, about and contact pages deliver their substance as server-rendered text.",
                "The pages that answer buyer questions are exactly the ones assistants fetch; if they are empty to a machine, competitors get cited instead."))

    # 3. Content locked in images.
    total_imgs = sum(len(parse_page(h).images) for _r, h in pages[:4])
    missing_alt = sum(1 for _r, h in pages[:4] for _src, has in parse_page(h).images if not has)
    if total_imgs >= 5 and missing_alt / max(total_imgs, 1) > 0.5:
        findings.append(finding(
            "F-RENDER-010", "Most images ship without alt text", "medium",
            "%d of %d images across sampled pages have empty or missing alt attributes." % (missing_alt, total_imgs),
            "Write descriptive alt text for every informative image, and move any facts that exist only inside images (menus, price boards, infographics) into HTML text as well.",
            "Facts locked inside pixels are invisible to text extraction; alt text and parallel HTML text are the machine-readable copy (appendix concept C).",
            confidence="high"))

    # 4. Critical info behind PDFs.
    pdf_links = []
    for rec, html in pages:
        for href, text in parse_page(html).links:
            if re.search(r"\.pdf($|\?)", href or "", re.I) and re.search(
                    r"menu|price|pricing|brochure|catalog|spec|rate", (href or "") + " " + (text or ""), re.I):
                pdf_links.append((href, text.strip()[:40]))
    if pdf_links:
        findings.append(finding(
            "F-RENDER-011", "Key facts appear to live only in linked PDFs", "medium",
            "Found %d PDF links whose names suggest core content (e.g. %s). PDFs are fetched far less often than HTML by answer engines and extract poorly." % (
                len(pdf_links), ", ".join(sorted({h for h, _t in pdf_links})[:3])),
            "Publish the same content (menus, price lists, specs) as an HTML page and keep the PDF as a secondary download.",
            "Content that only exists in a PDF is one step further from being quoted than the same content in HTML.",
            confidence="medium"))

    # 5. Main content inside iframes.
    home_iframes = [s for s in hp.iframes if s and not re.search(r"youtube|vimeo|maps|recaptcha|gtm|doubleclick", s, re.I)]
    if home_iframes and home_words < 200:
        findings.append(finding(
            "F-RENDER-012", "Homepage content is embedded via iframe", "high",
            "Non-media iframes on a text-thin homepage: %s. Iframe content belongs to another document and is usually not attributed to this page." % ", ".join(home_iframes[:2]),
            "Move primary content out of iframes into the page itself; reserve iframes for third-party widgets.",
            "Crawlers index the framing page, not the framed document, so the content does not count for this URL."))

    # 6. Content revealed only by scroll or a click (invisible to one fetch).
    LOADMORE_RE = re.compile(r"\b(load more|show more|view more|see more|load all|show all)\b", re.I)
    INFINITE_RE = re.compile(r"infinite[\s_-]?scroll|data-infinite|js-load-more|data-load-more|data-next-page", re.I)
    lm_hits = [rec["final_url"] for rec, html in pages if LOADMORE_RE.search(html) or INFINITE_RE.search(html)]
    if lm_hits:
        findings.append(finding(
            "F-RENDER-013", "Content is revealed only by scroll or a 'load more' action", "medium",
            "Load-more or infinite-scroll markup found on %d page(s), e.g. %s. Items past the first batch are fetched by JavaScript on interaction, so a single crawl fetch never sees them." % (
                len(lm_hits), lm_hits[0]),
            "Provide crawlable pagination (real <a href> links to page 2, 3, ...) or server-render the full list; keep infinite scroll as an enhancement on top of real links.",
            "A fetcher makes one request and does not scroll or click; whatever is not in that first response does not exist for citation (appendix concept C).",
            confidence="medium"))

    # 7. Homepage substance locked inside a video.
    VIDEO_RE = re.compile(r"youtube\.com/embed|youtu\.be/|player\.vimeo\.com|<video[\s>]", re.I)
    if VIDEO_RE.search(home_html) and home_words < 150:
        findings.append(finding(
            "F-RENDER-014", "Homepage leads with a video but little machine-readable text", "medium",
            "A video embed is present on the homepage while the raw HTML has only %d words of text. If the core message is spoken in the video, a machine cannot read it." % home_words,
            "Add a text transcript or a written summary of the video's key points as HTML on the page.",
            "Speech inside a video is not text a fetcher can extract; the same facts must also exist as HTML to be quoted (appendix concept C).",
            confidence="medium"))

    print(json.dumps({"module": "render", "findings": findings, "proactive": proactive,
                      "stats": {"pages": stats_rows}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
