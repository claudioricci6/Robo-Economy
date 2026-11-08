"""Robotic Theatre Planner - Streamlit app.

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import datetime as dt
import io

import pandas as pd
import streamlit as st

import ui
from core import (CONTRACTS, GROUP_NAME, OP, PROCEDURES, SYNONYMS, Robot, clinical_score, deadline_alerts,
                          economic_alerts, example_list, next_code, optimise, parse_rows, schedule, schedule_table, summary)

COPYRIGHT = ("© 2026 Claudio Ricci, University of Bologna, IRCCS Azienda Ospedaliero-Universitaria di Bologna. "
             "All rights reserved.")

st.set_page_config(page_title="Robotic Theatre Planner", page_icon="🗓️", layout="wide")
st.html(ui.CSS)

TODAY = dt.date.today()
OP_LABEL = {p["k"]: p["n"] for p in PROCEDURES}
LABEL_OP = {v: k for k, v in OP_LABEL.items()}


def first_workday(d: dt.date) -> dt.date:
    while d.weekday() > 4:
        d += dt.timedelta(days=1)
    return d


# ------------------------------------------------------------------ state
if "patients" not in st.session_state:
    st.session_state.patients = []
    st.session_state.example = False
if "pending" not in st.session_state:
    st.session_state.pending = []

# ------------------------------------------------------------------ sidebar: robots and sessions
with st.sidebar:
    st.header("Robots and sessions")
    n_robots = st.selectbox("Number of robots", [1, 2, 3, 4, 5, 6], index=1)
    defaults = [("multi", 5, "A"), ("colon", 3, "B")] + [("multi", 5, "A")] * 4
    robots = []
    for i in range(n_robots):
        with st.expander(f"Robot {i + 1}", expanded=i < 2):
            t0, s0, c0 = defaults[i]
            rtype = st.radio("Type", ["multi", "colon"], index=0 if t0 == "multi" else 1, key=f"type{i}", horizontal=True,
                             format_func=lambda x: "Multi-purpose" if x == "multi" else "Colorectal only")
            spw = st.select_slider("Sessions per week", options=[1, 2, 3, 4, 5], value=s0, key=f"spw{i}")
            contract = st.selectbox("Contract", list(CONTRACTS), index=list(CONTRACTS).index(c0), key=f"ctr{i}",
                                    format_func=lambda k: CONTRACTS[k]["n"])
            robots.append(Robot(i, rtype, spw, contract))
    session_len = st.selectbox("Session length", [480, 600, 720], index=2, format_func=lambda m: f"{m // 60} hours")
    start = st.date_input("First day", value=first_workday(TODAY + dt.timedelta(days=1)))
    weeks = st.selectbox("Planning horizon (weeks)", [2, 4, 6, 8], index=2)
    deadline = st.selectbox("Cancer deadline (days)", [30, 45, 60], index=0)
    allow_benign = st.checkbox("Use free robot time for benign operations", value=True)
    st.caption("Multi-purpose robot: all operations. Colorectal-only robot: colon, rectum, ileocaecal resection, "
               "left colectomy, Hartmann reversal.")

# ------------------------------------------------------------------ header
st.html(ui.header())
kpi_slot = st.empty()

tab_upload, tab_list, tab_alerts, tab_plan, tab_opt, tab_about = st.tabs(
    ["1 · Upload a list", "2 · Waiting list", "Alerts", "Schedule", "Optimiser", "Methods"])


def load_example():
    st.session_state.patients, st.session_state.example = example_list(TODAY), True


EXAMPLE_TEXT = ("No waiting list yet? Load an example with 70 patients waiting (48 cancer: colorectal, gastric, pancreas, "
                "liver, prostate, kidney, bladder, lung, oesophagus, ovary; 22 benign: cholecystectomy, Crohn's disease, "
                "diverticular disease, Hartmann reversal, bariatric and antireflux surgery).")

# ------------------------------------------------------------------ waiting list
with tab_list:
    if not st.session_state.patients:
        st.info("No waiting list yet. Upload your list in tab 1, add patients one by one in the table below, or load the example.")
        if st.button("Load example list (70 patients)", key="ex_list", type="primary"):
            load_example()
            st.rerun()
    elif st.session_state.example:
        st.info("Example data (70 patients). Replace them with your own list (tab 1) or edit the table below.")
    df = pd.DataFrame([{"Code": p["code"], "Operation": OP_LABEL[p["op"]], "Listed on": p["date"]}
                       for p in st.session_state.patients])
    edited = st.data_editor(
        df, num_rows="dynamic", width="stretch", hide_index=True, key="editor",
        column_config={
            "Code": st.column_config.TextColumn("Code", help="Progressive number"),
            "Operation": st.column_config.SelectboxColumn("Operation", options=list(OP_LABEL.values()), required=True),
            "Listed on": st.column_config.DateColumn("Listed on", format="DD/MM/YYYY", required=True),
        })
    new = []
    for _, r in edited.iterrows():
        if pd.isna(r["Operation"]) or pd.isna(r["Listed on"]):
            continue
        code = str(r["Code"]).strip() if pd.notna(r["Code"]) and str(r["Code"]).strip() else next_code([x["code"] for x in new] + [p["code"] for p in st.session_state.patients])
        d = r["Listed on"]
        new.append(dict(code=code, op=LABEL_OP[r["Operation"]], date=d if isinstance(d, dt.date) else pd.Timestamp(d).date()))
    if new != st.session_state.patients:
        st.session_state.patients = new
        st.session_state.example = False
    n_c = sum(OP[p["op"]]["g"] != "ben" for p in st.session_state.patients)
    st.caption(f"{len(st.session_state.patients)} patients: {n_c} cancer, {len(st.session_state.patients) - n_c} benign. "
               "Use progressive codes, not names.")
    c1, c2 = st.columns(2)
    if c1.button("Clear list"):
        st.session_state.patients, st.session_state.example = [], False
        st.rerun()
    if c2.button("Load example (70 patients)"):
        load_example()
        st.rerun()

# ------------------------------------------------------------------ upload
with tab_upload:
    if not st.session_state.patients:
        st.html(ui.alerts([dict(severity="info", title="Start here: upload your waiting list", text=EXAMPLE_TEXT, items=[])]))
        if st.button("Load example list (70 patients)", key="ex_up", type="primary"):
            load_example()
            st.rerun()
    else:
        st.html(ui.alerts([dict(severity="ok", title=f"{len(st.session_state.patients)} patients on the waiting list"
                                + (" (example)" if st.session_state.example else ""),
                                text="See tab 2 to check or edit the list, then Alerts, Schedule and Optimiser.", items=[])]))
    st.write("Excel (.xlsx), CSV or text file. Columns: **code** (progressive number), **operation**, **date** of listing. "
             "Without a code, numbering continues from the last number in the list.")
    template = pd.DataFrame({"code": [31, 32, 33], "operation": ["PD", "DP", "Radical prostatectomy"],
                             "date": ["2026-10-20", "28/10/2026", "2026-11-02"]})
    buf = io.BytesIO()
    template.to_excel(buf, index=False)
    st.download_button("Download Excel template", buf.getvalue(), "waiting_list_template.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    up = st.file_uploader("Choose a file", type=["xlsx", "xls", "csv", "txt"])
    pasted = st.text_area("Or paste rows (code;operation;date)", placeholder="31;PD;2026-10-20\n32;DP;28/10/2026")
    rows = None
    if up is not None:
        try:
            if up.name.lower().endswith((".xlsx", ".xls")):
                raw = pd.read_excel(up, header=None, dtype=object)
            else:
                raw = pd.read_csv(up, header=None, sep=None, engine="python", dtype=str)
            rows = raw.where(pd.notna(raw), "").values.tolist()
        except Exception:
            st.error("The file cannot be read. Check that it is a valid Excel or CSV file and is not password-protected.")
    elif pasted.strip():
        import re
        rows = [re.split(r"[;\t]|,(?=\s*\S)", line) for line in pasted.splitlines()]
    if rows is not None:
        parsed = parse_rows(rows, {p["code"] for p in st.session_state.patients})
        ok = [r for r in parsed if not r["errors"]]
        st.write(f"{len(parsed)} rows read: **{len(ok)} valid**" + (f", {len(parsed) - len(ok)} with errors (will not be loaded)" if len(parsed) > len(ok) else ""))
        st.dataframe(pd.DataFrame([{"Code": r["code"] or "auto", "Operation": OP_LABEL.get(r["op"], r["raw"]),
                                    "Date": r["date"], "Check": "; ".join(r["errors"]) or ("code already listed: will be renumbered" if r["duplicate"] else "OK")}
                                   for r in parsed]), width="stretch", hide_index=True)
        b1, b2 = st.columns(2)

        def load(replace: bool):
            base = [] if replace else list(st.session_state.patients)
            for r in ok:
                ids = [p["code"] for p in base]
                code = r["code"] if r["code"] and r["code"] not in ids else next_code(ids)
                base.append(dict(code=code, op=r["op"], date=r["date"]))
            st.session_state.patients, st.session_state.example = base, False

        if b1.button("Add to list", disabled=not ok, type="primary"):
            load(False)
            st.success(f"{len(ok)} patients added.")
            st.rerun()
        if b2.button("Replace list", disabled=not ok):
            load(True)
            st.success(f"{len(ok)} patients loaded in place of the previous list.")
            st.rerun()
    with st.expander("Accepted operation names and codes"):
        st.dataframe(pd.DataFrame([{"Code": p["k"], "Operation": p["n"], "Group": GROUP_NAME[p["g"]], "OR minutes": p["m"],
                                    "Also accepted": ", ".join(s.lower() for s in SYNONYMS.get(p["k"], []))} for p in PROCEDURES]),
                     width="stretch", hide_index=True)

# ------------------------------------------------------------------ plan
plan = schedule(st.session_state.patients, robots, start, weeks, session_len, deadline, allow_benign)
S = summary(plan)

HAS = bool(st.session_state.patients)
NOLIST = "Upload a waiting list in tab 1, or load the example list with 70 patients, to see the plan."
kpi_slot.html(ui.kpis(S, deadline) if HAS else '<p class="rtp-note" style="font-size:14px;margin:8px 0 4px">' + NOLIST + '</p>')


def show(title, alerts):
    st.html(f'<div style="display:flex;justify-content:space-between;align-items:baseline">{ui.h2(title)}'
            f'<span class="rtp-tag">{ui.alert_count(alerts)}</span></div>' + ui.alerts(alerts))


with tab_alerts:
    if not HAS:
        st.info(NOLIST)
    else:
        show("Cancer deadline alerts", deadline_alerts(plan))
        show("Economic use alerts", economic_alerts(plan))
        st.caption("Thresholds from the Robo Economy model: robot time used below 40% is uneconomic and 40-70% is low; robot "
                   "cost above the DRG revenue it handles (ratio above 1) is uneconomic. Short benign operations "
                   "(cholecystectomy, bariatric surgery) have a low DRG tariff and no proven robotic benefit.")

def render_schedule(p, key):
    tab = schedule_table(p)
    if tab.empty:
        st.info("No operation scheduled. Add patients to the list or check robots and sessions.")
        return
    st.html(ui.schedule(p))
    with st.expander("Table view"):
        st.dataframe(tab, width="stretch", hide_index=True)
    out = io.BytesIO()
    tab.to_excel(out, index=False)
    st.download_button("Download schedule (Excel)", out.getvalue(), f"robotic_schedule_{key}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_{key}")


with tab_plan:
    if not HAS:
        st.info(NOLIST)
    else:
        st.caption("Rule-based schedule: cancer patients by deadline, benign patients in the time left, on the sessions set "
                   "for each robot. For the best plan, use the Optimiser tab.")
        render_schedule(plan, "rules")

with tab_opt:
    if not HAS:
        st.info(NOLIST)
    else:
        st.write("The optimiser looks for the best plan in strict order of priority: **1. clinical** (every cancer patient "
                 "scheduled, no day beyond the deadline, a margin of more than 3 days when possible); **2. economic** (each "
                 "operation on the robot where DRG tariff minus robot cost is highest; benign operations that cost the robot "
                 "more than their DRG are left to laparoscopy); **3. use** (the fewest sessions needed, so free sessions can "
                 "go back to other surgery).")
        o1, o2, o3 = st.columns(3)
        sess_val = o1.number_input("Value of a session given back to other surgery (€)", 0, 20000, 2000, 500,
                                   help="A session is opened only if its operations are worth more than this. Higher values "
                                        "give fewer, fuller sessions.")
        all_days = o2.checkbox("Let the optimiser use every weekday on each robot", value=True,
                               help="Then it recommends how many weekly sessions each robot needs. Untick to keep the "
                                    "sessions set for each robot.")
        tlimit = o3.slider("Time limit (seconds)", 5, 60, 20)
        sig = (tuple((p["code"], p["op"], p["date"]) for p in st.session_state.patients),
               tuple((r.type, r.sessions_per_week, r.contract) for r in robots), start, weeks, session_len, deadline,
               allow_benign, sess_val, all_days)
        if st.button("Optimise", type="primary"):
            with st.spinner("Optimising..."):
                st.session_state.opt = (sig, *optimise(st.session_state.patients, robots, start, weeks, session_len, deadline,
                                                         allow_benign, sess_val, all_days, tlimit))
        if "opt" in st.session_state and st.session_state.opt[0] == sig:
            _, oplan, info = st.session_state.opt
            O = summary(oplan)
            st.caption(f"Solver status: {info['status']}.")
            busy_r = [x for x in plan.sessions if x.cases]
            u_r = sum(x.used for x in busy_r) / sum(x.length for x in busy_r) if busy_r else 0
            spw_now = sum(r.sessions_per_week for r in robots)
            spw_opt = sum(info["recommended_sessions"].values())
            labels = [f"Cancers within {deadline} days", "Cancers late", "Cancers not scheduled", "Benign on the robot",
                      "Weekly sessions set (all robots)", "Sessions with operations in the period",
                      "Robot time used in those sessions", "Robot cost per € of DRG", "DRG revenue minus robot cost"]
            rv = [f"{S['on_time']}/{S['cancers']}", S["late"], S["unscheduled"], f"{S['benign_done']}/{S['benign']}", spw_now,
                  len(busy_r), f"{u_r:.0%}", f"{S['ratio']:.2f}" if S["drg"] else "-", f"€{S['drg'] - S['cost']:,.0f}"]
            ov = [f"{O['on_time']}/{O['cancers']}", O["late"], O["unscheduled"], f"{O['benign_done']}/{O['benign']}", spw_opt,
                  len(oplan.sessions), f"{O['utilisation']:.0%}", f"{O['ratio']:.2f}" if O["drg"] else "-", f"€{O['drg'] - O['cost']:,.0f}"]
            num = lambda v: float(str(v).split("/")[0].replace("€", "").replace(",", "").replace("%", "")) if str(v) not in ("-",) else None
            lower_better = {1, 2, 4, 5, 7}
            better = set()
            for i, (a_, b_) in enumerate(zip(rv, ov)):
                x, y = num(a_), num(b_)
                if x is not None and y is not None and x != y and ((y < x) if i in lower_better else (y > x)) and i != 3:
                    better.add(i)
            st.html(ui.h2("Rule-based versus optimised") + ui.table(["", "Rule-based", "Optimised"],
                    [[l, a_, b_] for l, a_, b_ in zip(labels, rv, ov)], better_col=2, better_rows=better))
            st.html(ui.h2("Recommended configuration") + ui.table(
                ["Robot", "Type", "Contract", "Sessions per week now", "Sessions per week needed", "Sessions opened in the period"],
                [[r.label, "multi-purpose" if r.type == "multi" else "colorectal only", CONTRACTS[r.contract]["n"],
                  r.sessions_per_week, info["recommended_sessions"][r.index],
                  sum(1 for s in oplan.sessions if s.robot.index == r.index)] for r in robots]))
            if not all_days:
                st.caption("Sessions were limited to the weekdays set for each robot.")
            lap = info["benign_laparoscopy"]
            if lap:
                st.html(ui.alerts([dict(severity="info", title=f"{len(lap)} benign patient(s) left to laparoscopy or to a later period",
                                        text="On the available robots their robot cost exceeds the DRG tariff, or no session had room.",
                                        items=[f"{c.code} {c.op['n']}" for c in lap])]))
            show("Cancer deadline alerts (optimised plan)", deadline_alerts(oplan))
            show("Economic use alerts (optimised plan)", economic_alerts(oplan))
            st.html(ui.h2("Optimised schedule"))
            render_schedule(oplan, "optimised")
        elif "opt" in st.session_state:
            st.info("Settings or list changed. Press Optimise again.")

with tab_about:
    st.markdown("""
**Operating-room time.** Published robotic operative time + 60 min (anaesthesia, positioning, docking, recovery) + 30 min
turnover. Pancreatoduodenectomy 565 min, distal pancreatectomy 328 min, minor liver resection 316 min, major hepatectomy 372 min.

**Scheduling.** Only whole operations; no session runs late. Cancer patients first, by deadline (listing date + deadline);
benign patients only in the time left, by listing date. Colorectal-only robots are filled first each day.
Weekday pattern: 5 sessions = Mon-Fri; 4 = Mon, Tue, Thu, Fri; 3 = Mon, Wed, Fri; 2 = Tue, Thu; 1 = Wed.

**Costs.** One of three Italian public contracts for each robot (VAT included): rental + consumables (€534,360 per year +
€4,844 per operation), price per operation (€3,226), high rental + consumables (€906,216 per year + €2,490 per operation).
Fixed costs are counted per robot for the planning horizon (46 operating weeks per year). Expected DRG tariffs from the
Lombardy list, 40% of patients in the DRG with complications.

**Source.** Ricci C, D'Ambra V, Fichera M, Alberici L, Ingaldi C, Casadei R. Who should fill the robot? Operating-room
capacity, approach-neutral DRG payment and interdisciplinary use of robotic platforms in major general surgery: a
hospital-level model.

Scheduling support only: clinical decisions remain with the surgeon. Patient data stay in this session and are not stored.
""")

st.html(ui.footer(COPYRIGHT))
