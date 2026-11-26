#!/usr/bin/env python3
"""Reach gate: can AI systems get to the site at all?

Checks robots.txt policy per AI crawler category, HTTP health of the
homepage and key pages, redirect hygiene, noindex directives, canonicals,
and sitemap availability. Reads the crawl cache produced by
audit-orchestrator/scripts/crawl_site.py and prints findings as JSON.
"""

import argparse
import datetime
import json
import os
import re
import urllib.parse
import sys

# AI crawler user agents by function. Blocking the retrieval or user-fetch
# agents removes the site from live AI answers; blocking training-only agents
# is a legitimate policy choice, so it is reported as informational trade-off.
AI_AGENTS = {
    "retrieval": ["oai-searchbot", "claude-searchbot", "perplexitybot", "amazonbot"],
    "user_fetch": ["chatgpt-user", "claude-user", "perplexity-user", "mistralai-user"],
    "training": ["gptbot", "claudebot", "anthropic-ai", "google-extended",
                 "applebot-extended", "ccbot", "meta-externalagent", "bytespider"],
}

SEV_PRIORITY = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}


def finding(fid, title, severity, evidence, action, mechanism, confidence="high"):
    return {
        "id": fid, "title": title, "severity": severity, "confidence": confidence,
        "category": "reach", "mechanism": mechanism, "evidence": evidence,
        "suggested_action": {"summary": action, "priority": SEV_PRIORITY[severity]},
    }


def load_manifest(cache):
    with open(os.path.join(cache, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def read_page(cache, rec):
    if not rec.get("file"):
        return None
    path = os.path.join(cache, rec["file"])
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def robots_verdict_for_agent(parsed, agent):
    """Is the site root effectively blocked for this agent? Longest-match on '/'."""
    groups = parsed.get("groups", {})
    group = groups.get(agent) or groups.get("*")
    if not group:
        return "allowed", "no matching group"
    specific = agent in groups
    dis = group.get("disallow", [])
    allow = group.get("allow", [])
    if "/" in dis and not any(a == "/" or a == "" for a in allow):
        return "blocked", ("specific group" if specific else "wildcard group") + " has Disallow: /"
    return "allowed", "root not disallowed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    args = ap.parse_args()
    m = load_manifest(args.cache)
    findings, proactive = [], []
    origin_pages = m.get("pages", [])
    home = next((p for p in origin_pages if p.get("role") == "home"), None)

    # 1. Homepage reachability: if this fails, nothing downstream matters.
    if not home or home.get("error"):
        findings.append(finding(
            "F-REACH-001", "Homepage could not be fetched at all", "critical",
            "GET %s failed: %s" % (m.get("start_url"), (home or {}).get("error", "no response")),
            "Make the homepage return HTTP 200 over HTTPS for standard clients; check DNS, TLS certificate, and any bot-blocking WAF rules.",
            "A crawler that cannot fetch the page cannot index or cite anything on it (appendix concept A)."))
    elif home.get("status") in (401, 403, 429, 503):
        # A refusal aimed at this audit's own request. It proves the site turns
        # away unrecognised automated clients; it does not prove that named AI
        # crawlers are refused, so it is reported with low confidence.
        findings.append(finding(
            "F-REACH-003", "Site refused the audit's request (HTTP %s)" % home.get("status"), "high",
            "GET %s -> %s (final URL %s). This is typically bot protection (a WAF or CDN rule) answering an unrecognised client. The audit could not read any page, and it cannot tell from here whether AI retrieval bots are refused the same way." % (
                home["url"], home.get("status"), home.get("final_url")),
            "Check the bot-protection rules: confirm that the AI retrieval and user-fetch agents you want (for example OAI-SearchBot, PerplexityBot, ChatGPT-User, Claude-User) are allow-listed, and verify with their published user agents or IP ranges.",
            "Bot protection that blocks unknown clients often blocks AI fetchers too; an assistant that gets a 403 has nothing to quote (appendix concept A).",
            confidence="low"))
    elif home.get("status") != 200:
        findings.append(finding(
            "F-REACH-002", "Homepage returns HTTP %s" % home.get("status"), "critical",
            "GET %s -> %s (final URL %s)" % (home["url"], home.get("status"), home.get("final_url")),
            "Return HTTP 200 on the canonical homepage URL. Fix the server error or the redirect target.",
            "Non-200 responses are dropped by crawlers and answer engines before content is ever read."))

    # 2. robots.txt health and per-agent policy.
    robots = m.get("robots") or {}
    parsed = robots.get("parsed")
    if robots.get("status") and 500 <= robots["status"] < 600:
        findings.append(finding(
            "F-REACH-010", "robots.txt returns a server error", "high",
            "GET /robots.txt -> HTTP %s. Several crawlers treat a 5xx robots.txt as a full disallow and stop crawling." % robots["status"],
            "Make /robots.txt return 200 with rules, or 404 if you have none. Never let it 5xx.",
            "Crawlers that cannot read the access policy assume they are not allowed in."))
    elif parsed:
        verdict_star, why = robots_verdict_for_agent(parsed, "*")
        if verdict_star == "blocked":
            findings.append(finding(
                "F-REACH-011", "robots.txt blocks all crawlers from the whole site", "critical",
                "robots.txt: %s. Every compliant crawler, including all AI retrieval bots, is locked out." % why,
                "Remove the blanket 'Disallow: /' under 'User-agent: *', or scope it to genuinely private paths only.",
                "The crawler must be let in before it can read anything (appendix concept A)."))
        blocked_retrieval = []
        blocked_training = []
        for agent in AI_AGENTS["retrieval"] + AI_AGENTS["user_fetch"]:
            v, _ = robots_verdict_for_agent(parsed, agent)
            if v == "blocked" and (agent in parsed.get("groups", {}) or verdict_star == "blocked"):
                blocked_retrieval.append(agent)
        for agent in AI_AGENTS["training"]:
            if agent in parsed.get("groups", {}):
                v, _ = robots_verdict_for_agent(parsed, agent)
                if v == "blocked":
                    blocked_training.append(agent)
        if blocked_retrieval and verdict_star != "blocked":
            findings.append(finding(
                "F-REACH-012", "robots.txt blocks AI answer and retrieval bots", "high",
                "Explicitly disallowed: %s. These agents fetch pages to build live AI answers; blocking them removes the site from those answers." % ", ".join(sorted(blocked_retrieval)),
                "Allow the retrieval and user-fetch agents (for example OAI-SearchBot, Claude-SearchBot, PerplexityBot, ChatGPT-User, Claude-User) even if you keep training bots blocked.",
                "Assistants cite pages their fetchers are allowed to reach (appendix concept B)."))
        if blocked_training and not blocked_retrieval:
            proactive.append({
                "id": "P-REACH-001",
                "summary": "Training bots (%s) are blocked while retrieval bots are allowed. This is a coherent policy; just confirm it is intentional, since it trades long-term model familiarity with the brand for content control." % ", ".join(sorted(blocked_training)),
                "priority": "low"})
    elif robots.get("status") in (401, 403, 429):
        proactive.append({
            "id": "P-REACH-005",
            "summary": "robots.txt could not be read (HTTP %s): the site refused the request, so its crawler policy is unknown rather than absent. Make /robots.txt readable by every client, including ones your bot protection does not recognise." % robots.get("status"),
            "priority": "medium"})
    else:
        proactive.append({
            "id": "P-REACH-002",
            "summary": "No robots.txt found (HTTP %s). Crawlers default to full access, so nothing is blocked, but adding one with a Sitemap line gives crawlers an explicit map and an explicit welcome." % robots.get("status"),
            "priority": "low"})

    # 2b. Login wall or paywall gating the main content.
    GATE_RE = re.compile(
        r"(sign ?in|log ?in|subscribe|become a member|create an account|register|start your free trial)\b"
        r"[^.<]{0,40}\b(to (read|continue|view|access|see|unlock)|for full access|to keep reading)"
        r"|this (article|content|story|page) is (for|available to|reserved for) (subscribers|members)"
        r"|members[\s-]only|subscribers?[\s-]only|\bpaywall\b", re.I)
    PAYWALL_SCHEMA_RE = re.compile(r'"isAccessibleForFree"\s*:\s*(false|"false")', re.I)
    gated = []
    for rec in origin_pages:
        html = read_page(args.cache, rec)
        if html and (GATE_RE.search(html) or PAYWALL_SCHEMA_RE.search(html)):
            gated.append(rec)
    if gated:
        on_key = any(r.get("role") in ("home", "product", "news", "faq") for r in gated)
        findings.append(finding(
            "F-REACH-050", "Main content appears to sit behind a login or paywall",
            "high" if on_key else "medium",
            "Gating language or an isAccessibleForFree:false flag was found on %d page(s), e.g. %s. A public crawler and answer-engine fetcher cannot pass a login or paywall, so the content behind it is not readable or citable." % (
                len(gated), gated[0].get("final_url")),
            "Expose a substantial free summary of each gated page to unauthenticated fetchers, or mark genuinely free content with isAccessibleForFree:true; keep the paywall on the full text if needed.",
            "AI fetchers arrive unauthenticated; anything visible only after sign-in or payment is invisible to them and gets attributed to whoever published it in the open (appendix concept A).",
            confidence="medium"))

    # 3. noindex directives on fetched pages. A noindex on a non-canonical alias
    # (its canonical points to a different URL) is correct deduplication, not a
    # defect, so those pages are skipped.
    def _norm_url(u):
        try:
            s = urllib.parse.urlsplit((u or "").strip())
            return (s.netloc or "").lower().replace("www.", "") + (s.path or "/").rstrip("/")
        except Exception:
            return (u or "").strip().rstrip("/")

    for rec in origin_pages:
        html = read_page(args.cache, rec)
        if not html:
            continue
        if rec.get("status") != 200:
            continue  # noindex on a 4xx/5xx block page is not a real directive
        header_robots = (rec.get("headers") or {}).get("x-robots-tag", "")
        meta_noindex = re.search(
            r"<meta[^>]+name=[\"']robots[\"'][^>]+content=[\"'][^\"']*noindex", html, re.I)
        if "noindex" in header_robots.lower() or meta_noindex:
            page_url = rec.get("final_url") or rec.get("url") or ""
            canon = re.findall(r"<link[^>]+rel=[\"']canonical[\"'][^>]*href=[\"']([^\"']+)", html, re.I)
            if canon and _norm_url(urllib.parse.urljoin(page_url, canon[0])) != _norm_url(page_url):
                continue  # non-canonical alias; noindex here is correct deduplication
            sev = "critical" if rec.get("role") == "home" else "high"
            where = "X-Robots-Tag header" if "noindex" in header_robots.lower() else "meta robots tag"
            findings.append(finding(
                "F-REACH-020", "noindex directive on %s page" % rec.get("role", "a"), sev,
                "%s carries noindex via %s. The page is excluded from every index that feeds search and AI answers." % (rec.get("final_url"), where),
                "Remove the noindex directive unless the page is genuinely private. Audit deploy configs; staging noindex flags often leak to production.",
                "An explicitly de-indexed page does not exist for retrieval systems."))
            break

    # 4. Redirect hygiene.
    if home and len(home.get("redirect_chain", [])) > 2:
        chain = " -> ".join([c["from"] for c in home["redirect_chain"]] + [home.get("final_url", "")])
        findings.append(finding(
            "F-REACH-030", "Homepage sits behind a long redirect chain", "medium",
            "%d hops before content: %s" % (len(home["redirect_chain"]), chain),
            "Redirect in a single hop from every legacy URL (http, www or non-www) straight to the canonical URL.",
            "Each hop costs latency and some fetchers give up midway; answer-engine fetchers work under tight timeouts.",
            confidence="high"))

    # 5. Canonical tag sanity on the homepage.
    if home:
        html = read_page(args.cache, home)
        if html:
            canon = re.findall(r"<link[^>]+rel=[\"']canonical[\"'][^>]*href=[\"']([^\"']+)", html, re.I)
            if len(canon) > 1 and len(set(canon)) > 1:
                findings.append(finding(
                    "F-REACH-031", "Conflicting canonical tags on the homepage", "medium",
                    "Multiple different canonicals declared: %s" % ", ".join(sorted(set(canon))[:3]),
                    "Emit exactly one canonical link tag per page, pointing at the preferred absolute URL.",
                    "Conflicting canonicals make crawlers unsure which URL represents the brand, diluting identity signals."))

    # 6. Sitemap availability.
    sm = m.get("sitemap") or {}
    if sm.get("status") != 200:
        findings.append(finding(
            "F-REACH-040", "No usable XML sitemap found", "medium",
            "Tried %s -> HTTP %s; robots.txt declares a sitemap: %s." % (sm.get("tried"), sm.get("status"), sm.get("declared_in_robots")),
            "Publish /sitemap.xml with canonical URLs and lastmod dates, and declare it in robots.txt with a Sitemap: line.",
            "Sitemaps are how crawlers find pages that navigation does not surface, and lastmod is a freshness signal.",
            confidence="high"))
    elif not sm.get("declared_in_robots"):
        proactive.append({
            "id": "P-REACH-003",
            "summary": "A sitemap exists at %s but robots.txt does not declare it. Add a 'Sitemap:' line so every crawler finds it without guessing." % sm.get("tried"),
            "priority": "low"})

    # 7. llms.txt: honest, evidence-based note only. Absence is not a defect:
    # as of 2026 no major AI provider confirms consuming it in production.
    llms = m.get("llms_txt") or {}
    if not llms.get("present"):
        proactive.append({
            "id": "P-REACH-004",
            "summary": "No /llms.txt. This is optional: no major AI provider has confirmed using it, so treat it as a cheap, low-risk curated index for agent tooling, not a fix for visibility problems. Prioritize the actual findings first.",
            "priority": "low"})

    print(json.dumps({"module": "reach", "findings": findings, "proactive": proactive,
                      "stats": {"pages_checked": len(origin_pages)}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
