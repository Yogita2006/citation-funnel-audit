#!/usr/bin/env python3
"""Compare the AI visibility of two sites side by side.

Runs the full audit on both sites (same engine as run_audit.py) and writes an
interactive HTML page with their funnel scores next to each other, the gap on
each gate, and the biggest gap called out. Standard library only.

    python3 compare.py your-site.com competitor.com --out compare.html
    python3 compare.py a.com b.com --out compare.html --max-pages 6
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_AUDIT = os.path.join(HERE, "run_audit.py")


def audit_json(url, max_pages):
    tmp = tempfile.mkdtemp(prefix="cfa-cmp-")
    out = os.path.join(tmp, "r.json")
    proc = subprocess.run(
        [sys.executable, RUN_AUDIT, url, "--out", out, "--max-pages", str(max_pages)],
        capture_output=True, text=True, timeout=260)
    if proc.returncode != 0 or not os.path.exists(out):
        raise SystemExit("audit failed for %s: %s" % (url, (proc.stderr or proc.stdout or "")[:300]))
    with open(out, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="Compare two sites' AI visibility.")
    ap.add_argument("site_a")
    ap.add_argument("site_b")
    ap.add_argument("--out", default="compare.html", help="Output HTML path")
    ap.add_argument("--max-pages", type=int, default=8)
    args = ap.parse_args()

    sys.path.insert(0, HERE)
    from report_html import render_compare

    print("Auditing %s ..." % args.site_a, file=sys.stderr)
    ra = audit_json(args.site_a, args.max_pages)
    print("Auditing %s ..." % args.site_b, file=sys.stderr)
    rb = audit_json(args.site_b, args.max_pages)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render_compare(ra, rb, args.site_a, args.site_b))
    print("wrote " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
