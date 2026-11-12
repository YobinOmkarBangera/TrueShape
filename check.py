"""
TrueShape self-check: proves the prototype works on this computer and reproduces every number we report.
Run:  python check.py      (Windows)      python3 check.py      (macOS / Linux)
Takes about a minute (longer on the very first run, when the data is generated).
"""
import sys
import time

if sys.version_info < (3, 9):
    sys.exit("TrueShape needs Python 3.9 or newer. You have Python " + sys.version.split()[0] + ".")
try:
    import fastapi, uvicorn, pandas as pd, numpy as np, multipart  # noqa: F401
except ImportError as e:
    sys.exit("A package is missing (" + str(e) + ").\nRun this first:  python -m pip install -r requirements.txt")

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"  ({detail})" if detail else ""))


t0 = time.time()
print(f"Python {sys.version.split()[0]}, pandas {pd.__version__}, numpy {np.__version__}, fastapi {fastapi.__version__}\n")

print("1. Data")
from backend import service as SV, engine as E
from backend import app as A
st = A.S()
tx = pd.read_csv(SV.DATA / "transactions.csv", usecols=["amount_inr", "payer_id"])
check("168 shops, 18 of them betting fronts", len(st.merchants) == 168 and int(st.ev.fraud.sum()) == 18)
check("Same payments on every computer (fixed seeds)",
      len(tx) == 1_660_824 and int(tx.amount_inr.sum()) == 895_295_350 and tx.payer_id.nunique() == 687_847,
      f"{len(tx):,} payments, Rs {int(tx.amount_inr.sum()):,}")

print("\n2. Headline results")
s = st.summary["trueshape"]
check("18 of 18 fronts stopped", s["caught"] == 18, f"{s['caught']}")
check("0 of 150 honest shops disrupted", s["disrupted"] == 0, f"{s['disrupted']}")
check("6 honest shops asked once, then cleared", s["asked_only"] == 6, f"{s['asked_only']}")
f = st.ev[st.ev.fraud & st.ev.caught]
bold, careful = f[f.kind == "front"].days_to_act, f[f.kind == "disguised_front"].days_to_act
check("Bold fronts delayed 3-4 days after the first bet", bold.min() == 3 and bold.max() == 4, f"{int(bold.min())}-{int(bold.max())}")
check("Careful fronts delayed 9-20 days after the first bet", careful.min() == 9 and careful.max() == 20, f"{int(careful.min())}-{int(careful.max())}")
R = st.results()
rules = {r["name"]: (r["caught"], r["disrupted"]) for r in R["rules"]}
check("Sales-limit rule: 14 fronts, 104 honest shops hit", rules["Sales-limit rule"] == (14, 104), str(rules["Sales-limit rule"]))
check("Smarter sales rule: 9 fronts, 20 honest shops hit", rules["Smarter sales rule"] == (9, 20), str(rules["Smarter sales rule"]))
ch = st.ev[~st.ev.fraud & (st.ev.kind != "honest")]
check("0 of 46 honest shops with real business changes disrupted", len(ch) == 46 and int(ch.disrupted.sum()) == 0)

print("\n3. Stress tests")
x = R["stress"]
check("Every front gives its best excuse or stays silent: still 17 stopped", x["fronts_best_excuse"] == 17, f"{x['fronts_best_excuse']}")
lv = [int(E.run_ladder(st.res[m]["drift"], m, st.mrow.loc[m, "answer_key"], "silent")["level"].max())
      for m in st.ev[~st.ev.fraud & st.ev.asked].mid]
check("Honest shops that ignore the check-in are never suspended", max(lv) < 5, f"highest step {max(lv)}")
fest = np.array([bool(v) for v in st.cal["festival"]])
hit = sum(bool((st.res[m]["ladder"]["level"][fest] >= 3).any()) for m in st.ev[~st.ev.fraud].mid)
check("No honest shop has payouts touched on a festival day", hit == 0, f"{hit}")
m4 = [e["text"] for e in st.res["M004"]["ladder"]["events"]]
check("Golden Crust Bakery: suspended 18 Sep, 9 days after the first bet",
      any("Suspend" in t for t in m4) and st.iso(st.res["M004"]["ladder"]["events"][-1]["day"]) == "2026-09-18")

print("\n4. Link test")
hon = st.ev[~st.ev.fraud].mid
top = max(float(st.res[m]["drift"]["ring_link"].max()) for m in hon)
check("No honest shop comes near the link-test trigger", top < E.DRIFT_ON, f"highest {top:.2f}, trigger {E.DRIFT_ON}")
check("Hello Mobile Point (careful front) is linked to Golden Crust Bakery", st.links["M084"]["partners"].get("M004", 0) >= 20,
      f"{st.links['M084']['partners'].get('M004', 0)} shared payers")
nolink = st.ev_nolink
check("Without the link test, 14 of 18 fronts stopped (it adds 4)", int(nolink[nolink.fraud].caught.sum()) == 14)
first_hold = min(st.held_from().values())
check("Link test never looks ahead: no link evidence until the day after the first hold",
      all(float(v["count"][:first_hold + 1].sum()) == 0 for v in st.links.values()), f"first hold {st.iso(first_hold)}")

print("\n5. Every API endpoint")
check("Health, overview, profiles, results", A.health()["ok"] and len(A.overview()["merchants"]) == 168
      and len(A.profiles()["categories"]) == 3 and "rules" in A.results())
check("Case file for every shop", all("traits" in A.merchant(m) for m in st.res))
check("Merchant reply is judged", A.reply("M003", A.Reply(reason="late_night"))["outcome"] == "trusted"
      and A.reply("M004", A.Reply(reason="festival"))["outcome"] == "continue")
bad = careful_watch = 0
for cat, scs in SV.SCENARIOS.items():
    for sc in scs:
        for city in ["Hyderabad", "Mumbai"]:
            for seed in (7, 8):
                lv = A.simulate(A.Simulate(category=cat, city=city, scenario=sc[0], start="mid", seed=seed))["level"]
                if sc[1] == "disguised_front":          # careful fronts: stopped, or at least on Watch
                    bad += lv < 1; careful_watch += lv < 3
                else:
                    bad += (lv >= 3) != (sc[1] == "front")
check("Try it live: 72 new shops (honest left alone, bold fronts stopped, careful fronts at least watched)",
      bad == 0, f"{bad} wrong, {careful_watch} careful fronts on Watch only")
sample = st.sample_csv().encode()
iso = st.analyze(sample, "a.csv", "bakery", "Hyderabad")
d = pd.read_csv(pd.io.common.BytesIO(sample))
ts = pd.to_datetime(d.timestamp)
pack = d.drop(columns="timestamp").assign(date=ts.dt.strftime("%d-%m-%Y"), time=ts.dt.strftime("%H:%M")).to_csv(index=False).encode()
dmy = st.analyze(pack, "b.csv", "bakery", "Hyderabad")
check("CSV upload works with 2026-07-01 and 01-07-2026 dates (funds held: no settlement data, so no suspension)",
      iso["level"] == dmy["level"] == 4 and iso["score"] == dmy["score"], f"step {iso['level']}, score {iso['score']}")
try:
    st.analyze(b"%PDF-1.4 not a csv", "x.pdf", "bakery", "Hyderabad"); ok = False
except ValueError:
    ok = True
check("A wrong file gets a plain-language error", ok)
front = SV.ROOT / "frontend"
check("Screens present", all((front / n).exists() for n in ["index.html", "app.js", "styles.css"]))

n = len(RESULTS)
print(f"\n{sum(RESULTS)} of {n} checks passed in {time.time() - t0:.0f}s.")
if all(RESULTS):
    print("TrueShape works on this computer. Start it with:  python run.py")
sys.exit(0 if all(RESULTS) else 1)
