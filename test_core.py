import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
from core import (OP, Robot, deadline_alerts, economic_alerts, example_list, next_code, parse_rows, schedule,
                          summary)

MON = dt.date(2026, 11, 9)  # a Monday


def test_sessions_never_overrun_and_whole_cases():
    plan = schedule(example_list(MON), [Robot(0, "multi", 5, "A"), Robot(1, "colon", 3, "B")], MON, 6, 720)
    for s in plan.sessions:
        assert s.used <= s.length
    assert len(plan.done) + len(plan.waiting) == len(plan.cases)


def test_cancer_before_benign_and_by_deadline():
    pts = [dict(code="1", op="CHOLE", date=MON - dt.timedelta(days=60)),
           dict(code="2", op="COLON", date=MON - dt.timedelta(days=5)),
           dict(code="3", op="COLON", date=MON - dt.timedelta(days=20))]
    plan = schedule(pts, [Robot(0, "multi", 1, "A")], MON, 1, 480)  # one 8-h session fits one colon only
    first = plan.sessions[0].cases[0]
    assert first.code == "3"  # earliest deadline first, benign waits


def test_colorectal_robot_rejects_other_operations():
    pts = [dict(code="1", op="PROSTATE", date=MON)]
    plan = schedule(pts, [Robot(0, "colon", 5, "B")], MON, 2, 720)
    assert plan.waiting and not plan.done
    titles = " ".join(a["title"] for a in deadline_alerts(plan))
    assert "not scheduled" in titles


def test_late_and_improper_use_alerts():
    pts = [dict(code=str(i), op="PD", date=MON - dt.timedelta(days=25)) for i in range(1, 6)]
    pts.append(dict(code="9", op="CHOLE", date=MON - dt.timedelta(days=90)))
    plan = schedule(pts, [Robot(0, "multi", 1, "A")], MON, 4, 720)
    s = summary(plan)
    assert s["late"] + s["unscheduled"] > 0
    assert any(a["severity"] == "critical" for a in deadline_alerts(plan))


def test_underuse_alert_and_cost_ratio():
    plan = schedule([dict(code="1", op="COLON", date=MON)], [Robot(0, "multi", 5, "C")], MON, 4, 720)
    s = summary(plan)
    assert s["utilisation"] < 0.4 and s["ratio"] > 1
    sev = {a["severity"] for a in economic_alerts(plan)}
    assert "critical" in sev


def test_price_per_operation_has_no_fixed_cost():
    plan = schedule([dict(code="1", op="COLON", date=MON)], [Robot(0, "multi", 5, "B")], MON, 4, 720)
    s = summary(plan)
    assert s["cost"] == 3226 and abs(s["ratio"] - 3226 / OP["COLON"]["t"]) < 1e-9


def test_parsing_synonyms_dates_and_ambiguous():
    rows = [["code", "operation", "date"], ["1", "Whipple", "20/10/2026"], ["2", "Liver", "2026-10-20"],
            ["", "segmentectomia", "2026-10-21"], ["4", "appendicectomy", "2026-10-21"], ["5", "PSX", "bad"]]
    out = parse_rows(rows, set())
    assert out[0]["op"] == "PD" and out[0]["date"] == dt.date(2026, 10, 20) and not out[0]["errors"]
    assert "specify" in out[1]["errors"][0]
    assert out[2]["op"] == "LIVER_MIN" and out[2]["code"] == ""
    assert out[3]["errors"] and out[4]["errors"]
    assert next_code(["1", "2", "10", "x"]) == "11"


def test_optimiser_never_clinically_worse_and_compacts_sessions():
    from core import clinical_score, optimise
    robots = [Robot(0, "multi", 5, "A"), Robot(1, "colon", 3, "B")]
    pts = example_list(MON)
    opt, info = optimise(pts, robots, MON, 6, 720, 30, time_limit=20)
    rule = schedule(pts, robots, MON, 6, 720, 30)
    assert clinical_score(opt) <= clinical_score(rule)
    assert len(opt.sessions) < len([s for s in rule.sessions])
    for s in opt.sessions:
        assert s.used <= s.length
    # no benign operation whose robot cost exceeds its DRG tariff
    from core import CONTRACTS
    rob = {r.index: r for r in robots}
    for c in opt.done:
        if not c.cancer:
            assert c.op["t"] > CONTRACTS[rob[c.robot].contract]["var"]
