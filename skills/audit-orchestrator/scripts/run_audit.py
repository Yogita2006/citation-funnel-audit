#!/usr/bin/env python3
"""Citation Funnel audit orchestrator.

Runs the full pipeline: one polite crawl, then every analysis module from the
sibling skills (resolved through marketplace.json), then merges their findings
into the single audit report required by the contest schema.

Usage:
    python3 run_audit.py https://example.com --out report.json --markdown report.md

Deterministic: same crawl snapshot in, same report out. Read-only: GET
requests only, robots.txt honored, politeness delay between fetches.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
FUNNEL_STAGES = [
    ("reach", "Reach: can AI crawlers and fetchers get in?"),
    ("render", "Read: does the content exist without JavaScript?"),
    ("quotability", "Quote: can a machine lift a clean fact?"),
    ("trust", "Trust: is it fresh, corroborated, unambiguous?"),
    ("engagement", "Retain: does the arriving visitor stay?"),
]
SEV_WEIGHT = {"critical": 45, "high": 25, "medium": 10, "low": 4}

MODULES = {
    "reach": ("reach-audit", "scripts/check_reach.py"),
    "render": ("render-parity-audit", "scripts/check_render.py"),
    "quotability": ("quotability-audit", "scripts/check_quotability.py"),
    "trust": ("trust-signals-audit", "scripts/check_trust.py"),
    "engagement": ("engagement-audit", "scripts/check_engagement.py"),
}


def find_marketplace_root(start):
    d = os.path.abspath(start)
    for _ in range(6):
        if os.path.exists(os.path.join(d, "marketplace.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    raise SystemExit("marketplace.json not found above " + start)


def resolve_skill_paths(root):
    with open(os.path.join(root, "marketplace.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    return {s["id"]: os.path.join(root, s["path"]) for s in manifest["skills"]}


def run_module(script_path, cache):
    try:
        proc = subprocess.run(
            [sys.executable, script_path, "--cache", cache],
            capture_output=True, text=True, timeout=90)
        if proc.returncode != 0:
            return {"findings": [], "proactive": [],
                    "stats": {"error": (proc.stderr or "nonzero exit").strip()[:300]}}
        return json.loads(proc.stdout)
    except Exception as e:
        return {"findings": [], "proactive": [], "stats": {"error": "%s: %s" % (type(e).__name__, e)}}


def stage_score(findings):
    score = 100
    for f in findings:
        score -= SEV_WEIGHT.get(f.get("severity"), 0)
    return max(score, 0)


def to_markdown(report):
    lines = ["# Citation Funnel Audit: %s" % report["site"], "",
             "Audited at %s. %d findings (%d critical, %d high, %d medium, %d low)." % (
                 report["audited_at"], report["summary"]["total_findings"],
                 report["summary"]["critical"], report["summary"]["high"],
                 report["summary"]["medium"], report["summary"]["low"]), ""]
    prof = report.get("site_profile") or {}
    if prof.get("type"):
        lines += ["Detected site type: **%s** (%s confidence). Checks are tuned to this type."
                  % (prof["type"], prof.get("confidence", "low")), ""]
    lines += ["## Where the site falls out of the funnel", ""]
    if any(s.get("score") is None for s in report["funnel"]):
        lines += ["_Site unreachable: no page returned HTTP 200, so only the Reach gate could be "
                  "evaluated; the content gates are marked N/A rather than scored._", ""]
    for stage in report["funnel"]:
        sc = stage.get("score")
        bar = ("." * 10) if sc is None else ("#" * (sc // 10) + "." * (10 - sc // 10))
        label = "   N/A " if sc is None else "%3d/100" % sc
        lines.append("- `%s` %s  %s" % (bar, label, stage["question"]))
    lines += ["", "## Findings (highest impact first)", ""]
    for f in report["findings"]:
        lines += ["### %s — %s" % (f["id"], f["title"]), "",
                  "**Severity:** %s" % f["severity"].capitalize(), "",
                  "**Evidence:** %s" % f["evidence"], "",
                  "**Why it matters:** %s" % f.get("mechanism", ""), "",
                  "**Fix (priority %s):** %s" % (f["suggested_action"]["priority"],
                                                 f["suggested_action"]["summary"]), ""]
    if report.get("proactive_recommendations"):
        lines += ["## Beyond the defects: proactive improvements", ""]
        for p in report["proactive_recommendations"]:
            lines.append("- (%s) %s" % (p["priority"], p["summary"]))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Run the full Citation Funnel website audit.")
    ap.add_argument("url", help="Website URL or bare domain")
    ap.add_argument("--out", default="audit-report.json", help="Path for the JSON report")
    ap.add_argument("--markdown", default=None, help="Optional path for a human-readable report")
    ap.add_argument("--html", default=None, help="Optional path for an interactive self-contained HTML report")
    ap.add_argument("--cache", default=None, help="Reuse or create this crawl cache directory")
    ap.add_argument("--max-pages", type=int, default=8)
    args = ap.parse_args()

    started = time.time()
    here = os.path.dirname(os.path.abspath(__file__))
    root = find_marketplace_root(here)
    skills = resolve_skill_paths(root)
    cache = args.cache or tempfile.mkdtemp(prefix="cfa-cache-")

    # 1. Crawl once; every module reads the same snapshot.
    if not os.path.exists(os.path.join(cache, "manifest.json")):
        crawl = os.path.join(here, "crawl_site.py")
        proc = subprocess.run([sys.executable, crawl, args.url, "--cache", cache,
                               "--max-pages", str(args.max_pages)],
                              capture_output=True, text=True, timeout=240)
        if proc.returncode != 0:
            raise SystemExit("crawl failed: " + (proc.stderr or proc.stdout)[:500])
        print("crawl: " + proc.stdout.strip(), file=sys.stderr)

    with open(os.path.join(cache, "manifest.json"), encoding="utf-8") as f:
        crawl_manifest = json.load(f)

    # 1b. Detect site type once, so every gate can make its checks conditional
    # instead of scoring a blog against an ecommerce checklist.
    if not os.path.exists(os.path.join(cache, "profile.json")):
        detect = os.path.join(here, "detect_profile.py")
        subprocess.run([sys.executable, detect, "--cache", cache],
                       capture_output=True, text=True, timeout=60)
    site_profile = {}
    profile_file = os.path.join(cache, "profile.json")
    if os.path.exists(profile_file):
        with open(profile_file, encoding="utf-8") as f:
            site_profile = json.load(f)
    if site_profile.get("type"):
        print("profile: type=%s (%s)" % (site_profile["type"], site_profile.get("confidence")),
              file=sys.stderr)

    # 2. Run every analysis module.
    # A site is "reachable" only if at least one crawled page returned HTTP 200.
    # When it is not, the four content gates (Read/Quote/Trust/Retain) have no
    # page text to judge, so they are marked N/A rather than scored 100 (which
    # would read as a clean pass). Reach still scores, because it evaluates
    # robots, status and sitemap without needing page content. Reachable sites
    # always have the 200 homepage, so this never affects them.
    reachable = any(p.get("status") == 200 for p in crawl_manifest.get("pages", []))
    CONTENT_GATES = {"render", "quotability", "trust", "engagement"}
    findings, proactive, funnel, module_stats = [], [], [], {}
    for stage_key, question in FUNNEL_STAGES:
        skill_id, rel = MODULES[stage_key]
        result = run_module(os.path.join(skills[skill_id], rel), cache)
        stage_findings = result.get("findings", [])
        findings += stage_findings
        proactive += result.get("proactive", [])
        module_stats[stage_key] = result.get("stats", {})
        entry = {"stage": stage_key, "question": question, "findings": len(stage_findings)}
        if not reachable and stage_key in CONTENT_GATES:
            entry["score"] = None
            entry["note"] = "not evaluated: site unreachable (no page returned HTTP 200)"
        else:
            entry["score"] = stage_score(stage_findings)
        funnel.append(entry)
        print("module %-12s findings=%d" % (stage_key, len(stage_findings)), file=sys.stderr)

    # 3. Merge deterministically: severity first, then stable id.
    findings.sort(key=lambda f: (SEV_ORDER.get(f.get("severity"), 9), f["id"]))
    seen = set()
    findings = [f for f in findings if not (f["id"] in seen or seen.add(f["id"]))]
    prio_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    proactive.sort(key=lambda p: (prio_order.get(p.get("priority"), 9), p["id"]))

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    report = {
        "site": crawl_manifest.get("site"),
        "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "site_profile": site_profile,
        "summary": {"total_findings": len(findings), **counts},
        "funnel": funnel,
        "findings": findings,
        "proactive_recommendations": proactive,
        "audit_meta": {
            "marketplace": "citation-funnel-audit/1.7.0",
            "pages_crawled": len(crawl_manifest.get("pages", [])),
            "crawl_notes": crawl_manifest.get("notes", []),
            "module_stats": module_stats,
            "elapsed_seconds": round(time.time() - started, 1),
            "read_only": True,
        },
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(to_markdown(report))

    if args.html:
        sys.path.insert(0, here)
        from report_html import render_html
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(render_html(report))

    print(json.dumps({"ok": True, "report": args.out,
                      "total_findings": len(findings), **counts,
                      "elapsed_seconds": report["audit_meta"]["elapsed_seconds"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
