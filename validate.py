"""
TrueShape out-of-sample validation.

The published dataset (seed 26) is the one the thresholds were set on. This script builds NEW datasets the
engine has never seen (new shops, new payments, a new cricket schedule; festival dates stay real), runs the
unchanged engine on each, and reports pooled results with 95% confidence intervals.

Run:  python validate.py                       (20 new datasets: 3,360 shops, 360 betting fronts, with the
                                                ablation study; about 20 minutes)
      python validate.py --runs 3 --no-save     (quick look)
      python validate.py --ring-share 0.1 --no-ablation --key ring10   (sensitivity: rings share fewer punters)
Writes backend/validation.json, which the Results screen shows.
"""
import argparse
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "backend" / "validation.json"


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes out of n, in percent."""
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1)]


ABLATIONS = [("No link test", dict(link=False)), ("No peer test", dict(peer=False)),
             ("No check-in", dict(checkin=False)), ("No two-habit rule", dict(two_habits=False))]


def one(job):
    seed, ring, stray, ablate = job
    from backend import simulator as S
    from backend.service import Store
    S.RING_SHARE = ring
    S.STRAY_PUNTER = {k: v * stray for k, v in S.STRAY_BASE.items()}   # from the base rate: workers are reused
    st = Store(log=lambda *a: None, tables=S.generate_tables(seed))
    ev, R = st.ev, st.results()
    f, h = ev[ev.fraud], ev[~ev.fraud]
    bold, careful = f[f.kind == "front"], f[f.kind == "disguised_front"]
    rules = {r["name"]: r for r in R["rules"]}
    hon = list(h.mid)
    out = dict(
        seed=seed, shops=len(ev), fronts=len(f), honest=len(h),
        bold=len(bold), bold_caught=int(bold.caught.sum()),
        careful=len(careful), careful_caught=int(careful.caught.sum()),
        careful_watched=int((careful.max_level >= 1).sum()),
        disrupted=int(h.disrupted.sum()), asked=int((h.asked & ~h.disrupted).sum()),
        changed=int((h.kind != "honest").sum()), changed_disrupted=int(h[h.kind != "honest"].disrupted.sum()),
        days_bold=[int(x) for x in bold.days_to_act.dropna()], days_careful=[int(x) for x in careful.days_to_act.dropna()],
        sales_caught=rules["Sales-limit rule"]["caught"], sales_disrupted=rules["Sales-limit rule"]["disrupted"],
        smart_caught=rules["Smarter sales rule"]["caught"], smart_disrupted=rules["Smarter sales rule"]["disrupted"],
        best_excuse=R["stress"]["fronts_best_excuse"], honest_silent=R["stress"]["honest_silent"],
        honest_asked_total=R["stress"]["honest_asked"],
        honest_link_max=round(max(float(st.res[m]["drift"]["ring_link"].max()) for m in hon), 3),
        disrupted_ids=[f"{seed}:{m}:{k}" for m, k in zip(h[h.disrupted].mid, h[h.disrupted].kind)],
        ablation={},
    )
    if ablate:
        for name, kw in ABLATIONS:
            e = st.run_variant(**kw)
            fe, he = e[e.fraud], e[~e.fraud]
            out["ablation"][name] = dict(caught=int(fe.caught.sum()), disrupted=int(he.disrupted.sum()),
                                         asked=int(he.asked.sum()))
    return out


def pool(runs):
    T = lambda k: sum(r[k] for r in runs)
    db = [d for r in runs for d in r["days_bold"]]
    dc = [d for r in runs for d in r["days_careful"]]
    fr, ho = T("fronts"), T("honest")
    caught = T("bold_caught") + T("careful_caught")

    def rate(k, n):
        return dict(k=k, n=n, pct=round(100 * k / n, 1) if n else 0.0, ci=wilson(k, n))

    return dict(
        datasets=len(runs), seeds=[r["seed"] for r in runs], shops=T("shops"), fronts=fr, honest=ho,
        trueshape=dict(stopped=rate(caught, fr), bold=rate(T("bold_caught"), T("bold")),
                       careful=rate(T("careful_caught"), T("careful")),
                       careful_watched=rate(T("careful_watched"), T("careful")),
                       disrupted=rate(T("disrupted"), ho), changed_disrupted=rate(T("changed_disrupted"), T("changed")),
                       asked=T("asked"),
                       days_bold=dict(median=float(np.median(db)) if db else None, p90=float(np.percentile(db, 90)) if db else None),
                       days_careful=dict(median=float(np.median(dc)) if dc else None, p90=float(np.percentile(dc, 90)) if dc else None)),
        sales_rule=dict(stopped=rate(T("sales_caught"), fr), disrupted=rate(T("sales_disrupted"), ho)),
        smart_rule=dict(stopped=rate(T("smart_caught"), fr), disrupted=rate(T("smart_disrupted"), ho)),
        stress=dict(best_excuse=rate(T("best_excuse"), fr), honest_silent=T("honest_silent"), honest_asked=T("honest_asked_total")),
        honest_asked=T("asked") + T("disrupted"), honest_link_max=max(r["honest_link_max"] for r in runs),
        ablation=[dict(name=n, stopped=rate(sum(r["ablation"][n]["caught"] for r in runs), fr),
                       disrupted=rate(sum(r["ablation"][n]["disrupted"] for r in runs), ho),
                       asked=sum(r["ablation"][n]["asked"] for r in runs))
                  for n, _ in ABLATIONS if all(n in r["ablation"] for r in runs)],
        per_dataset=[dict(seed=r["seed"], stopped=r["bold_caught"] + r["careful_caught"], fronts=r["fronts"],
                          disrupted=r["disrupted"], honest=r["honest"]) for r in runs],
        disrupted_ids=[x for r in runs for x in r["disrupted_ids"]],
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--first-seed", type=int, default=101)
    ap.add_argument("--ring-share", type=float, default=None, help="share of a front's punters from its ring (default 0.5)")
    ap.add_argument("--stray", type=float, default=1.0, help="multiply punters who also buy at honest shops")
    ap.add_argument("--no-ablation", action="store_true")
    ap.add_argument("--key", default="main", help="name of this result in validation.json")
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--workers", type=int, default=None, help="parallel processes (default: CPUs - 1, at most 4)")
    a = ap.parse_args()
    from backend import simulator as S0
    ring = S0.RING_SHARE if a.ring_share is None else a.ring_share
    seeds = list(range(a.first_seed, a.first_seed + a.runs))
    t = time.time()
    workers = a.workers or max(1, min(len(seeds), (os.cpu_count() or 2) - 1, 4))
    print(f"Building and scoring {len(seeds)} new datasets ({len(seeds) * 168:,} shops), ring share {ring}, "
          f"stray punters x{a.stray}, {workers} worker(s)...")
    with ProcessPoolExecutor(workers) as ex:
        runs = list(ex.map(one, [(sd, ring, a.stray, not a.no_ablation) for sd in seeds]))
    for r in runs:
        print(f"  dataset {r['seed']}: fronts stopped {r['bold_caught'] + r['careful_caught']}/{r['fronts']}, "
              f"honest disrupted {r['disrupted']}/{r['honest']}, sales-limit rule disrupted {r['sales_disrupted']}")
    P = pool(runs)
    P.update(ring_share=ring, stray=a.stray)
    ts, sr = P["trueshape"], P["sales_rule"]
    print(f"\nPooled over {P['shops']:,} shops ({P['fronts']} fronts, {P['honest']:,} honest), {time.time() - t:.0f}s:")
    print(f"  TrueShape   fronts stopped {ts['stopped']['k']}/{P['fronts']} = {ts['stopped']['pct']}% (95% CI {ts['stopped']['ci']}),"
          f" honest disrupted {ts['disrupted']['k']}/{P['honest']} = {ts['disrupted']['pct']}% (95% CI {ts['disrupted']['ci']})")
    print(f"              bold {ts['bold']['pct']}%, careful {ts['careful']['pct']}% (at least watched {ts['careful_watched']['pct']}%),"
          f" days to act: bold median {ts['days_bold']['median']}, careful median {ts['days_careful']['median']}")
    print(f"  Sales rule  fronts stopped {sr['stopped']['pct']}%, honest disrupted {sr['disrupted']['k']}/{P['honest']} = {sr['disrupted']['pct']}%")
    print(f"  Stress test fronts stopped with their best excuse or silence: {P['stress']['best_excuse']['pct']}%")
    print(f"  Highest link signal on any honest shop: {P['honest_link_max']} (it counts from 0.5)")
    for ab in P["ablation"]:
        print(f"  {ab['name']:18s} fronts stopped {ab['stopped']['pct']}%, honest disrupted {ab['disrupted']['k']}, honest asked {ab['asked']}")
    if P["disrupted_ids"]:
        print("  Honest shops disrupted (dataset:shop:type):", ", ".join(P["disrupted_ids"]))
    if not a.no_save:
        allr = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        if "datasets" in allr:                      # older single-result format
            allr = {}
        allr[a.key] = P
        OUT.write_text(json.dumps(allr, indent=1), encoding="utf-8")
        print(f"Saved '{a.key}' in", OUT.name)
