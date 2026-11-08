# Robotic Theatre Planner

A scheduling tool for shared robotic operating theatres. It fills robotic sessions with cancer patients first, in
order of deadline (30 days from listing by default), uses the remaining time for benign operations, and flags missed
deadlines and uneconomic use of the robots.

The tool is based on the hospital-level model described in:

> Ricci C, D'Ambra V, Fichera M, Alberici L, Ingaldi C, Casadei R. *Who should fill the robot? Operating-room capacity,
> approach-neutral DRG payment and interdisciplinary use of robotic platforms in major general surgery: a
> hospital-level model.* [Journal and DOI to be added]

**Live app:** [URL to be added]

## What it does

- **Robots:** 1 to 6 robots. For each robot: type (multi-purpose or colorectal only), sessions per week (1-5) and
  contract (rental + consumables, price per operation, high rental + consumables).
- **Waiting list:** edit it in the app or upload an Excel/CSV file with three columns: `code` (progressive number),
  `operation`, `date` of listing. Operation names are recognised in English and Italian (for example *Whipple*, *DCP*,
  *PSX*, *segmentectomia*, *colecistectomia*). Generic names such as "liver" or "pancreas" are rejected with a request
  to specify the operation.
- **Scheduling:** whole operations only, no session overrun; cancer patients by deadline, benign patients by
  listing date in the time left; colorectal-only robots are filled first each day.
- **Cancer deadline alerts:** patients already past the deadline, scheduled late, not scheduled, or scheduled within
  3 days of the deadline.
- **Economic use alerts:** robot time used below 40% (critical) or 40-70% (warning); single robots used below 30%;
  robot cost above the DRG revenue it handles; benign operations scheduled while cancer patients miss the deadline on
  the same robots; more than 15% of robot time on short benign operations (cholecystectomy, bariatric surgery).
- **Optimiser:** finds the best plan in strict order of priority. 1) Clinical: every cancer patient scheduled, no day
  beyond the deadline, a margin of more than 3 days when possible. 2) Economic: each operation on the robot where DRG
  tariff minus robot cost is highest; benign operations whose robot cost exceeds their DRG tariff are left to
  laparoscopy. 3) Use: the fewest sessions needed, with the recommended number of weekly sessions for each robot. It
  uses mixed-integer linear programming (HiGHS, through SciPy) in two stages (cancer patients, then benign patients in
  the time left). A safety net keeps the rule-based cancer schedule whenever the solver, stopped by the time limit,
  would return a clinically worse plan, so the optimised plan is never clinically worse than the rule-based one.
- **Output:** rule-based and optimised schedules by day and robot, downloadable as Excel.

## Files

All files are in one folder.

```
app.py                     Streamlit interface
core.py                    Catalogue of operations, contracts, scheduling, optimiser, parsing and alerts (source of truth)
ui.py                      Visual components (same look as the web version)
test_core.py               Unit tests (pytest)
requirements.txt           Python dependencies
procedures.csv             Operating-room minutes and DRG tariffs used by the app (reference copy)
contracts.csv              Contract costs used by the app (reference copy)
example_waiting_list.csv   Example list to try the upload
LICENSE                    All rights reserved
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Run the tests with `pip install pytest && pytest -q test_core.py`.

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository and upload all files of this folder.
2. Go to <https://share.streamlit.io>, sign in with GitHub and choose **Create app**.
3. Select the repository, branch `main` and main file `app.py`; choose Python 3.11 or later; click **Deploy**.
4. Copy the app URL into this README, into the manuscript (Results and Data availability) and into the app's
   *Methods* tab if you wish.

## Model inputs

| Input | Value |
|---|---|
| Operating-room minutes | Published robotic operative time + 60 min (anaesthesia, positioning, docking, recovery) + 30 min turnover |
| Pancreas | Pancreatoduodenectomy 565 min; distal pancreatectomy 328 min |
| Liver | Minor resection 316 min; major hepatectomy 372 min (Sucandy et al., Am Surg 2023) |
| Contracts (VAT included) | Rental + consumables €534,360/year + €4,844/operation; price per operation €3,226; high rental + consumables €906,216/year + €2,490/operation |
| DRG tariffs | Lombardy list, 40% of patients in the DRG with complications |
| Operating weeks | 46 per year |

All values are in `planner/core.py`; change them there to adapt the tool to another hospital or country.

## Privacy

The app does not store data. Patient lists exist only in the user's browser session and are lost when the session
ends. Use progressive codes, never names or other identifiers.

## Disclaimer

Scheduling support only. Clinical decisions, including the priority of individual patients, remain with the surgeon.

## Copyright

© 2026 Claudio Ricci, University of Bologna, IRCCS Azienda Ospedaliero-Universitaria di Bologna. All rights reserved.
See `LICENSE`. Contact: claudio.ricci6@unibo.it
