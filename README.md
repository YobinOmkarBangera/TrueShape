# TrueShape (Team Dhurandhar)

**Follow The Money: Innovation Challenge (IIM Bangalore and PayU), 2026. Problem: "The Bakery That Takes Bets".**

> Volume can change. Shape shouldn't.

TrueShape watches how every shop takes payments and flags the ones whose payments stop looking like the business they registered as. Shops that simply grow (festivals, a new branch, late-night orders, online selling) are left alone. Because a payment provider sees all its merchants at once, TrueShape also links shops through the punters they share: catch one front, find the ring.

It is a transparent comparison engine: plain statistics and stated rules, no machine learning, no fraud labels needed. Every decision comes with a sentence that explains it.

## Start it

You need Python 3.9 or newer ([python.org/downloads](https://www.python.org/downloads/)). On Windows, tick **Add python.exe to PATH** during setup.

**Easiest:** double-click the start file. The first run sets everything up and builds the data (a few minutes); later runs start in about 10 seconds. The browser opens by itself.

| Computer | Double-click |
|---|---|
| Windows | `start_windows.bat` (if Windows SmartScreen warns: More info, Run anyway) |
| Mac | `start_mac.command` (if macOS blocks it: right-click, Open, Open) |

**Or from a terminal**, inside this folder:

```bash
# Windows
python -m pip install -r requirements.txt
python run.py

# Mac / Linux
python3 -m pip install -r requirements.txt
python3 run.py
```

Open http://127.0.0.1:8000 if the browser does not open by itself. Stop the app with Ctrl+C. If port 8000 is busy, it uses the next free one and prints the address.

**Linux:** `bash start_mac.command` (on Ubuntu or Debian you may first need `sudo apt install python3-venv`).

**Mac says the file "could not be executed" (common after copying from Windows or a zip):** open Terminal in this folder and run `bash start_mac.command`.

**Check that it works on this computer:**

```bash
python check.py        # Windows  (python3 check.py on Mac / Linux)
```

It runs 25 checks in about a minute: the data is identical to ours, every number in our deck is reproduced, the stress tests hold, the link test never looks ahead in time, and every screen's API answers. Tested on Python 3.9, 3.10, 3.13 and 3.14, with the oldest and newest allowed package versions. It needs about 400 MB of memory.

**No Python?** Open `dist/trueshape_demo.html` in any browser. It is a single-file copy of the app with every answer pre-computed, so it works offline (Try it live offers fixed examples instead of random ones, and CSV upload is off).

## The screens

| Tab | Question it answers |
|---|---|
| Overview | Who needs attention today? Filter by city and category; every shop is drawn as its own small shape. |
| Category shapes | What does normal look like for a bakery, a kirana and a mobile shop? Why don't festivals cause false alarms? |
| Case file (click any shop) | Why was this shop flagged? Shape, declared vs actual, four tests, the habits, shared payers with shops on hold, raw payments, response ladder, merchant check-in. |
| Try it live | Generate a brand-new shop (any category, city and scenario) and watch the engine judge it. Or upload a CSV. |
| Results | How well does it work: against two simpler rules, on 20 new datasets it never saw, with each part switched off, if our ring assumptions are wrong, by group, on the hardest honest shops, and where it falls short. |
| How it works | The six checks, the data, the guardrails, the research and RBI rules behind each part, the build. |

## The data

`data/` holds the simulated dataset: 168 shops (bakery, kirana, mobile and accessories, in Hyderabad and Mumbai), 1 Jul to 3 Nov 2026, about 16.6 lakh payments. It is the same data as the Excel data pack (`Raw_Data_Pack.zip`, where dates are in DD-MM-YYYY form). The dataset (about 140 MB) is not stored in this folder: on the first run, `run.py` generates it from fixed random seeds, so everyone gets exactly the same payments.

Real people use more than one shop, so some payers appear at several shops: neighbours share local regulars, a few punters also buy genuinely at honest shops (most often online sellers), and the betting fronts of each city share punters through one betting ring (half of each front's punters, in the main dataset). Inside any one shop, every payer keeps one ID.

The `answer_key` columns are never read by the detection logic. They are used for two things only: scoring accuracy, and playing the merchant's side of the "What changed?" check-in (honest shops give their true reason, fronts give a false excuse or stay silent).

## How the engine decides

1. **Fingerprint**: each day, the last 7 days of payments become six habits: payment sizes, shop hours, who pays, where the money goes, what drives sales, and volume.
2. **Self test**: compare with the shop's own first 45 days (break point analysis).
3. **Peer test**: subtract what the typical shop of the same category in the same city did that week, so festival rushes cancel out (peer group analysis).
4. **Context test**: check cricket match days and the merchant's own answer to "What changed?".
5. **Link test**: of the shop's new, out-of-state payers in the last 14 days, how many also paid a shop that was already on hold? Neighbours sharing local regulars do not count, and only shops held on an earlier day are used, so it never looks ahead.
6. **Score and respond**: unexplained signs become a 0-100 mismatch score. Ladder: All clear, Watch, Ask, Delay payouts, Hold funds, Suspend and report.

Guardrails: fewer than two drifting signs keep a shop at Watch. The shop gets a day to answer the check-in before any delay, unless money leaves the moment it arrives. An answer counts from the day it arrives. Levels go up one step at a time from Delay, and come down one step at a time. No answer can delay payouts but freezes funds only on strong evidence; only money that leaves at once can lead to a suspension, and only a person lifts one. A few shared payers go to an analyst while money keeps flowing; many cannot be explained away.

## Results on the main dataset

| | Fronts stopped (of 18) | Honest shops disrupted (of 150) |
|---|---|---|
| **TrueShape** | **18** | **0** |
| TrueShape without the link test | 14 | 0 |
| Sales-limit rule (2x the shop's normal) | 14 | 104 |
| Smarter sales rule (2x the typical shop in its group) | 9 | 20 |

Bold fronts had payouts delayed 3-4 days after their first bet; careful ones 9-20 days. 6 honest shops with genuinely unusual changes were asked one question and cleared; 0 of the 46 honest shops whose business really changed were disrupted.

## Tested on data it never saw

The thresholds were set on the main dataset. To check that TrueShape is not tuned to it, `validate.py` builds new datasets with new shops, new payments and a new cricket schedule, and runs the same engine unchanged.

**20 new datasets, 3,360 shops (360 fronts, 3,000 honest):**

| | Fronts stopped | Honest shops disrupted |
|---|---|---|
| **TrueShape** | **359 = 99.7% (95% range 98.4-100.0%)** | **0 = 0.0% (95% range 0.0-0.1%)** |
| Sales-limit rule | 84.4% | 2,065 = 68.8% |
| Smarter sales rule | 57.5% | 326 = 10.9% |

Bold fronts: 100.0% stopped, median 3 days after the first bet. Careful fronts: 99.4% stopped, median 13 days. Ranges are 95% Wilson intervals.

**What each part adds** (same datasets, one part switched off at a time):

| Version | Fronts stopped | Honest shops disrupted | Honest shops asked |
|---|---|---|---|
| Full TrueShape | 99.7% | 0 | 117 |
| No link test | 97.2% | 0 | 117 |
| No peer test | 99.7% | 1 | 82 |
| No check-in | 99.4% | 99 | 117 |
| No two-habit rule | 100.0% | 0 | 253 |

**If our assumptions about rings are wrong:**

| Scenario | Fronts stopped | Honest shops disrupted |
|---|---|---|
| Rings share 2 in 10 punters (10 new datasets) | 180 of 180 (100.0%) | 0 of 1,500 |
| Rings share 1 in 10 punters (10 new datasets) | 179 of 180 (99.4%) | 0 of 1,500 |
| 4 times more punters also buy at honest shops (10 new datasets) | 180 of 180 (100.0%) | 0 of 1,500 |

**Stress tests** (`check.py` reproduces the main-dataset ones):

- Every front gives whichever answer helps it most, or stays silent: 17 of 18 still stopped on the main dataset, 99.4% on the new datasets.
- The 6 honest shops that get asked ignore the check-in, or only tap "Something else": their payouts are delayed until they answer, none is suspended. In practice the check-in also goes by SMS and WhatsApp with a reminder call before any delay.
- Try it live, 920 brand-new random shops: no honest shop disrupted and every bold front stopped; 3 careful fronts (late-starting mobile shops) stay on Watch, because the single-shop simulator has no portfolio for the link test.

## Built on research and on the rules

- Bolton, R. J. and Hand, D. J. (2001). Unsupervised profiling methods for fraud detection. *Credit Scoring and Credit Control VII*. Peer group analysis and break point analysis: the basis of our peer test and self test.
- Weston, D. J. et al. (2008). Plastic card fraud detection using peer group analysis. *Advances in Data Analysis and Classification*.
- Oztas, B. et al. (2024). Transaction monitoring in anti-money laundering: a qualitative analysis and points of view from industry. *Future Generation Computer Systems*. Rule-based monitoring raises too many false alarms; explainability is required.
- Fronzetti Colladon, A. and Remondi, E. (2017). Using social network analysis to prevent money laundering. *Expert Systems with Applications*, 67, 49-58. Shared links reveal groups that single-account checks miss: the basis of our link test.
- Cheng, D. et al. (2023). Anti-money laundering by group-aware deep graph learning. *IEEE Transactions on Knowledge and Data Engineering*.
- Altman, E. et al. (2023). Realistic synthetic financial transactions for anti-money laundering models. Synthetic data gives complete labels, so it is a fair way to compare methods.
- Reserve Bank of India (15 Sep 2025). Master Direction on Regulation of Payment Aggregators: para 13(h) monitor merchants' transactions after onboarding; 13(e) allot the appropriate MCC; 13(i) register with FIU-IND; 16 settlement timelines are set transparently in the merchant agreement (our payout delay is a risk clause there).
- Prevention of Money Laundering Act, 2002: suspicious transaction reports to FIU-IND.

## Files

```
run.py                 start the app
start_windows.bat      double-click start for Windows
start_mac.command      double-click start for Mac (and Linux: bash start_mac.command)
requirements.txt       Python packages
check.py               self-check: 25 tests that prove it works and reproduce every result
validate.py            out-of-sample test on new datasets, the ablation study and the ring sensitivity
backend/simulator.py   simulated payment data
backend/engine.py      the detection logic
backend/service.py     turns engine output into API answers
backend/app.py         FastAPI endpoints (docs at /docs)
backend/validation.json  results written by validate.py, shown on the Results screen
frontend/              the screens (HTML, CSS, JavaScript, SVG charts)
build_demo.py          builds dist/trueshape_demo.html, a single-file demo that works offline
dist/trueshape_demo.html  the offline demo (open in any browser)
data/                  the simulated dataset (created on the first run)
```

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/api/overview` | Every shop with status, score, shape and reasons |
| GET | `/api/profiles` | Normal shape of each category, festival check |
| GET | `/api/results` | Accuracy, rule comparison, new-data test, ablation, groups, hard cases, every front |
| GET | `/api/merchants/{id}` | One shop's full case file, including shops on hold it shares payers with |
| POST | `/api/merchants/{id}/reply` | `{"reason": "new_branch"}` judges a check-in answer |
| POST | `/api/simulate` | `{"category": "kirana", "city": "Mumbai", "scenario": "front", "start": "mid"}` |
| POST | `/api/analyze` | Upload a CSV (form fields: file, category, city) |
| GET | `/api/sample.csv` | A sample file in the upload format |

All shops, payers and payments are simulated. Festival dates are the real 2026 dates; the cricket schedule is invented. The link test needs the whole portfolio, so it does not run in Try it live or on an uploaded file.
