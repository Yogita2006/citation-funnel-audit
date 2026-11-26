#!/usr/bin/env python3
"""Render an audit report as a single self-contained interactive HTML page,
and render a side-by-side comparison of two audits.

No external assets, no CDN, no build step: inline CSS and vanilla JS only, so
the file opens straight in any browser and keeps the project's zero-dependency
promise. Findings pre-render as HTML (readable with JavaScript off); tapping a
funnel gate or a chip filters, evidence expands, a fix copies, the JSON
downloads. Light theme: navy blue, pistachio green, white.

Used by run_audit.py via --html and by compare.py / serve.py, and runnable:
    python3 report_html.py audit-report.json audit-report.html
"""

import html as _html
import json

SEV_COLORS = {"critical": "#c0392b", "high": "#d97b2e", "medium": "#b8860b", "low": "#64748b"}
LABEL = {"reach": "Reach", "render": "Read", "quotability": "Quote",
         "trust": "Trust", "engagement": "Retain"}


def score_color(s):
    return "#4f9d5a" if s >= 80 else ("#c9902a" if s >= 60 else "#c0392b")


CSS = """
:root{--bg:#ffffff;--panel:#f4f8f5;--ink:#15324f;--mut:#5c7185;--line:#e2e8ee;
--navy:#1c4e8a;--pista:#7cbf86;--pista-soft:#eaf5ec;--good:#4f9d5a}
*{box-sizing:border-box}
body{margin:0 auto;max-width:900px;background:var(--bg);color:var(--ink);padding:16px;
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
h1{font-size:20px;margin:0 0 2px;color:var(--navy)}
.sub{color:var(--mut);font-size:13px;margin:2px 0 10px}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.badge{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:4px 10px;font-size:12px;color:var(--mut)}
.badge b{color:var(--ink)}
.tools{display:flex;gap:8px;margin:10px 0 4px}
.tools button{background:#fff;border:1px solid var(--line);color:var(--navy);border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer}
.tools button:hover{border-color:var(--navy)}
#funnel{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:10px 0 14px}
.gate{text-align:left;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;cursor:pointer;color:var(--ink)}
.gate.sel{border-color:var(--navy);box-shadow:0 0 0 1px var(--navy)}
.gate-top{display:flex;justify-content:space-between;align-items:baseline}
.gate-name{font-weight:600}
.gate-score{font-weight:700;font-variant-numeric:tabular-nums}
.bar{height:7px;background:#e9eef4;border-radius:6px;margin:6px 0;overflow:hidden}
.bar-fill{height:100%}
.gate-q{color:var(--mut);font-size:11px}
.controls{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:6px 0}
.controls .lbl{color:var(--mut);font-size:12px;margin-right:2px}
.chip{background:#fff;border:1px solid var(--line);color:var(--mut);border-radius:999px;padding:4px 10px;font-size:12px;cursor:pointer}
.chip.active{background:var(--navy);border-color:var(--navy);color:#fff;font-weight:600}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px;box-shadow:0 1px 2px rgba(21,50,79,.05)}
.card-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pill{color:#fff;font-size:11px;font-weight:700;border-radius:6px;padding:2px 7px;letter-spacing:.3px}
.gate-tag{font-size:11px;color:var(--mut);border:1px solid var(--line);border-radius:6px;padding:1px 6px}
.fid{font-size:11px;color:var(--mut);font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.title{font-weight:600;flex:1 1 100%;color:var(--ink)}
.why{font-size:13px;margin:8px 0}
.ev-toggle{background:none;border:none;color:var(--navy);cursor:pointer;font-size:12px;padding:0;margin:2px 0}
.evidence{display:none;white-space:pre-wrap;word-break:break-word;background:var(--pista-soft);border:1px solid var(--line);
border-radius:8px;padding:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:#3f5a49;margin:6px 0}
.evidence.open{display:block}
.fix{display:flex;gap:8px;align-items:flex-start;margin-top:8px}
.fix-text{font-size:13px;flex:1}
.copy{white-space:nowrap;background:#fff;border:1px solid var(--line);color:var(--navy);border-radius:8px;padding:6px 10px;cursor:pointer;font-size:12px}
.copy.ok{border-color:var(--good);color:var(--good)}
.section{margin:20px 0 8px;font-size:15px;font-weight:700;color:var(--navy)}
.pro{list-style:none;padding:0;margin:0}
.pro li{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 10px;margin-bottom:8px;font-size:13px}
.ppri{font-size:11px;color:var(--mut);text-transform:uppercase;margin-right:6px}
.empty{color:var(--mut);font-size:13px;padding:12px}
.foot{color:var(--mut);font-size:12px;margin-top:20px;border-top:1px solid var(--line);padding-top:10px}
"""

JS = """
var G='all',S='all';
function apply(){
  var shown=0;
  document.querySelectorAll('.card').forEach(function(c){
    var ok=(G==='all'||c.dataset.gate===G)&&(S==='all'||c.dataset.sev===S);
    c.style.display=ok?'':'none'; if(ok)shown++;
  });
  document.querySelectorAll('.gate').forEach(function(g){g.classList.toggle('sel',g.dataset.gate===G);});
  var em=document.getElementById('empty'); if(em)em.style.display=shown?'none':'block';
}
function syncChips(){
  document.querySelectorAll('[data-gchip]').forEach(function(b){b.classList.toggle('active',b.dataset.gchip===G);});
  document.querySelectorAll('[data-schip]').forEach(function(b){b.classList.toggle('active',b.dataset.schip===S);});
}
function setGate(g){G=(G===g?'all':g);syncChips();apply();}
function setGateChip(g){G=g;syncChips();apply();}
function setSev(s){S=s;syncChips();apply();}
function tog(b){var e=b.nextElementSibling;var o=e.classList.toggle('open');b.innerHTML=o?'Hide evidence &#9662;':'Show evidence &#9656;';}
function done(b){var o=b.textContent;b.textContent='Copied!';b.classList.add('ok');setTimeout(function(){b.textContent=o;b.classList.remove('ok');},1200);}
function fbk(t,b){var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();try{document.execCommand('copy');}catch(e){}document.body.removeChild(a);done(b);}
function cp(b){var t=b.getAttribute('data-fix');if(navigator.clipboard){navigator.clipboard.writeText(t).then(function(){done(b);},function(){fbk(t,b);});}else{fbk(t,b);}}
function dl(){var s=document.getElementById('raw').textContent;var bl=new Blob([s],{type:'application/json'});var u=URL.createObjectURL(bl);var a=document.createElement('a');a.href=u;a.download='audit-report.json';a.click();URL.revokeObjectURL(u);}
syncChips();apply();
"""


def render_html(report):
    e = _html.escape
    s = report.get("summary", {})
    prof = report.get("site_profile") or {}
    meta = report.get("audit_meta", {})

    fbits = []
    for st in report.get("funnel", []):
        stage = st.get("stage", "")
        label = LABEL.get(stage, stage.title())
        # A gate that could not be evaluated (unreachable site) has score None:
        # show N/A with an empty bar instead of a misleading number.
        raw_score = st.get("score")
        score = 0 if raw_score is None else int(raw_score)
        shown = "N/A" if raw_score is None else str(score)
        fbits.append(
            '<button class="gate" data-gate="%s" onclick="setGate(\'%s\')">'
            '<div class="gate-top"><span class="gate-name">%s</span><span class="gate-score">%s</span></div>'
            '<div class="bar"><div class="bar-fill" style="width:%d%%;background:%s"></div></div>'
            '<div class="gate-q">%s</div></button>'
            % (stage, stage, label, shown, score, score_color(score), e(st.get("question", "")))
        )

    gate_chips = ['<button class="chip active" data-gchip="all" onclick="setGateChip(\'all\')">All gates</button>']
    for k in ["reach", "render", "quotability", "trust", "engagement"]:
        gate_chips.append('<button class="chip" data-gchip="%s" onclick="setGateChip(\'%s\')">%s</button>' % (k, k, LABEL[k]))
    sev_chips = ['<button class="chip active" data-schip="all" onclick="setSev(\'all\')">All</button>']
    for sv in ["critical", "high", "medium", "low"]:
        sev_chips.append('<button class="chip" data-schip="%s" onclick="setSev(\'%s\')">%s (%d)</button>'
                         % (sv, sv, sv.title(), s.get(sv, 0)))

    cbits = []
    for f in report.get("findings", []):
        cat = f.get("category", "")
        sev = f.get("severity", "low")
        fx = f.get("suggested_action", {}) or {}
        cbits.append(
            '<div class="card" data-gate="%s" data-sev="%s">'
            '<div class="card-head">'
            '<span class="pill" style="background:%s">%s</span>'
            '<span class="gate-tag">%s</span>'
            '<span class="fid">%s</span>'
            '<span class="title">%s</span></div>'
            '<div class="why"><b>Why it matters:</b> %s</div>'
            '<button class="ev-toggle" onclick="tog(this)">Show evidence &#9656;</button>'
            '<div class="evidence">%s</div>'
            '<div class="fix"><div class="fix-text"><b>Fix (%s priority):</b> %s</div>'
            '<button class="copy" data-fix="%s" onclick="cp(this)">Copy fix</button></div>'
            '</div>'
            % (e(cat), e(sev), SEV_COLORS.get(sev, "#64748b"), sev.upper(),
               e(LABEL.get(cat, cat)), e(f.get("id", "")), e(f.get("title", "")),
               e(f.get("mechanism", "")), e(f.get("evidence", "")),
               e(str(fx.get("priority", ""))), e(fx.get("summary", "")), e(fx.get("summary", "")))
        )
    if not cbits:
        cbits.append('<div class="empty">No defect findings on the sampled pages.</div>')

    pbits = []
    for p in report.get("proactive_recommendations", []):
        pbits.append('<li><span class="ppri">%s</span>%s</li>' % (e(str(p.get("priority", ""))), e(p.get("summary", ""))))
    pro_html = ('<div class="section">Beyond the defects: proactive improvements</div>'
                '<ul class="pro">' + "".join(pbits) + '</ul>') if pbits else ""

    prof_badge = ""
    if prof.get("type"):
        prof_badge = '<span class="badge">Site type: <b>%s</b> (%s)</span>' % (
            e(prof.get("type", "")), e(prof.get("confidence", "")))

    raw = json.dumps(report, indent=2).replace("</", "<\\/")

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Citation Funnel Audit: " + e(report.get("site", "")) + "</title>"
        "<style>" + CSS + "</style></head><body>"
        "<h1>Citation Funnel Audit</h1>"
        "<div class='sub'>" + e(report.get("site", "")) + " &middot; audited " + e(report.get("audited_at", "")) + "</div>"
        "<div class='badges'>"
        "<span class='badge'>Findings <b>" + str(s.get("total_findings", 0)) + "</b></span>"
        "<span class='badge'>Critical <b>" + str(s.get("critical", 0)) + "</b></span>"
        "<span class='badge'>High <b>" + str(s.get("high", 0)) + "</b></span>"
        "<span class='badge'>Medium <b>" + str(s.get("medium", 0)) + "</b></span>"
        "<span class='badge'>Low <b>" + str(s.get("low", 0)) + "</b></span>" + prof_badge +
        "</div>"
        "<div class='tools'><button onclick='dl()'>Download report JSON</button></div>"
        "<div class='sub'>Tap a gate to filter findings to that stage of the funnel.</div>"
        "<div id='funnel'>" + "".join(fbits) + "</div>"
        "<div class='controls'><span class='lbl'>Gate:</span>" + "".join(gate_chips) + "</div>"
        "<div class='controls'><span class='lbl'>Severity:</span>" + "".join(sev_chips) + "</div>"
        "<div id='findings'>" + "".join(cbits) + "</div>"
        "<div id='empty' class='empty' style='display:none'>No findings match this filter.</div>" + pro_html +
        "<div class='foot'>Read-only audit &middot; " + str(meta.get("pages_crawled", "?")) +
        " pages crawled &middot; " + str(meta.get("elapsed_seconds", "?")) + "s &middot; " +
        e(str(meta.get("marketplace", "citation-funnel-audit"))) + "</div>"
        "<script id='raw' type='application/json'>" + raw + "</script>"
        "<script>" + JS + "</script></body></html>"
    )


COMPARE_CSS = """
:root{--bg:#ffffff;--panel:#f4f8f5;--ink:#15324f;--mut:#5c7185;--line:#e2e8ee;--navy:#1c4e8a;--pista:#7cbf86}
*{box-sizing:border-box}
body{margin:0 auto;max-width:820px;background:var(--bg);color:var(--ink);padding:16px;
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
h1{font-size:20px;margin:0 0 2px;color:var(--navy)}
.sub{color:var(--mut);font-size:13px;margin:2px 0 12px}
.legend{display:flex;gap:16px;font-size:13px;margin-bottom:14px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.dot{width:12px;height:12px;border-radius:3px;display:inline-block}
.overall{display:flex;gap:10px;margin-bottom:16px}
.oc{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center}
.oc .n{font-size:13px;color:var(--mut);word-break:break-word}
.oc .v{font-size:28px;font-weight:800;font-variant-numeric:tabular-nums}
.insight{background:#eaf5ec;border:1px solid #cfe6d3;border-radius:12px;padding:12px;font-size:14px;margin-bottom:16px;color:#2f5a3a}
.row{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px;box-shadow:0 1px 2px rgba(21,50,79,.05)}
.row .g{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.gname{font-weight:700}
.delta{font-size:12px;font-weight:700;border-radius:6px;padding:2px 8px}
.pair{display:grid;grid-template-columns:88px 1fr 40px;gap:8px;align-items:center;margin:4px 0;font-size:12px}
.pair .who{color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.track{height:12px;background:#e9eef4;border-radius:6px;overflow:hidden}
.fill{height:100%}
.pair .sc{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.foot{color:var(--mut);font-size:12px;margin-top:18px;border-top:1px solid var(--line);padding-top:10px}
"""


def render_compare(a, b, label_a=None, label_b=None):
    e = _html.escape
    la = e(label_a or a.get("site") or "Site A")
    lb = e(label_b or b.get("site") or "Site B")
    # An unevaluated gate (score None, unreachable site) counts as 0 in a comparison.
    sa = {st.get("stage"): int(st.get("score") or 0) for st in a.get("funnel", [])}
    sb = {st.get("stage"): int(st.get("score") or 0) for st in b.get("funnel", [])}
    stages = [st.get("stage") for st in a.get("funnel", [])] or list(sa.keys())

    def overall(sc):
        v = list(sc.values())
        return round(sum(v) / len(v)) if v else 0
    oa, ob = overall(sa), overall(sb)

    gaps = [(st, sa.get(st, 0) - sb.get(st, 0)) for st in stages]
    if gaps and min(g[1] for g in gaps) < 0:
        st, d = min(gaps, key=lambda x: x[1])
        insight = "Biggest gap: <b>%s</b> &mdash; %s is %d points behind %s here." % (LABEL.get(st, st), la, abs(d), lb)
    elif gaps and max(g[1] for g in gaps) > 0:
        st, d = max(gaps, key=lambda x: x[1])
        insight = "%s leads most on <b>%s</b> (+%d)." % (la, LABEL.get(st, st), d)
    else:
        insight = "The two sites score almost identically across the funnel."

    rows = []
    for st in stages:
        va, vb = sa.get(st, 0), sb.get(st, 0)
        d = va - vb
        if d > 0:
            dstyle, dtxt = "background:#e7f3ea;color:#2f7d43", "+%d ahead" % d
        elif d < 0:
            dstyle, dtxt = "background:#fbe9e7;color:#b23b2e", "%d behind" % d
        else:
            dstyle, dtxt = "background:#eef2f7;color:#5c7185", "even"
        rows.append(
            "<div class='row'><div class='g'><span class='gname'>%s</span>"
            "<span class='delta' style='%s'>%s</span></div>"
            "<div class='pair'><span class='who'>%s</span>"
            "<span class='track'><span class='fill' style='width:%d%%;background:var(--navy)'></span></span>"
            "<span class='sc'>%d</span></div>"
            "<div class='pair'><span class='who'>%s</span>"
            "<span class='track'><span class='fill' style='width:%d%%;background:var(--pista)'></span></span>"
            "<span class='sc'>%d</span></div></div>"
            % (e(LABEL.get(st, st)), dstyle, dtxt, la, va, va, lb, vb, vb)
        )

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>AI Visibility Comparison</title><style>" + COMPARE_CSS + "</style></head><body>"
        "<h1>AI Visibility Comparison</h1>"
        "<div class='sub'>Funnel scores side by side &mdash; higher is better.</div>"
        "<div class='legend'><span><i class='dot' style='background:var(--navy)'></i>" + la + "</span>"
        "<span><i class='dot' style='background:var(--pista)'></i>" + lb + "</span></div>"
        "<div class='overall'>"
        "<div class='oc'><div class='n'>" + la + "</div><div class='v' style='color:" + score_color(oa) + "'>" + str(oa) + "</div></div>"
        "<div class='oc'><div class='n'>" + lb + "</div><div class='v' style='color:" + score_color(ob) + "'>" + str(ob) + "</div></div>"
        "</div>"
        "<div class='insight'>" + insight + "</div>"
        + "".join(rows) +
        "<div class='foot'>Overall = average of the five gate scores &middot; read-only audit</div>"
        "</body></html>"
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: report_html.py <report.json> <out.html>")
        sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as f:
        rep = json.load(f)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(render_html(rep))
    print("wrote " + sys.argv[2])
