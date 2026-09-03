#!/usr/bin/env python3
"""Polite, read-only site crawler for the Citation Funnel audit.

Fetches robots.txt, the homepage, sitemap.xml, and up to --max-pages
high-value internal pages (about, pricing, contact, product, faq, blog),
then writes everything to a cache directory that the analysis modules read.

Read-only by design: GET requests only, custom identifying user agent,
honors robots.txt rules for '*', fixed politeness delay, hard time budget.
Python 3.8+ standard library only.
"""

import argparse
import gzip
import json
import os
import re
import sys
import time
import zlib
import urllib.parse
import urllib.request
import ssl
from html.parser import HTMLParser

USER_AGENT = "CitationFunnelAudit/1.0 (read-only site audit; respects robots.txt)"
FETCH_TIMEOUT = 12
POLITENESS_DELAY = 0.6
TIME_BUDGET_SECONDS = 120

# Path keywords that answer the questions people ask AI assistants about a brand,
# in priority order. The crawler prefers these over arbitrary internal links.
PRIORITY_PATTERNS = [
    ("about", r"/about|/company|/who-we-are|/our-story|/team"),
    ("pricing", r"/pricing|/plans|/price|/rates|/fees"),
    ("contact", r"/contact|/support|/help|/locations|/find-us"),
    ("product", r"/product|/services|/features|/solutions|/menu|/shop|/store"),
    ("faq", r"/faq|/frequently|/questions|/docs|/documentation"),
    ("news", r"/blog|/news|/updates|/press|/articles|/insights"),
]


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value.strip())


def parse_robots(text):
    """Parse robots.txt into {agent_lower: {"allow": [...], "disallow": [...]}} plus sitemaps."""
    groups = {}
    sitemaps = []
    current_agents = []
    last_was_agent = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if not last_was_agent:
                current_agents = []
            current_agents.append(value.lower())
            groups.setdefault(value.lower(), {"allow": [], "disallow": []})
            last_was_agent = True
            continue
        last_was_agent = False
        if field == "sitemap" and value:
            sitemaps.append(value)
        elif field in ("allow", "disallow"):
            for agent in current_agents:
                groups[agent][field].append(value)
    return {"groups": groups, "sitemaps": sitemaps}


def rule_matches(rule, path):
    if not rule:
        return False
    pattern = re.escape(rule).replace(r"\*", ".*")
    if pattern.endswith(r"\$"):
        pattern = pattern[:-2] + "$"
    return re.match(pattern, path) is not None


def allowed_by_robots(robots, path, agent="*"):
    """Longest-match evaluation of allow/disallow for one agent group."""
    group = robots["groups"].get(agent) or robots["groups"].get("*")
    if not group:
        return True
    best_len, best_allow = -1, True
    for rule in group.get("disallow", []):
        if rule and rule_matches(rule, path) and len(rule) > best_len:
            best_len, best_allow = len(rule), False
    for rule in group.get("allow", []):
        if rule and rule_matches(rule, path) and len(rule) >= best_len:
            best_len, best_allow = len(rule), True
    return best_allow


def decompress_body(raw, headers):
    """Undo gzip/deflate transfer compression; some CDNs compress regardless
    of Accept-Encoding, and gzip magic bytes are checked as a fallback."""
    encoding = (headers.get("content-encoding") or "").lower()
    try:
        if "gzip" in encoding or raw[:2] == b"\x1f\x8b":
            return gzip.decompress(raw)
        if "deflate" in encoding:
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:
        pass
    return raw


def fetch(url, binary=False):
    """GET a URL. Returns a record dict; never raises."""
    record = {
        "url": url, "final_url": url, "status": None, "headers": {},
        "redirect_chain": [], "fetch_ms": None, "error": None, "body": None,
    }
    chain = []

    class ChainRecorder(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            chain.append({"from": req.full_url, "to": newurl, "status": code})
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(ChainRecorder, urllib.request.HTTPSHandler(context=ctx))
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en",
        "Accept-Encoding": "gzip",
    })
    start = time.time()
    try:
        with opener.open(req, timeout=FETCH_TIMEOUT) as resp:
            raw = resp.read(3 * 1024 * 1024)
            record["status"] = resp.status
            record["final_url"] = resp.geturl()
            record["headers"] = {k.lower(): v for k, v in resp.headers.items()}
            raw = decompress_body(raw, record["headers"])
            record["body"] = raw if binary else raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        record["status"] = e.code
        record["final_url"] = e.url or url
        record["headers"] = {k.lower(): v for k, v in (e.headers or {}).items()}
        try:
            body = decompress_body(e.read(512 * 1024), record["headers"])
            record["body"] = body if binary else body.decode("utf-8", errors="replace")
        except Exception:
            record["body"] = None
    except Exception as e:
        record["error"] = "%s: %s" % (type(e).__name__, e)
    record["fetch_ms"] = int((time.time() - start) * 1000)
    record["redirect_chain"] = chain
    return record


def normalize_start_url(target):
    target = target.strip()
    if not re.match(r"^https?://", target, re.I):
        target = "https://" + target
    parsed = urllib.parse.urlsplit(target)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))


def same_site(url, host):
    try:
        netloc = urllib.parse.urlsplit(url).netloc.lower()
    except ValueError:
        return False
    host = host.lower()
    return netloc == host or netloc == "www." + host or "www." + netloc == host


def pick_pages(candidates, host, max_pages, exclude=()):
    """Deduplicate, keep same-site html-looking URLs, prefer priority patterns."""
    seen, cleaned = set(), []
    exclude_norm = {u.rstrip("/") for u in exclude}
    for link in candidates:
        link = urllib.parse.urldefrag(link)[0]
        if not link or not same_site(link, host):
            continue
        if link.rstrip("/") in exclude_norm:
            continue
        path = urllib.parse.urlsplit(link).path or "/"
        if re.search(r"\.(pdf|jpg|jpeg|png|gif|svg|webp|css|js|ico|zip|mp4|xml|woff2?)$", path, re.I):
            continue
        if link in seen:
            continue
        seen.add(link)
        cleaned.append(link)

    chosen, used = [], set()
    for label, pattern in PRIORITY_PATTERNS:
        for link in cleaned:
            if link in used:
                continue
            if re.search(pattern, urllib.parse.urlsplit(link).path, re.I):
                chosen.append({"url": link, "role": label})
                used.add(link)
                break
    for link in cleaned:
        if len(chosen) >= max_pages:
            break
        if link not in used:
            chosen.append({"url": link, "role": "other"})
            used.add(link)
    return chosen[:max_pages]


def extract_sitemap_urls(xml_text, limit=200):
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml_text or "")[:limit]


def main():
    ap = argparse.ArgumentParser(description="Crawl a site into an audit cache directory.")
    ap.add_argument("url", help="Site URL or bare domain, e.g. example.com")
    ap.add_argument("--cache", required=True, help="Directory to write the crawl cache into")
    ap.add_argument("--max-pages", type=int, default=8, help="Max internal pages beyond the homepage")
    args = ap.parse_args()

    start_time = time.time()
    os.makedirs(args.cache, exist_ok=True)
    start_url = normalize_start_url(args.url)
    parts = urllib.parse.urlsplit(start_url)
    host = parts.netloc
    origin = "%s://%s" % (parts.scheme, parts.netloc)

    manifest = {
        "site": host.replace("www.", ""),
        "start_url": start_url,
        "crawled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "user_agent": USER_AGENT,
        "pages": [],
        "robots": None,
        "sitemap": None,
        "llms_txt": None,
        "notes": [],
    }

    def save_page(record, name, role):
        body = record.pop("body", None)
        filename = None
        if body is not None:
            filename = name + ".html"
            with open(os.path.join(args.cache, filename), "w", encoding="utf-8") as f:
                f.write(body if isinstance(body, str) else body.decode("utf-8", "replace"))
        record["file"] = filename
        record["role"] = role
        manifest["pages"].append(record)
        return record

    # 1. robots.txt
    robots_rec = fetch(origin + "/robots.txt")
    robots_parsed = None
    if robots_rec["status"] == 200 and robots_rec.get("body"):
        with open(os.path.join(args.cache, "robots.txt"), "w", encoding="utf-8") as f:
            f.write(robots_rec["body"])
        robots_parsed = parse_robots(robots_rec["body"])
    manifest["robots"] = {
        "status": robots_rec["status"], "error": robots_rec["error"],
        "file": "robots.txt" if robots_parsed else None,
        "parsed": robots_parsed,
    }
    time.sleep(POLITENESS_DELAY)

    def may_fetch(url):
        if not robots_parsed:
            return True
        return allowed_by_robots(robots_parsed, urllib.parse.urlsplit(url).path or "/", "*")

    # 2. homepage
    home = fetch(start_url)
    save_page(home, "page_000_home", "home")
    home_html = None
    home_file = os.path.join(args.cache, "page_000_home.html")
    if os.path.exists(home_file):
        with open(home_file, encoding="utf-8") as f:
            home_html = f.read()
    time.sleep(POLITENESS_DELAY)

    # 3. llms.txt presence probe (informational only)
    llms = fetch(origin + "/llms.txt")
    manifest["llms_txt"] = {"status": llms["status"], "error": llms["error"],
                            "present": llms["status"] == 200 and bool(llms.get("body"))}
    time.sleep(POLITENESS_DELAY)

    # 4. sitemap: robots-declared first, else /sitemap.xml
    sitemap_urls = []
    sitemap_sources = (robots_parsed or {}).get("sitemaps") or []
    sitemap_try = sitemap_sources[:1] or [origin + "/sitemap.xml"]
    sm = fetch(sitemap_try[0])
    if sm["status"] == 200 and sm.get("body"):
        with open(os.path.join(args.cache, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write(sm["body"][:1024 * 1024])
        sitemap_urls = extract_sitemap_urls(sm["body"])
        # index sitemaps point at child sitemaps; expand the first child
        if sitemap_urls and all(u.endswith(".xml") for u in sitemap_urls[:5]):
            child = fetch(sitemap_urls[0])
            if child["status"] == 200 and child.get("body"):
                sitemap_urls = extract_sitemap_urls(child["body"]) or sitemap_urls
            time.sleep(POLITENESS_DELAY)
    manifest["sitemap"] = {
        "tried": sitemap_try[0], "status": sm["status"], "error": sm["error"],
        "declared_in_robots": bool(sitemap_sources), "url_count": len(sitemap_urls),
        "sample_urls": sitemap_urls[:50],
    }
    time.sleep(POLITENESS_DELAY)

    # 5. choose internal pages from homepage links plus sitemap
    candidates = []
    if home_html:
        collector = LinkCollector()
        try:
            collector.feed(home_html)
        except Exception:
            pass
        base = home.get("final_url") or start_url
        candidates = [urllib.parse.urljoin(base, l) for l in collector.links]
    candidates += sitemap_urls
    pages = pick_pages(candidates, host, args.max_pages,
                       exclude={start_url, home.get("final_url") or start_url})

    for i, page in enumerate(pages, start=1):
        if time.time() - start_time > TIME_BUDGET_SECONDS:
            manifest["notes"].append("time budget reached; stopped after %d pages" % i)
            break
        if not may_fetch(page["url"]):
            manifest["notes"].append("skipped (robots disallow for *): " + page["url"])
            continue
        rec = fetch(page["url"])
        save_page(rec, "page_%03d_%s" % (i, page["role"]), page["role"])
        time.sleep(POLITENESS_DELAY)

    manifest["elapsed_seconds"] = round(time.time() - start_time, 1)
    with open(os.path.join(args.cache, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps({"ok": True, "cache": args.cache,
                      "pages_fetched": len(manifest["pages"]),
                      "elapsed_seconds": manifest["elapsed_seconds"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
