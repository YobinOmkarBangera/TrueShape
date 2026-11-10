# TrueShape (Team Dhurandhar)

**Follow The Money: Innovation Challenge (IIM Bangalore and PayU), 2026. Problem: "The Bakery That Takes Bets".**

> Volume can change. Shape shouldn't.

TrueShape watches how every shop takes payments and flags the ones whose payments stop looking like the business they registered as. Shops that simply grow (festivals, a new branch, late-night orders, online selling) are left alone.

It is a transparent comparison engine: plain statistics and stated rules, no machine learning, no fraud labels needed. Every decision comes with a sentence that explains it.

## Start it

You need Python 3.9 or newer ([python.org/downloads](https://www.python.org/downloads/)). On Windows, tick **Add python.exe to PATH** during setup.

**Easiest:** double-click the start file. The first run sets everything up (about a minute); later runs start in about 10 seconds. The browser opens by itself.

| Computer | Double-click |
|---|---|
| Windows | `start_windows.bat` |
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

**No Python?** Open `dist/trueshape_demo.html` in any browser. It is a single-file copy of the app with every answer pre-computed, so it works offline (Try it live offers fixed examples instead of random ones, and CSV upload is off).

## The screens

| Tab | Question it answers |
|---|---|
| Overview | Who needs attention today? Filter by city and category; every shop is drawn as its own small shape. |
| Category shapes | What does normal look like for a bakery, a kirana and a mobile shop? Why don't festivals cause false alarms? |
| Case file (click any shop) | Why was this shop flagged? Shape, declared vs actual, three tests, six habits, raw payments, response ladder, merchant check-in. |
| Try it live | Generate a brand-new shop (any category, city and scenario) and watch the engine judge it. Or upload a CSV. |
| Results | How well does it work, against two simpler rules, by group, on the hardest honest shops, and where it falls short. |
| How it works | The five steps, the data, the guardrails, the build. |

## The data

`data/` holds the simulated dataset: 168 shops (bakery, kirana, mobile and accessories, in Hyderabad and Mumbai), 1 Jul to 3 Nov 2026, about 16.6 lakh payments. It is the same data as the Excel data pack. The dataset (about 140 MB) is not stored in this repository: on the first run, `run.py` generates it from fixed random seeds (about 30 seconds), so everyone gets exactly the same payments. The `answer_key` columns are never read by the detection logic. They are used for two things only: scoring accuracy, and playing the merchant's side of the "What changed?" check-in (honest shops give their true reason, fronts give a false excuse or stay silent).

## How the engine decides

1. **Fingerprint**: each day, the last 7 days of payments become six habits: payment sizes, shop hours, who pays, where the money goes, what drives sales, and volume.
2. **Self test**: compare with the shop's own first 45 days.
3. **Peer test**: subtract what the typical shop of the same category in the same city did that week, so festival rushes cancel out.
4. **Context test**: check cricket match days and the merchant's own answer to "What changed?".
5. **Score and respond**: unexplained habits become a 0-100 mismatch score. Fewer than two drifting habits keeps a shop at Watch. Ladder: All clear, Watch, Ask, Delay payouts, Hold funds, Suspend and report.

## Results on the simulated data

| | Fronts stopped (of 18) | Honest shops disrupted (of 150) |
|---|---|---|
| **TrueShape** | **14** | **0** |
| Sales-limit rule (2x the shop's normal) | 14 | 104 |
| Smarter sales rule (2x the typical shop in its group) | 9 | 20 |

Bold fronts had payouts delayed 2-4 days after their first bet; careful ones 16-18 days. Four careful fronts that started late and stayed small are on Watch, not stopped. Six honest shops with genuinely unusual changes were asked one question and cleared.

## Files

```
run.py                 start the app
start_windows.bat      double-click start for Windows
start_mac.command      double-click start for Mac
requirements.txt       Python packages
backend/simulator.py   simulated payment data
backend/engine.py      the detection logic
backend/service.py     turns engine output into API answers
backend/app.py         FastAPI endpoints (docs at /docs)
frontend/              the screens (HTML, CSS, JavaScript, SVG charts)
build_demo.py          builds dist/trueshape_demo.html, a single-file demo that works offline
dist/trueshape_demo.html  the offline demo (open in any browser)
data/                  the simulated dataset (created on the first run, not in the repo)
```

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/api/overview` | Every shop with status, score, shape and reasons |
| GET | `/api/profiles` | Normal shape of each category, festival check |
| GET | `/api/results` | Accuracy, rule comparison, groups, hard cases, every front |
| GET | `/api/merchants/{id}` | One shop's full case file |
| POST | `/api/merchants/{id}/reply` | `{"reason": "new_branch"}` judges a check-in answer |
| POST | `/api/simulate` | `{"category": "kirana", "city": "Mumbai", "scenario": "front", "start": "mid"}` |
| POST | `/api/analyze` | Upload a CSV (form fields: file, category, city) |
| GET | `/api/sample.csv` | A sample file in the upload format |

All shops, payers and payments are simulated. Festival dates are the real 2026 dates; the cricket schedule is invented.
