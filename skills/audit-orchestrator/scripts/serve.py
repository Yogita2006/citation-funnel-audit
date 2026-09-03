#!/usr/bin/env python3
"""Local web UI for the Citation Funnel audit (standard library only).

Type a URL and get the interactive dashboard, or compare two sites side by
side. No Flask, no external packages, just http.server. It runs the same
run_audit.py engine the CLI uses and renders the same dashboard/compare views,
so there is one audit engine behind every interface. Light theme: navy,
pistachio, white.

    python3 serve.py                 # then open http://127.0.0.1:8000
    python3 serve.py --port 9000

Read-only and local by design: binds to 127.0.0.1 only, URLs are passed to the
auditor as single arguments (no shell), the audit is GET-only and honors
robots.txt.
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_AUDIT = os.path.join(HERE, "run_audit.py")
AUDIT_TIMEOUT = 260

LANDING_TMPL = """<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>AI Visibility Auditor</title><style>
:root{--bg:#eef4f0;--card:#ffffff;--ink:#15324f;--mut:#5c7185;--line:#dce6df;--navy:#1c4e8a;--pista:#7cbf86}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);
color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:20px}
.wrap{width:100%;max-width:540px}
h1{font-size:22px;margin:0 0 4px;text-align:center;color:var(--navy)}
.tag{color:var(--mut);font-size:13px;text-align:center;margin:0 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 2px 10px rgba(21,50,79,.06)}
.tabs{display:flex;gap:6px;margin-bottom:16px}
.tab{flex:1;text-align:center;background:#f1f5f2;border:1px solid var(--line);color:var(--mut);border-radius:10px;padding:8px;font-size:13px;cursor:pointer}
.tab.on{background:var(--navy);border-color:var(--navy);color:#fff;font-weight:600}
input{width:100%;background:#f7faf8;border:1px solid var(--line);color:var(--ink);border-radius:10px;padding:12px 14px;font-size:16px;outline:none}
input:focus{border-color:var(--navy);background:#fff}
input+input{margin-top:10px}
.row{display:flex;gap:10px;align-items:center;margin-top:12px}
label{color:var(--mut);font-size:13px;display:flex;align-items:center;gap:6px}
select{background:#f7faf8;border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:6px 8px;font-size:13px}
button.go{margin-left:auto;background:var(--navy);border:none;color:#fff;font-weight:700;border-radius:10px;padding:12px 18px;font-size:15px;cursor:pointer}
button.go:hover{background:#163f70}
.note{background:#fdecea;border:1px solid #f5c6c0;color:#a12d21;border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:14px}
.foot{color:var(--mut);font-size:12px;text-align:center;margin-top:16px}
.hidden{display:none}
#ov{display:none;position:fixed;inset:0;background:rgba(238,244,240,.94);flex-direction:column;
align-items:center;justify-content:center;text-align:center;padding:24px;z-index:50}
.spin{width:44px;height:44px;border:4px solid #d7e3da;border-top-color:var(--navy);border-radius:50%;
animation:sp 0.9s linear infinite;margin-bottom:16px}
@keyframes sp{to{transform:rotate(360deg)}}
.ovt{font-size:16px;font-weight:600;color:var(--navy)}
.ovu{color:var(--navy)}
.ovs{color:var(--mut);font-size:13px;margin-top:6px;max-width:380px}
</style></head><body>
<div class='wrap'>
<h1>AI Visibility Auditor</h1>
<p class='tag'>Can AI assistants find, read, quote and trust this site?</p>
<div class='card'>
{{NOTE}}
<div class='tabs'>
<div class='tab on' id='t1' onclick="mode('single')">Single site</div>
<div class='tab' id='t2' onclick="mode('compare')">Compare two</div>
</div>
<form action='/audit' method='get' id='fSingle'>
<input name='url' placeholder='example.com' autofocus autocomplete='off' spellcheck='false'>
<div class='row'><label>Pages
<select name='max_pages'><option>5</option><option selected>8</option><option>12</option></select></label>
<button class='go' type='submit'>Audit &rarr;</button></div>
</form>
<form action='/compare' method='get' id='fCompare' class='hidden'>
<input name='a' placeholder='your-site.com' autocomplete='off' spellcheck='false'>
<input name='b' placeholder='competitor.com' autocomplete='off' spellcheck='false'>
<div class='row'><label>Pages each
<select name='max_pages'><option>5</option><option selected>8</option><option>12</option></select></label>
<button class='go' type='submit'>Compare &rarr;</button></div>
</form>
</div>
<p class='foot'>Read-only &middot; runs locally &middot; the same five-gate engine as the CLI</p>
</div>
<div id='ov'><div class='spin'></div>
<div class='ovt'>Auditing <span class='ovu' id='ovu'></span></div>
<div class='ovs' id='ovs'>Crawling and running the five gates &mdash; usually 30 to 90 seconds.</div></div>
<script>
function mode(m){var s=m==='single';
  document.getElementById('t1').classList.toggle('on',s);
  document.getElementById('t2').classList.toggle('on',!s);
  document.getElementById('fSingle').classList.toggle('hidden',!s);
  document.getElementById('fCompare').classList.toggle('hidden',s);}
function ovshow(t,extra){document.getElementById('ovu').textContent=t;
  if(extra){document.getElementById('ovs').textContent=extra;}
  document.getElementById('ov').style.display='flex';}
document.getElementById('fSingle').addEventListener('submit',function(){
  var u=(this.url.value||'').trim(); if(!u){return;} ovshow(u);});
document.getElementById('fCompare').addEventListener('submit',function(){
  var a=(this.a.value||'').trim(),b=(this.b.value||'').trim(); if(!a||!b){return;}
  ovshow(a+' vs '+b,'Auditing two sites \\u2014 this takes about twice as long.');});
</script></body></html>"""


def landing_page(msg=""):
    note = "<div class='note'>" + html.escape(msg) + "</div>" if msg else ""
    return LANDING_TMPL.replace("{{NOTE}}", note)


def error_page(url, detail):
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Audit failed</title><style>"
            "body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;"
            "background:#eef4f0;color:#15324f;font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;padding:24px}"
            ".c{max-width:520px;background:#fff;border:1px solid #dce6df;border-radius:16px;padding:22px;box-shadow:0 2px 10px rgba(21,50,79,.06)}"
            "h2{margin:0 0 8px;font-size:18px;color:#1c4e8a} .m{color:#5c7185;font-size:13px}"
            ".d{background:#fdecea;border:1px solid #f5c6c0;border-radius:10px;padding:10px;margin:12px 0;"
            "font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#a12d21;white-space:pre-wrap;word-break:break-word}"
            "a{color:#1c4e8a;text-decoration:none;font-weight:600}</style></head><body><div class='c'>"
            "<h2>Could not audit " + html.escape(url) + "</h2>"
            "<div class='m'>The site may be unreachable, blocking automated fetches, or too slow.</div>"
            "<div class='d'>" + html.escape(detail) + "</div>"
            "<a href='/'>&#8592; Try again</a></div></body></html>")


def with_banner(doc, url):
    bar = ("<div style=\"position:sticky;top:0;z-index:9;background:#fff;border-bottom:1px solid #dce6df;"
           "padding:8px 16px;font:13px -apple-system,Segoe UI,Roboto,sans-serif;color:#5c7185\">"
           "<a href='/' style='color:#1c4e8a;text-decoration:none;font-weight:600'>&#8592; New audit</a>"
           "<span style='margin-left:12px'>Audited: <b style='color:#15324f'>" + html.escape(url) + "</b></span></div>")
    return doc.replace("<body>", "<body>" + bar, 1)


def valid_url(raw):
    raw = (raw or "").strip()
    if not raw or len(raw) > 300 or re.search(r"\s", raw):
        return None
    probe = raw if re.match(r"^https?://", raw, re.I) else "https://" + raw
    host = urllib.parse.urlsplit(probe).netloc
    if not host or "." not in host:
        return None
    return raw


def _audit(url, max_pages, want_html):
    tmp = tempfile.mkdtemp(prefix="cfa-web-")
    out_json = os.path.join(tmp, "r.json")
    cmd = [sys.executable, RUN_AUDIT, url, "--out", out_json, "--max-pages", max_pages]
    out_html = os.path.join(tmp, "r.html")
    if want_html:
        cmd += ["--html", out_html]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=AUDIT_TIMEOUT)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "audit failed").strip()[:400])
    if want_html:
        with open(out_html, encoding="utf-8") as f:
            return f.read()
    with open(out_json, encoding="utf-8") as f:
        return json.load(f)


class Handler(BaseHTTPRequestHandler):
    server_version = "CitationFunnelUI/1.0"

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if body:
            self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stderr.write("[serve] " + (fmt % args) + "\n")

    def _pages(self, q):
        try:
            return str(max(1, min(int((q.get("max_pages") or ["8"])[0]), 15)))
        except ValueError:
            return "8"

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/":
            self._send(200, landing_page())
        elif parsed.path == "/favicon.ico":
            self._send(204, "")
        elif parsed.path == "/audit":
            url = valid_url((q.get("url") or [""])[0])
            if not url:
                self._send(400, landing_page("Please enter a valid website URL, for example example.com"))
                return
            try:
                dashboard = _audit(url, self._pages(q), want_html=True)
            except subprocess.TimeoutExpired:
                self._send(504, error_page(url, "The audit took too long and was stopped. Try fewer pages or a smaller site."))
                return
            except Exception as ex:
                self._send(500, error_page(url, "%s: %s" % (type(ex).__name__, ex)))
                return
            self._send(200, with_banner(dashboard, url))
        elif parsed.path == "/compare":
            a = valid_url((q.get("a") or [""])[0])
            b = valid_url((q.get("b") or [""])[0])
            if not a or not b:
                self._send(400, landing_page("Please enter two valid website URLs to compare."))
                return
            mp = self._pages(q)
            try:
                ra = _audit(a, mp, want_html=False)
                rb = _audit(b, mp, want_html=False)
            except subprocess.TimeoutExpired:
                self._send(504, error_page(a + " / " + b, "One of the audits took too long and was stopped."))
                return
            except Exception as ex:
                self._send(500, error_page(a + " / " + b, "%s: %s" % (type(ex).__name__, ex)))
                return
            sys.path.insert(0, HERE)
            from report_html import render_compare
            self._send(200, with_banner(render_compare(ra, rb, a, b), a + " vs " + b))
        else:
            self._send(404, landing_page("Page not found."))


def main():
    ap = argparse.ArgumentParser(description="Local web UI for the Citation Funnel audit.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1", help="Bind address (default localhost only)")
    args = ap.parse_args()
    try:
        srv = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as e:
        print("Could not start on %s:%d (%s). Try another port: python3 serve.py --port 9001"
              % (args.host, args.port, e))
        return 1
    url = "http://%s:%d" % (args.host, args.port)
    print("Citation Funnel Audit - local UI running at " + url)
    print("Open that address in your browser. Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
