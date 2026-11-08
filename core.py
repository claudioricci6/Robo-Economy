"""Core logic of the Robotic Theatre Planner.

Scheduling rules (same as the Robo Economy model):
* one session = a fixed number of minutes (8, 10 or 12 hours); only whole operations; no overrun;
* cancer patients first, in order of deadline (listing date + deadline days);
* benign patients only in the time left, in order of listing date;
* colorectal-only robots accept colorectal operations only and are filled first each day;
* operating-room minutes = published robotic operative time + 60 min (anaesthesia, positioning,
  docking, recovery) + 30 min turnover.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- catalogue
# g: onc = general-surgery cancer, oth = other specialties' cancer, ben = benign
# m: operating-room minutes; cr: colorectal; t: expected DRG tariff (EUR, Lombardy list,
# 40% of patients in the DRG with complications); lv: short low-value benign operation
PROCEDURES = [
    dict(k="COLON", n="Colon cancer resection", g="onc", m=318, cr=True, t=9618),
    dict(k="RECTUM", n="Rectal cancer resection", g="onc", m=388, cr=True, t=8348),
    dict(k="STOMACH", n="Gastrectomy for cancer", g="onc", m=311, t=9053),
    dict(k="PD", n="Pancreatoduodenectomy (PD)", g="onc", m=565, t=12063),
    dict(k="DP", n="Distal pancreatectomy (DP)", g="onc", m=328, t=12063),
    dict(k="LIVER_MIN", n="Minor liver resection (cancer)", g="onc", m=316, t=12063),
    dict(k="LIVER_MAJ", n="Major hepatectomy (cancer)", g="onc", m=372, t=12063),
    dict(k="PROSTATE", n="Radical prostatectomy", g="oth", m=280, t=5212),
    dict(k="KIDNEY", n="Kidney cancer surgery", g="oth", m=246, t=9292),
    dict(k="BLADDER", n="Radical cystectomy", g="oth", m=390, t=9292),
    dict(k="LUNG", n="Lung lobectomy (cancer)", g="oth", m=270, t=10972),
    dict(k="OESOPHAGUS", n="Oesophagectomy (cancer)", g="oth", m=471, t=9053),
    dict(k="OVARY", n="Ovarian cancer surgery", g="oth", m=328, t=7713),
    dict(k="CHOLE", n="Cholecystectomy", g="ben", m=172, t=4276, lv=True),
    dict(k="ILEOCAECAL", n="Ileocaecal resection (Crohn's disease)", g="ben", m=316, cr=True, t=9618),
    dict(k="SIGMOID", n="Left colectomy (diverticular disease)", g="ben", m=355, cr=True, t=9618),
    dict(k="HARTMANN", n="Hartmann reversal", g="ben", m=365, cr=True, t=9618),
    dict(k="SLEEVE", n="Sleeve gastrectomy", g="ben", m=192, t=5681, lv=True),
    dict(k="BYPASS", n="Roux-en-Y gastric bypass", g="ben", m=253, t=5681, lv=True),
    dict(k="ANTIREFLUX", n="Antireflux surgery (fundoplication)", g="ben", m=249, t=9053),
]
for _p in PROCEDURES:
    _p.setdefault("cr", False)
    _p.setdefault("lv", False)
OP = {p["k"]: p for p in PROCEDURES}
GROUP_NAME = {"onc": "General-surgery cancer", "oth": "Other specialties' cancer", "ben": "Benign"}

# Italian public contracts, VAT included (Robo Economy model)
CONTRACTS = {
    "A": dict(n="Rental + consumables", fixed=534_360, var=4_844),
    "B": dict(n="Price per operation", fixed=0, var=3_226),
    "C": dict(n="High rental + consumables", fixed=906_216, var=2_490),
}
OPERATING_WEEKS = 46
# weekday pattern by sessions per week (Monday = 0)
DAY_PATTERN = {5: [0, 1, 2, 3, 4], 4: [0, 1, 3, 4], 3: [0, 2, 4], 2: [1, 3], 1: [2]}

SYNONYMS = {
    "COLON": ["COLON CANCER", "RIGHT HEMICOLECTOMY", "LEFT HEMICOLECTOMY", "HEMICOLECTOMY", "COLECTOMY", "EMICOLECTOMIA", "COLON TUMORE"],
    "RECTUM": ["RECTAL CANCER", "ANTERIOR RESECTION", "LOW ANTERIOR RESECTION", "TME", "RETTO", "RESEZIONE ANTERIORE"],
    "STOMACH": ["GASTRECTOMY", "GASTRIC CANCER", "STOMACO", "GASTRECTOMIA"],
    "PD": ["WHIPPLE", "PANCREATODUODENECTOMY", "PANCREATICODUODENECTOMY", "DCP", "DUODENOCEFALOPANCREASECTOMIA", "PANCREATODUODENECTOMIA"],
    "DP": ["DISTAL PANCREATECTOMY", "LEFT PANCREATECTOMY", "SPLENOPANCREATECTOMY", "PSX", "PANCREASECTOMIA SINISTRA", "PANCREASECTOMIA DISTALE", "SPLENOPANCREASECTOMIA"],
    "LIVER_MIN": ["LIVER MIN", "MINOR LIVER RESECTION", "MINOR HEPATECTOMY", "WEDGE", "WEDGE RESECTION", "SEGMENTECTOMY", "BISEGMENTECTOMY", "LEFT LATERAL SECTIONECTOMY", "FEGATO MIN", "RESEZIONE EPATICA MINORE", "SEGMENTECTOMIA", "RESEZIONE ATIPICA"],
    "LIVER_MAJ": ["LIVER MAJ", "MAJOR HEPATECTOMY", "MAJOR LIVER RESECTION", "RIGHT HEPATECTOMY", "LEFT HEPATECTOMY", "TRISECTIONECTOMY", "FEGATO MAG", "EPATECTOMIA MAGGIORE", "EPATECTOMIA DESTRA", "EPATECTOMIA SINISTRA"],
    "PROSTATE": ["PROSTATECTOMY", "RADICAL PROSTATECTOMY", "RARP", "PROSTATA", "PROSTATECTOMIA"],
    "KIDNEY": ["NEPHRECTOMY", "PARTIAL NEPHRECTOMY", "RADICAL NEPHRECTOMY", "RENE", "NEFRECTOMIA", "NEFRECTOMIA PARZIALE"],
    "BLADDER": ["CYSTECTOMY", "RADICAL CYSTECTOMY", "VESCICA", "CISTECTOMIA"],
    "LUNG": ["LOBECTOMY", "LUNG LOBECTOMY", "POLMONE", "LOBECTOMIA"],
    "OESOPHAGUS": ["ESOPHAGUS", "OESOPHAGECTOMY", "ESOPHAGECTOMY", "ESOFAGO", "ESOFAGECTOMIA"],
    "OVARY": ["OVARIAN CANCER", "OVAIO"],
    "CHOLE": ["CHOLECYSTECTOMY", "COLECISTI", "COLECISTECTOMIA"],
    "ILEOCAECAL": ["ILEOCECAL", "ILEOCAECAL RESECTION", "ILEOCECAL RESECTION", "ILEOCOLIC RESECTION", "CROHN", "ILEOCECALE", "RESEZIONE ILEOCECALE"],
    "SIGMOID": ["SIGMOIDECTOMY", "LEFT COLECTOMY", "DIVERTICULAR DISEASE", "DIVERTICULITIS", "SIGMA", "SIGMOIDECTOMIA", "COLECTOMIA SINISTRA", "DIVERTICOLITE"],
    "HARTMANN": ["HARTMANN REVERSAL", "STOMA REVERSAL", "RICANALIZZAZIONE"],
    "SLEEVE": ["SLEEVE GASTRECTOMY"],
    "BYPASS": ["GASTRIC BYPASS", "RYGB", "BYPASS GASTRICO"],
    "ANTIREFLUX": ["ANTI REFLUX", "FUNDOPLICATION", "NISSEN", "ANTIREFLUSSO", "FUNDOPLICATIO"],
}
AMBIGUOUS = {
    **{x: "liver: specify minor liver resection or major hepatectomy" for x in ["LIVER", "HEPATECTOMY", "LIVER RESECTION", "FEGATO", "EPATECTOMIA", "RESEZIONE EPATICA"]},
    **{x: "pancreas: specify PD (pancreatoduodenectomy) or DP (distal pancreatectomy)" for x in ["PANCREAS", "PANCREATECTOMY", "PANCREASECTOMIA"]},
}


def norm(text) -> str:
    t = unicodedata.normalize("NFD", str(text or "").upper())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", t)).strip()


ALIAS: dict[str, str] = {}
for _p in PROCEDURES:
    ALIAS[norm(_p["k"])] = _p["k"]
    ALIAS[norm(_p["n"])] = _p["k"]
    for _s in SYNONYMS.get(_p["k"], []):
        ALIAS[norm(_s)] = _p["k"]


def to_operation(value) -> str | None:
    return ALIAS.get(norm(value))


def to_date(value) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if hasattr(value, "to_pydatetime"):  # pandas Timestamp
        try:
            return value.to_pydatetime().date()
        except Exception:
            return None
    if isinstance(value, (int, float)) and 20000 < value < 80000:  # Excel serial date
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(value))
    t = str(value).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})$", t)
    if m:
        y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        try:
            return dt.date(y, int(m[2]), int(m[1]))
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------- upload parsing
def parse_rows(rows: list[list], existing_ids: set[str]) -> list[dict]:
    """Parse raw rows (first row may be a header). Returns one dict per row with 'errors'."""
    rows = [["" if c is None else c for c in r] for r in rows]
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        return []
    i_c, i_o, i_d, start = 0, 1, 2, 0
    head = [norm(c) for c in rows[0]]
    if any(re.search(r"CODE|CODICE|OPERATION|PROCEDURE|INTERV|DISEASE|DATE|DATA", h) for h in head):
        start = 1
        find = lambda pat: next((i for i, h in enumerate(head) if re.search(pat, h)), -1)
        i_c = find(r"CODE|COD|PROGR|^N$|NUMBER|NUMERO|^ID$")
        i_o = find(r"OPERATION|PROCEDURE|SURGERY|DISEASE|INTERV|PATOLOG|MALATT|PROCED")
        i_d = find(r"DATE|DATA|LIST|INSER")
    elif to_operation(rows[0][0]) or norm(rows[0][0]) in AMBIGUOUS:
        i_c, i_o, i_d = -1, 0, 1
    out, in_file = [], set()
    for r in rows[start:]:
        get = lambda i: r[i] if 0 <= i < len(r) else ""
        code = str(get(i_c)).strip()
        if re.fullmatch(r"\d+(\.0+)?", code):
            code = str(int(float(code)))
        raw = str(get(i_o)).strip()
        op = to_operation(raw)
        date = to_date(get(i_d))
        errors = []
        if not op:
            errors.append(AMBIGUOUS.get(norm(raw), f'operation not recognised ("{raw}")' if raw else "operation missing"))
        if not date:
            errors.append("date missing or not valid")
        if code and code in in_file:
            errors.append("code repeated in the file")
        if code:
            in_file.add(code)
        out.append(dict(code=code, op=op, date=date, raw=raw, errors=errors, duplicate=bool(code and code in existing_ids)))
    return out


def next_code(ids) -> str:
    nums = [int(i) for i in ids if str(i).strip().isdigit()]
    return str(max(nums, default=0) + 1)


# --------------------------------------------------------------------------- scheduling
@dataclass
class Robot:
    index: int
    type: str = "multi"        # "multi" or "colon"
    sessions_per_week: int = 5
    contract: str = "A"

    @property
    def label(self) -> str:
        return f"Robot {self.index + 1}"

    def accepts(self, op: dict) -> bool:
        return self.type == "multi" or op["cr"]


@dataclass
class Case:
    code: str
    op: dict
    listed: dt.date
    due: dt.date | None
    when: dt.date | None = None
    robot: int | None = None

    @property
    def cancer(self) -> bool:
        return self.op["g"] != "ben"

    @property
    def late(self) -> bool:
        return bool(self.cancer and self.when and self.when > self.due)

    @property
    def margin(self) -> int | None:  # days between operation and deadline (negative = late)
        return (self.due - self.when).days if (self.cancer and self.when) else None


@dataclass
class Session:
    day: dt.date
    robot: Robot
    length: int
    cases: list = field(default_factory=list)

    @property
    def used(self) -> int:
        return sum(c.op["m"] for c in self.cases)


@dataclass
class Plan:
    sessions: list
    done: list
    waiting: list
    cases: list
    robots: list
    weeks: int
    start: dt.date
    session_len: int
    deadline: int


def schedule(patients: list[dict], robots: list[Robot], start: dt.date, weeks: int = 6,
             session_len: int = 720, deadline: int = 30, allow_benign: bool = True) -> Plan:
    cases = [Case(str(p["code"]), OP[p["op"]], p["date"],
                  p["date"] + dt.timedelta(days=deadline) if OP[p["op"]]["g"] != "ben" else None) for p in patients]
    waiting = list(cases)

    def priority(c: Case):
        if c.cancer:
            return (0, c.due, -c.op["m"])
        return (1, c.listed, -c.op["m"])

    order = sorted(robots, key=lambda r: 0 if r.type == "colon" else 1)
    sessions, done = [], []
    for d in range(weeks * 7):
        day = start + dt.timedelta(days=d)
        if day.weekday() > 4:
            continue
        for r in order:
            if day.weekday() not in DAY_PATTERN[r.sessions_per_week]:
                continue
            s = Session(day, r, session_len)
            left = session_len
            while True:
                cand = [c for c in waiting if c.op["m"] <= left and r.accepts(c.op)
                        and (allow_benign or c.cancer) and c.listed <= day]
                if not cand:
                    break
                c = min(cand, key=priority)
                c.when, c.robot = day, r.index
                s.cases.append(c)
                left -= c.op["m"]
                waiting.remove(c)
                done.append(c)
            sessions.append(s)
    return Plan(sessions, done, waiting, cases, robots, weeks, start, session_len, deadline)


# --------------------------------------------------------------------------- economics and alerts
def robot_cost(plan: Plan, robot: Robot) -> tuple[float, float]:
    """(robot cost, DRG revenue handled) for one robot over the planning horizon."""
    c = CONTRACTS[robot.contract]
    cases = [x for x in plan.done if x.robot == robot.index]
    cost = c["fixed"] * plan.weeks / OPERATING_WEEKS + c["var"] * len(cases)
    return cost, sum(x.op["t"] for x in cases)


def summary(plan: Plan) -> dict:
    avail = sum(s.length for s in plan.sessions)
    used = sum(s.used for s in plan.sessions)
    cost = drg = 0.0
    for r in plan.robots:
        c, d = robot_cost(plan, r)
        cost += c
        drg += d
    cancers = [c for c in plan.cases if c.cancer]
    done_c = [c for c in plan.done if c.cancer]
    return dict(cancers=len(cancers), on_time=sum(not c.late for c in done_c), late=sum(c.late for c in done_c),
                unscheduled=sum(c.cancer for c in plan.waiting), benign=len(plan.cases) - len(cancers),
                benign_done=sum(not c.cancer for c in plan.done), available=avail, used=used,
                utilisation=used / avail if avail else 0.0, cost=cost, drg=drg,
                ratio=(cost / drg) if drg else (float("inf") if cost else 0.0))


def _alert(severity, title, text="", items=None):
    return dict(severity=severity, title=title, text=text, items=items or [])


def fmt_day(d: dt.date) -> str:
    return d.strftime("%a %d %b")


def deadline_alerts(plan: Plan) -> list[dict]:
    A = []
    cancers = [c for c in plan.cases if c.cancer]
    before = [c for c in cancers if c.due < plan.start]
    late = [c for c in plan.done if c.late and c.due >= plan.start]
    unsched = [c for c in plan.waiting if c.cancer]
    tight = [c for c in plan.done if c.cancer and not c.late and c.margin <= 3]
    has_multi = any(r.type == "multi" for r in plan.robots)

    def why(c):
        out = ""
        if not has_multi and not c.op["cr"]:
            out += " Needs a multi-purpose robot."
        if c.op["m"] > plan.session_len:
            out += " Does not fit in a session of this length."
        return out

    if before:
        A.append(_alert("critical", f"{len(before)} cancer patient(s) already past the {plan.deadline}-day deadline before planning starts",
                        "These patients are scheduled first, but the deadline cannot be met.",
                        [f"{c.code} {c.op['n']}: due {fmt_day(c.due)}, " + (f"scheduled {fmt_day(c.when)}" if c.when else "not scheduled") for c in before]))
    if late:
        A.append(_alert("critical", f"{len(late)} cancer patient(s) scheduled after the deadline",
                        "Add sessions or a robot, use longer sessions, or stop benign operations until these patients are treated.",
                        [f"{c.code} {c.op['n']}: due {fmt_day(c.due)}, scheduled {fmt_day(c.when)} ({-c.margin} days late)" for c in late]))
    if unsched:
        A.append(_alert("critical", f"{len(unsched)} cancer patient(s) not scheduled within the planning horizon", "",
                        [f"{c.code} {c.op['n']}: due {fmt_day(c.due)}.{why(c)}" for c in unsched]))
    if tight:
        A.append(_alert("warning", f"{len(tight)} cancer patient(s) scheduled within 3 days of the deadline",
                        "Any cancellation will make these patients late. Keep a back-up slot.",
                        [f"{c.code} {c.op['n']}: scheduled {fmt_day(c.when)}, due {fmt_day(c.due)}" for c in tight]))
    if not A:
        A.append(_alert("ok", f"All {len(cancers)} cancer patients are scheduled within {plan.deadline} days of listing"
                        if cancers else "No cancer patients on the list"))
    return A


def economic_alerts(plan: Plan) -> list[dict]:
    A, S = [], summary(plan)
    U = S["utilisation"]
    if U < 0.40:
        A.append(_alert("critical", f"Robot time largely unused: {U:.0%} of the available time",
                        "The fixed cost of the robot is spread over too few operations. Reduce the number of sessions, share the "
                        "robot with the cancer surgery of other specialties, or prefer a price-per-operation contract."))
    elif U < 0.70:
        A.append(_alert("warning", f"Low use of robot time: {U:.0%} of the available time",
                        "Consider fewer sessions or interdisciplinary use with other cancer specialties."))
    for r in plan.robots:
        ss = [s for s in plan.sessions if s.robot.index == r.index]
        av, us = sum(s.length for s in ss), sum(s.used for s in ss)
        empty = sum(not s.cases for s in ss)
        if av and us / av < 0.30:
            A.append(_alert("warning", f"{r.label} ({'colorectal only' if r.type == 'colon' else 'multi-purpose'}) used {us / av:.0%}",
                            f"{empty} of {len(ss)} sessions have no operation. "
                            + ("A multi-purpose robot could take the cancer surgery of other specialties." if r.type == "colon"
                               else "Fewer weekly sessions would be enough.")))
        rc, rd = robot_cost(plan, r)
        if rc and (not rd or rc / rd > 1):
            A.append(_alert("warning", f"{r.label} ({CONTRACTS[r.contract]['n'].lower()}) costs "
                            + (f"{rc / rd:.2f}" if rd else "-") + " per euro of DRG",
                            f"€{rc:,.0f} of robot cost for €{rd:,.0f} of DRG revenue in this period." if rd
                            else f"€{rc:,.0f} of fixed cost and no operation in this period."))
    if S["ratio"] > 1:
        A.append(_alert("critical", f"Robot cost exceeds the DRG revenue it handles (ratio {S['ratio']:.2f})",
                        f"With the current contracts the robots cost €{S['cost']:,.0f} in this period for €{S['drg']:,.0f} of "
                        "DRG revenue, which must also pay for the whole hospital stay."))
    elif S["ratio"] > 0.8:
        A.append(_alert("warning", f"Robot cost close to the DRG revenue it handles (ratio {S['ratio']:.2f})",
                        "Little room is left to pay for the rest of the hospital stay."))
    benign_done = [c for c in plan.done if not c.cancer]
    missing = [c for c in plan.done if c.late] + [c for c in plan.waiting if c.cancer]
    rob = {r.index: r for r in plan.robots}
    blocking = [b for b in benign_done if any(rob[b.robot].accepts(m.op) for m in missing)]
    affected = [m for m in missing if any(rob[b.robot].accepts(m.op) for b in blocking)]
    if blocking:
        A.append(_alert("critical", f"Improper use: {len(blocking)} benign operation(s) scheduled while {len(affected)} cancer "
                        "patient(s) miss the deadline on the same robots",
                        "Robot time given to benign surgery is taken from patients with cancer. Switch off benign operations "
                        "or move them until the cancer list is clear."))
    if S["used"]:
        lv = [c for c in benign_done if c.op["lv"]]
        lv_share = sum(c.op["m"] for c in lv) / S["used"]
        if lv_share > 0.15:
            A.append(_alert("warning", f"Improper use: {lv_share:.0%} of robot time on short benign operations",
                            f"{len(lv)} operations (cholecystectomy, bariatric surgery). They have a low DRG tariff and no proven "
                            "benefit with the robot; with the rental-plus-consumables contract the consumables alone cost more "
                            "than the DRG of a cholecystectomy."))
        lb_share = sum(c.op["m"] for c in benign_done if not c.op["lv"]) / S["used"]
        if lb_share > 0.30:
            A.append(_alert("info", f"{lb_share:.0%} of robot time on longer benign operations",
                            "Ileocaecal, diverticular, Hartmann reversal and antireflux surgery share the DRGs of cancer surgery "
                            "and cost about the same per euro of DRG, but complications are frequent and cancer surgery comes first."))
    if not A:
        A.append(_alert("ok", f"Economically consistent use: {U:.0%} of robot time used, robot cost {S['ratio']:.2f} per euro of DRG"))
    return A


def schedule_table(plan: Plan):
    """One row per scheduled or unscheduled patient (for display and download)."""
    import pandas as pd
    rows = []
    for s in plan.sessions:
        for c in s.cases:
            rows.append({"Date": s.day, "Robot": s.robot.label,
                         "Robot type": "colorectal only" if s.robot.type == "colon" else "multi-purpose",
                         "Contract": CONTRACTS[s.robot.contract]["n"], "Code": c.code, "Operation": c.op["n"],
                         "Group": GROUP_NAME[c.op["g"]], "Minutes": c.op["m"], "Listed on": c.listed, "Due": c.due,
                         "Status": ("late by %d days" % -c.margin if c.late else "on time") if c.cancer else "benign"})
    for c in plan.waiting:
        rows.append({"Date": None, "Robot": "", "Robot type": "", "Contract": "", "Code": c.code, "Operation": c.op["n"],
                     "Group": GROUP_NAME[c.op["g"]], "Minutes": c.op["m"], "Listed on": c.listed, "Due": c.due,
                     "Status": "not scheduled"})
    return pd.DataFrame(rows)


def example_list(today: dt.date) -> list[dict]:
    mix = [("COLON", 3), ("RECTUM", 8), ("PROSTATE", 2), ("COLON", 12), ("LUNG", 5), ("PD", 9), ("KIDNEY", 1), ("CHOLE", 20),
           ("LIVER_MIN", 4), ("LIVER_MAJ", 15), ("SIGMOID", 30), ("BLADDER", 6), ("PROSTATE", 14), ("STOMACH", 10),
           ("ILEOCAECAL", 25), ("OVARY", 3), ("COLON", 1), ("RECTUM", 18), ("SLEEVE", 40), ("PROSTATE", 7), ("CHOLE", 35),
           ("OESOPHAGUS", 11), ("HARTMANN", 50), ("KIDNEY", 16), ("ANTIREFLUX", 28), ("DP", 6), ("LUNG", 13), ("BYPASS", 45),
           ("CHOLE", 12), ("RECTUM", 2)]
    return [dict(code=str(i + 1), op=k, date=today - dt.timedelta(days=d)) for i, (k, d) in enumerate(mix)]


# --------------------------------------------------------------------------- optimiser
W_UNSCHEDULED, W_LATE_DAY, W_TIGHT = 1e7, 1e5, 1e3


def clinical_score(plan: Plan) -> float:
    """Lower is better: unscheduled cancers, then days beyond the deadline, then tight margins."""
    sc = 0.0
    for c in plan.cases:
        if not c.cancer:
            continue
        if c.when is None:
            sc += W_UNSCHEDULED
        elif c.margin < 0:
            sc += W_LATE_DAY * -c.margin
        elif c.margin <= 3:
            sc += W_TIGHT
    return sc


def _milp(items, cand, start, session_len, capacity_left, session_open, session_value, time_limit):
    """items: list of (case, allowed session indices, objective coefficient per session index)."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import lil_matrix
    pairs, cost = [], []
    for ii, (c, opts) in enumerate(items):
        for si, coef in opts:
            pairs.append((ii, si))
            cost.append(coef)
    ny = len(cand)
    nx = len(pairs)
    if nx == 0:
        return {}, "optimal"
    y_cost = np.array([0.0 if session_open[si] else session_value for si in range(ny)])
    c_vec = np.concatenate([np.array(cost, dtype=float), y_cost])
    A = lil_matrix((len(items) + ny, nx + ny))
    for k, (ii, si) in enumerate(pairs):
        A[ii, k] = 1
        A[len(items) + si, k] = items[ii][0].op["m"]
    for si in range(ny):
        A[len(items) + si, nx + si] = -capacity_left[si]
    lb = np.full(len(items) + ny, -np.inf)
    ub = np.concatenate([np.ones(len(items)), np.zeros(ny)])
    yl = np.array([1.0 if session_open[si] else 0.0 for si in range(ny)])
    res = milp(c_vec, constraints=LinearConstraint(A.tocsr(), lb, ub), integrality=np.ones(nx + ny),
               bounds=Bounds(np.concatenate([np.zeros(nx), yl]), np.ones(nx + ny)),
               options={"time_limit": time_limit, "disp": False})
    status = "optimal" if res.status == 0 else "best solution found within the time limit"
    if res.x is None:
        return None, "no solution within the time limit"
    out = {}
    for k, (ii, si) in enumerate(pairs):
        if res.x[k] > 0.5:
            out[ii] = si
    return out, status


def optimise(patients: list[dict], robots: list[Robot], start: dt.date, weeks: int = 6, session_len: int = 720,
             deadline: int = 30, allow_benign: bool = True, session_value: float = 2000.0,
             use_all_weekdays: bool = True, time_limit: float = 20.0):
    """Exact optimisation in two stages (mixed-integer linear programming, HiGHS via SciPy).

    Stage 1 - cancer patients only: (a) schedule every cancer patient, (b) no day beyond the deadline, (c) a margin of
    more than 3 days when possible, then (d) put each operation on the robot where DRG tariff minus robot cost is
    highest and (e) open as few sessions as possible.
    Stage 2 - benign patients, in the time left and in new sessions only if worth more than `session_value`; benign
    operations whose robot cost exceeds their DRG tariff are left to laparoscopy.
    Safety net: if the result is clinically worse than the rule-based plan (possible when the solver stops at the time
    limit), the rule-based cancer schedule is kept and stage 2 is run on top of it.
    Candidate sessions: every weekday for each robot (use_all_weekdays) or the weekday pattern set for each robot.
    Returns (plan, info).
    """
    cases = [Case(str(p["code"]), OP[p["op"]], p["date"],
                  p["date"] + dt.timedelta(days=deadline) if OP[p["op"]]["g"] != "ben" else None) for p in patients]
    cand = []
    for d in range(weeks * 7):
        day = start + dt.timedelta(days=d)
        if day.weekday() <= 4:
            for r in robots:
                if use_all_weekdays or day.weekday() in DAY_PATTERN[r.sessions_per_week]:
                    cand.append((day, r))
    ny = len(cand)
    value = lambda c, r: c.op["t"] - CONTRACTS[r.contract]["var"]
    fits = lambda c, si: cand[si][1].accepts(c.op) and c.op["m"] <= session_len and cand[si][0] >= c.listed

    # ---- stage 1: cancers
    canc = [c for c in cases if c.cancer]
    items = []
    for c in canc:
        opts = []
        for si in range(ny):
            if not fits(c, si):
                continue
            day, r = cand[si]
            late = (day - c.due).days
            coef = -W_UNSCHEDULED - value(c, r) + 0.5 * (day - start).days
            coef += W_LATE_DAY * late if late > 0 else (W_TIGHT if late > -4 else 0)
            opts.append((si, coef))
        items.append((c, opts))
    t1 = time_limit * (0.7 if allow_benign else 1.0)
    sol, status1 = _milp(items, cand, start, session_len, [session_len] * ny, [False] * ny, session_value, t1)
    used = [0] * ny
    assign = {}
    if sol is not None:
        for ii, si in sol.items():
            assign[items[ii][0].code + "#" + str(id(items[ii][0]))] = si
            used[si] += items[ii][0].op["m"]

    def build(assignments):
        for c in cases:
            c.when = c.robot = None
        sess = {}
        for c in cases:
            si = assignments.get(c.code + "#" + str(id(c)))
            if si is None:
                continue
            day, r = cand[si]
            c.when, c.robot = day, r.index
            sess.setdefault(si, Session(day, r, session_len)).cases.append(c)
        sessions = [sess[si] for si in sorted(sess, key=lambda i: (cand[i][0], cand[i][1].index))]
        for s_ in sessions:
            s_.cases.sort(key=lambda c: (not c.cancer, c.due or c.listed))
        return Plan(sessions, [c for s_ in sessions for c in s_.cases], [c for c in cases if c.when is None],
                    cases, robots, weeks, start, session_len, deadline)

    # safety net against the rule-based plan (cancer part only)
    rule = schedule([dict(code=c.code, op=c.op["k"], date=c.listed) for c in canc], robots, start, weeks, session_len,
                    deadline, allow_benign=False)
    opt_plan = build(assign)
    used_rule = False
    if sol is None or clinical_score(opt_plan) > clinical_score(rule):
        used_rule = True
        idx = {(d, r.index): si for si, (d, r) in enumerate(cand)}
        assign, used = {}, [0] * ny
        by_code = {}
        for c in canc:
            by_code.setdefault(c.code, []).append(c)
        for rc in rule.done:
            si = idx.get((rc.when, rc.robot))
            if si is None:
                continue
            c = next(x for x in by_code[rc.code] if x.code + "#" + str(id(x)) not in assign)
            assign[c.code + "#" + str(id(c))] = si
            used[si] += c.op["m"]

    # ---- stage 2: benign in the time left
    status2 = "optimal"
    if allow_benign:
        ben = [c for c in cases if not c.cancer]
        items2 = []
        for c in ben:
            opts = []
            for si in range(ny):
                if not fits(c, si) or used[si] + c.op["m"] > session_len:
                    continue
                v = value(c, cand[si][1])
                if v <= 0:
                    continue
                opts.append((si, -v - 2.0 * (start - c.listed).days))
            items2.append((c, opts))
        sol2, status2 = _milp(items2, cand, start, session_len, [session_len - u for u in used],
                              [u > 0 for u in used], session_value, time_limit - t1 if not used_rule else time_limit * 0.3)
        if sol2:
            for ii, si in sol2.items():
                c = items2[ii][0]
                assign[c.code + "#" + str(id(c))] = si
    plan = build(assign)
    rec = {}
    for r in robots:
        per_week = {}
        for s_ in plan.sessions:
            if s_.robot.index == r.index:
                wk = (s_.day - start).days // 7
                per_week[wk] = per_week.get(wk, 0) + 1
        rec[r.index] = max(per_week.values(), default=0)
    status = "optimal" if status1 == "optimal" and status2 == "optimal" and not used_rule else (
        "rule-based cancer schedule kept (solver time limit), benign optimised" if used_rule else "best solution found within the time limit")
    return plan, dict(status=status, recommended_sessions=rec, benign_laparoscopy=[c for c in plan.waiting if not c.cancer],
                      candidate_sessions=ny)
