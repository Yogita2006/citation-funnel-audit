#!/usr/bin/env python3
"""Site-type detection for the Citation Funnel audit.

The single most important guard against false positives: a personal blog is
not missing a Product schema, and a SaaS page is not missing a menu. This
module reads the crawl cache and classifies the site into a coarse type
(ecommerce, saas, local_business, content, documentation, portfolio,
brochure) from JSON-LD @type, og:type, URL vocabulary, and on-page
vocabulary, then writes profile.json into the cache so every gate can make
its checks conditional on site type instead of applying one checklist to
every site. Python 3.8+ standard library only.
"""

import argparse
import json
import os
import re
import sys


def strip_text(html):
    t = re.sub(r"(?is)<(script|style|template|noscript|svg)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def load(cache):
    with open(os.path.join(cache, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    pages = []
    for rec in manifest.get("pages", []):
        if not rec.get("file"):
            continue
        p = os.path.join(cache, rec["file"])
        if os.path.exists(p) and rec.get("status") == 200:
            with open(p, encoding="utf-8") as f:
                pages.append((rec, f.read()))
    return manifest, pages


TYPE_RE = re.compile(r'"@type"\s*:\s*"([^"]+)"')
OG_TYPE_RE = re.compile(r'<meta[^>]+property=["\']og:type["\'][^>]+content=["\']([^"\']+)', re.I)

# On-page vocabulary that signals each site type.
VOCAB = {
    "ecommerce": r"add to cart|add to basket|add to bag|proceed to checkout|\bcheckout\b|buy now|in stock|out of stock|free shipping|free delivery|shopping cart|view cart|shopping bag|my bag|wishlist|select size|size chart|size guide",
    "saas": r"free trial|start free|sign up free|get started free|per month|per user|/mo\b|pricing plans|book a demo|request a demo|integrations|single sign-on|\bSSO\b|api key",
    "local_business": r"opening hours|open today|book a table|make a reservation|reservations|get directions|our location|visit us|walk-ins|order for pickup|dine-in",
    "content": r"read more|continue reading|posted on|published on|min read|minute read|subscribe to (our )?newsletter|latest posts|recent posts|categories|\btags\b",
    "documentation": r"getting started|installation|quick ?start|api reference|npm install|pip install|yarn add|command line|changelog|read the docs",
    "portfolio": r"my work|my portfolio|selected work|about me|\bresume\b|\bcv\b|get in touch|hire me|freelance",
}
URLVOCAB = {
    "ecommerce": r"/cart|/checkout|/shop|/store|/product|/products|/collections|/basket|/order",
    "saas": r"/pricing|/plans|/signup|/sign-up|/app|/dashboard|/integrations|/features",
    "local_business": r"/menu|/reservations|/book|/locations|/find-us|/directions|/hours",
    "content": r"/blog|/article|/articles|/news|/posts|/story|/stories|/insights",
    "documentation": r"/docs|/documentation|/api|/reference|/guide|/guides|/manual",
    "portfolio": r"/portfolio|/work|/projects|/about-me",
}
SCHEMA_TYPES = {
    "ecommerce": {"product", "offer", "aggregateoffer", "onlinestore"},
    "saas": {"softwareapplication", "webapplication", "mobileapplication", "service"},
    "local_business": {"localbusiness", "restaurant", "store", "cafeorcoffeeshop",
                       "professionalservice", "medicalbusiness", "lodgingbusiness"},
    "content": {"article", "blogposting", "newsarticle", "blog", "liveblogposting"},
    "documentation": {"techarticle", "apireference", "howto"},
    "portfolio": {"profilepage", "creativework"},
}
EXPECTED_SCHEMA = {
    "ecommerce": ["Product", "Offer", "Organization"],
    "saas": ["SoftwareApplication", "Offer", "Organization"],
    "local_business": ["LocalBusiness", "PostalAddress", "OpeningHoursSpecification"],
    "content": ["Article (or BlogPosting)", "Person (author)"],
    "documentation": ["TechArticle", "Organization"],
    "portfolio": ["Person", "Organization"],
    "brochure": ["Organization"],
    "unknown": ["Organization"],
}


def detect(manifest, pages):
    all_text = " ".join(strip_text(h) for _r, h in pages)
    all_html = " ".join(h for _r, h in pages)
    roles = {r.get("role") for r, _h in pages}
    urls = " ".join((r.get("final_url") or "") for r, _h in pages)
    schema_types = {t.lower() for t in TYPE_RE.findall(all_html)}
    og_types = {t.lower() for t in OG_TYPE_RE.findall(all_html)}

    scores = {k: 0 for k in VOCAB}
    signals = []

    # Structured-data signals are the strongest evidence of intent.
    for typ, wanted in SCHEMA_TYPES.items():
        hit = schema_types & wanted
        if hit:
            scores[typ] += 5
            signals.append("schema %s -> %s" % (sorted(hit)[0], typ))
    if "product" in og_types:
        scores["ecommerce"] += 3; signals.append("og:type=product")
    if "article" in og_types:
        scores["content"] += 3; signals.append("og:type=article")
    if "profile" in og_types:
        scores["portfolio"] += 2; signals.append("og:type=profile")

    # URL vocabulary.
    for typ, pat in URLVOCAB.items():
        n = len(re.findall(pat, urls, re.I))
        if n:
            scores[typ] += min(n, 3)
            signals.append("url pattern -> %s (x%d)" % (typ, n))

    # Crawl role hints.
    if "pricing" in roles:
        scores["saas"] += 1; scores["ecommerce"] += 1
    if "news" in roles:
        scores["content"] += 1

    # On-page vocabulary (capped so one repeated phrase cannot dominate).
    for typ, pat in VOCAB.items():
        n = len(re.findall(pat, all_text, re.I))
        if n:
            scores[typ] += min(n, 4)
            signals.append("text vocab -> %s (x%d)" % (typ, n))

    # Prices are a strong commercial signal even on a category or landing page,
    # where product/offer schema may be absent. A lone Person node is NOT treated
    # as portfolio evidence (it appears on many sites as bylines or exec bios).
    price_hits = len(re.findall(r"\u20b9\s?\d|Rs\.?\s?\d|INR\s?\d|\$\s?\d|\u20ac\s?\d|\u00a3\s?\d|\bMRP\b", all_text, re.I))
    if price_hits:
        scores["ecommerce"] += min(price_hits, 3)
        signals.append("price signals -> ecommerce (x%d)" % price_hits)

    best = max(scores, key=lambda k: scores[k])
    top = scores[best]
    ordered = sorted(scores.values(), reverse=True)
    second = ordered[1] if len(ordered) > 1 else 0
    if top < 3:
        site_type, conf = "brochure", "low"
    elif top >= 5 and (top - second) >= 3:
        site_type, conf = best, "high"
    else:
        site_type, conf = best, "medium"

    commercial = site_type in ("ecommerce", "saas", "local_business")
    return {
        "site": manifest.get("site"),
        "type": site_type,
        "confidence": conf,
        "commercial": commercial,
        "expected_schema": EXPECTED_SCHEMA.get(site_type, ["Organization"]),
        "signals": signals[:8],
        "scores": scores,
    }


def main():
    ap = argparse.ArgumentParser(description="Detect site type into profile.json in the crawl cache.")
    ap.add_argument("--cache", required=True)
    args = ap.parse_args()
    manifest, pages = load(args.cache)
    if not pages:
        profile = {"site": manifest.get("site"), "type": "unknown", "confidence": "low",
                   "commercial": False, "expected_schema": ["Organization"],
                   "signals": [], "scores": {}}
    else:
        profile = detect(manifest, pages)
    with open(os.path.join(args.cache, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    print(json.dumps({"ok": True, "type": profile["type"], "confidence": profile["confidence"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
