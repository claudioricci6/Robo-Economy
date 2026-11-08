"""HTML components that give the Streamlit app the look of the web version of the planner."""
from __future__ import annotations

import html

from core import CONTRACTS, GROUP_NAME

CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --rtp-bg:#f3f6f5; --rtp-panel:#ffffff; --rtp-ink:#15211f; --rtp-muted:#5b6b68; --rtp-line:#d6dfdc;
  --rtp-accent:#0e7a6d; --rtp-accent-soft:#dcefeb;
  --rtp-onc:#b4233c; --rtp-onc-soft:#f8e3e7; --rtp-oth:#7a3fb0; --rtp-oth-soft:#efe5f8; --rtp-ben:#3d5a80; --rtp-ben-soft:#e2e9f3;
  --rtp-ok:#1f7a3a; --rtp-ok-soft:#e1f2e6; --rtp-warn:#a15c00; --rtp-warn-soft:#fbefdc; --rtp-bad:#b4233c; --rtp-bad-soft:#f8e3e7;
  --rtp-info:#2f5f8f; --rtp-info-soft:#e3edf7;
  --rtp-body:"Instrument Sans","Segoe UI",system-ui,sans-serif; --rtp-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button p, .stApp [data-baseweb="select"] div, .stApp [data-baseweb="tab"] p{font-family:var(--rtp-body)}
[data-testid="stIconMaterial"], .material-symbols-rounded{font-family:"Material Symbols Rounded" !important}
h1,h2,h3{font-family:var(--rtp-body) !important;letter-spacing:-.01em}
[data-testid="stSidebar"]{background:var(--rtp-panel);border-right:1px solid var(--rtp-line)}
[data-testid="stSidebar"] h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--rtp-muted);font-weight:600}
.stTabs [data-baseweb="tab-list"]{gap:4px}
.stButton button[kind="primary"],.stDownloadButton button{background:var(--rtp-accent) !important;border-color:var(--rtp-accent) !important;color:#fff !important}
.stApp{background:var(--rtp-bg)}
.stTabs [data-baseweb="tab"]{font-weight:600}
.rtp-tag{font-family:var(--rtp-mono);font-size:11px;color:var(--rtp-muted);letter-spacing:.04em;text-transform:uppercase}
.rtp-h1{font-size:30px;font-weight:700;margin:2px 0 4px;color:var(--rtp-ink);letter-spacing:-.01em}
.rtp-sub{color:var(--rtp-muted);max-width:80ch;margin:0 0 6px;font-size:15px}
.rtp-h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--rtp-muted);margin:18px 0 10px;font-weight:600}
.rtp-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:6px 0 4px}
.rtp-kpi{border:1px solid var(--rtp-line);border-radius:8px;padding:10px 12px;background:var(--rtp-panel)}
.rtp-kpi .v{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.1;color:var(--rtp-ink)}
.rtp-kpi .l{font-size:12px;color:var(--rtp-muted)}
.rtp-kpi.good .v{color:var(--rtp-ok)} .rtp-kpi.bad .v{color:var(--rtp-bad)} .rtp-kpi.warn .v{color:var(--rtp-warn)}
.rtp-alerts{display:grid;gap:8px}
.rtp-alert{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;align-items:start;padding:10px 12px;border-radius:8px;border:1px solid var(--rtp-line);color:var(--rtp-ink)}
.rtp-alert.critical{background:var(--rtp-bad-soft);border-color:var(--rtp-bad)} .rtp-alert.warning{background:var(--rtp-warn-soft);border-color:var(--rtp-warn)}
.rtp-alert.info{background:var(--rtp-info-soft);border-color:var(--rtp-info)} .rtp-alert.ok{background:var(--rtp-ok-soft);border-color:var(--rtp-ok)}
.rtp-sev{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:2px 6px;border-radius:4px;color:#fff;margin-top:2px}
.critical .rtp-sev{background:var(--rtp-bad)} .warning .rtp-sev{background:var(--rtp-warn)} .info .rtp-sev{background:var(--rtp-info)} .ok .rtp-sev{background:var(--rtp-ok)}
.rtp-alert b{display:block;font-size:14px}
.rtp-alert p{margin:2px 0 0;font-size:13px}
.rtp-alert ul{margin:4px 0 0;padding-left:18px;font-size:13px}
.rtp-legend{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12px;color:var(--rtp-muted);margin:4px 0 12px}
.rtp-pill{display:inline-block;font-size:11px;padding:1px 7px;border-radius:999px;font-weight:600;white-space:nowrap}
.rtp-pill.onc{background:var(--rtp-onc-soft);color:var(--rtp-onc)} .rtp-pill.oth{background:var(--rtp-oth-soft);color:var(--rtp-oth)} .rtp-pill.ben{background:var(--rtp-ben-soft);color:var(--rtp-ben)}
.rtp-day{border-top:1px solid var(--rtp-line);padding:10px 0}
.rtp-day:first-child{border-top:none;padding-top:0}
.rtp-dayhead{display:flex;justify-content:space-between;gap:8px;font-weight:600;margin-bottom:6px;color:var(--rtp-ink)}
.rtp-dayhead span:last-child{font-family:var(--rtp-mono);font-size:12px;color:var(--rtp-muted);font-weight:400}
.rtp-sess{display:grid;grid-template-columns:150px minmax(0,1fr);gap:10px;align-items:start;margin:6px 0}
@media (max-width:640px){.rtp-sess{grid-template-columns:minmax(0,1fr)}}
.rtp-sesslab{font-size:12px;color:var(--rtp-muted);line-height:1.35}
.rtp-sesslab b{color:var(--rtp-ink);font-family:var(--rtp-mono);font-size:12px}
.rtp-bar{display:flex;height:30px;border:1px solid var(--rtp-line);border-radius:6px;overflow:hidden;background:var(--rtp-bg)}
.rtp-seg{display:flex;align-items:center;padding:0 6px;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-right:2px solid var(--rtp-panel);min-width:0;font-family:var(--rtp-mono)}
.rtp-seg.onc{background:var(--rtp-onc-soft);color:var(--rtp-onc)} .rtp-seg.oth{background:var(--rtp-oth-soft);color:var(--rtp-oth)} .rtp-seg.ben{background:var(--rtp-ben-soft);color:var(--rtp-ben)}
.rtp-seg.late{outline:2px solid var(--rtp-bad);outline-offset:-2px}
.rtp-cases{display:flex;flex-wrap:wrap;gap:4px 12px;margin-top:4px;font-size:12px;color:var(--rtp-muted)}
.rtp-cases b{color:var(--rtp-ink);font-family:var(--rtp-mono);font-weight:500}
.rtp-table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;background:var(--rtp-panel);border:1px solid var(--rtp-line);border-radius:8px;overflow:hidden}
.rtp-table th,.rtp-table td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--rtp-line);font-size:13px;color:var(--rtp-ink)}
.rtp-table th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--rtp-muted);font-weight:600;background:var(--rtp-bg)}
.rtp-table td.better{color:var(--rtp-ok);font-weight:600}
.rtp-note{font-size:12px;color:var(--rtp-muted);max-width:90ch}
.rtp-foot{font-size:12px;color:var(--rtp-muted);border-top:1px solid var(--rtp-line);padding-top:10px;margin-top:20px}
</style>
"""

e = html.escape


def header() -> str:
    return ('<div><span class="rtp-tag">Robo Economy · scheduling support</span>'
            '<div class="rtp-h1">Robotic Theatre Planner</div>'
            '<p class="rtp-sub">Fills robotic sessions with cancer patients first, in order of deadline (within 30 days of '
            'listing). Benign operations use only the time left. Alerts flag missed deadlines and uneconomic use of the '
            'robots; the optimiser finds the best plan.</p></div>')


def h2(text: str) -> str:
    return f'<div class="rtp-h2">{e(text)}</div>'


def kpis(S: dict, deadline: int) -> str:
    U, R = S["utilisation"], S["ratio"]
    tiles = [
        ("good" if S["cancers"] and S["on_time"] == S["cancers"] else "warn", f"{S['on_time']}/{S['cancers']}", f"Cancers within {deadline} days"),
        ("bad" if S["late"] else "good", S["late"], "Cancers late"),
        ("bad" if S["unscheduled"] else "good", S["unscheduled"], "Cancers not scheduled"),
        ("", f"{S['benign_done']}/{S['benign']}", "Benign scheduled"),
        ("bad" if U < .4 else "warn" if U < .7 else "good", f"{U:.0%}", "Robot time used"),
        ("bad" if R > 1 else "warn" if R > .8 else "good", f"{R:.2f}" if S["drg"] else "–", "Robot cost per € of DRG"),
    ]
    return '<div class="rtp-kpis">' + "".join(
        f'<div class="rtp-kpi {c}"><div class="v">{v}</div><div class="l">{e(l)}</div></div>' for c, v, l in tiles) + "</div>"


SEV = {"critical": "Critical", "warning": "Warning", "info": "Note", "ok": "OK"}


def alerts(items: list[dict]) -> str:
    out = []
    for a in items:
        li = "".join(f"<li>{e(x)}</li>" for x in a["items"])
        out.append(f'<div class="rtp-alert {a["severity"]}"><span class="rtp-sev">{SEV[a["severity"]]}</span><div>'
                   f'<b>{e(a["title"])}</b>' + (f'<p>{e(a["text"])}</p>' if a["text"] else "")
                   + (f"<ul>{li}</ul>" if li else "") + "</div></div>")
    return '<div class="rtp-alerts">' + "".join(out) + "</div>"


def alert_count(items: list[dict]) -> str:
    cr = sum(a["severity"] == "critical" for a in items)
    w = sum(a["severity"] == "warning" for a in items)
    return f"{cr} critical · {w} warning" if cr or w else "no issues"


LEGEND = ('<div class="rtp-legend"><span><span class="rtp-pill onc">General-surgery cancer</span></span>'
          '<span><span class="rtp-pill oth">Other specialties\' cancer</span></span>'
          '<span><span class="rtp-pill ben">Benign</span></span><span>Red border: cancer operated after the deadline</span></div>')


def schedule(plan) -> str:
    busy = [s for s in plan.sessions if s.cases]
    if not busy:
        return '<p class="rtp-note">No operation scheduled. Add patients to the list or check robots and sessions.</p>'
    out = [LEGEND]
    for day in sorted({s.day for s in busy}):
        ss = sorted([s for s in busy if s.day == day], key=lambda s: s.robot.index)
        n = sum(len(s.cases) for s in ss)
        out.append(f'<div class="rtp-day"><div class="rtp-dayhead"><span>{day.strftime("%a %d %b %Y")}</span>'
                   f'<span>{n} operation{"s" if n != 1 else ""}</span></div>')
        for s in ss:
            segs = "".join(
                f'<div class="rtp-seg {c.op["g"]}{" late" if c.late else ""}" style="flex:0 0 {100 * c.op["m"] / s.length:.2f}%" '
                f'title="{e(c.code)} · {e(c.op["n"])} · {c.op["m"]} min">{e(c.code)}</div>' for c in s.cases)
            cases = "".join(
                f'<span><b>{e(c.code)}</b> {e(c.op["n"])}' + (f' · due {c.due.strftime("%a %d %b")}' if c.cancer else "") + "</span>"
                for c in s.cases)
            out.append(f'<div class="rtp-sess"><div class="rtp-sesslab"><b>{e(s.robot.label)}</b> '
                       f'{"colorectal" if s.robot.type == "colon" else "multi-purpose"}<br>{e(CONTRACTS[s.robot.contract]["n"])}'
                       f'<br>{s.used}/{s.length} min</div><div style="min-width:0"><div class="rtp-bar">{segs}</div>'
                       f'<div class="rtp-cases">{cases}</div></div></div>')
        out.append("</div>")
    return "".join(out)


def table(header_row: list[str], rows: list[list], better_col: int | None = None, better_rows: set | None = None) -> str:
    th = "".join(f"<th>{e(h)}</th>" for h in header_row)
    body = []
    for i, r in enumerate(rows):
        tds = "".join(f'<td class="{"better" if (better_rows and i in better_rows and j == better_col) else ""}">{e(str(v))}</td>'
                      for j, v in enumerate(r))
        body.append(f"<tr>{tds}</tr>")
    return f'<table class="rtp-table"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def footer(text: str) -> str:
    return f'<div class="rtp-foot">{e(text)}</div>'
