"""TrueShape v2 service layer: loads data, runs the engine per peer group, shapes API responses."""
from __future__ import annotations
import io
import json
import numpy as np
import pandas as pd
from pathlib import Path

from . import engine as E
from . import simulator as S

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CAT_KEY = {v["label"]: k for k, v in S.CATEGORIES.items()}
NOUN = {"bakery": "bakeries", "kirana": "kirana stores", "mobile": "mobile shops"}
SHORT = {"bakery": "Bakery", "kirana": "Kirana", "mobile": "Mobile shop"}
STORY = ["M001", "M002", "M003", "M004", "M005"]

RADAR_AXES = [
    dict(key="big", label="Big payments", max=0.8, fmt="pct"),
    dict(key="round", label="Round amounts", max=0.8, fmt="pct"),
    dict(key="night", label="Late night", max=0.3, fmt="pct"),
    dict(key="outstate", label="Out of state", max=0.8, fmt="pct"),
    dict(key="cashout", label="Instant cash-out", max=1.0, fmt="pct"),
    dict(key="match_lift", label="Match-day spike", max=3.0, min=1.0, fmt="x"),
]
AXIS_LONG = {"big": "Payments at or above {big}", "round": "Round amounts (₹500, ₹1,000…)",
             "night": "Payments 11 PM to 5 AM", "outstate": "Payers outside {home}",
             "cashout": "Money pulled out within 1 hour", "match_lift": "Cricket match days vs other days"}

SCENARIOS = {
    "bakery": [
        ("festival", "honest", "Big festival rush", "Sales almost triple at Ganesh Chaturthi and Dussehra. Nothing else changes.", 2.1),
        ("new_branch", "grower", "Opens a second branch", "Sales double for good, with many new local customers.", None),
        ("late_night", "night_orders", "Starts midnight cakes", "₹500 to ₹1,500 cakes delivered between 10 PM and 1 AM.", None),
        ("stadium", "stadium", "Next to a cricket stadium", "Match-day crowds buy snacks. Sales follow the cricket schedule.", None),
        ("front", "front", "Betting front", "Collects ₹500 and ₹1,000 bets around match nights and cashes out at once.", None),
        ("careful_front", "disguised_front", "Careful betting front", "Odd amounts like ₹497, shop hours, small volume, slow start.", None),
    ],
    "kirana": [
        ("festival", "honest", "Big festival rush", "Ganesh Chaturthi and Diwali stock-up lift sales. Nothing else changes.", 2.1),
        ("khata", "khata", "Monthly credit settlements", "Regulars clear their khata in round amounts like ₹2,000 at the start of the month.", None),
        ("delivery", "delivery", "Starts home delivery", "More orders from new customers in the same neighbourhood.", None),
        ("late_night", "night_orders", "Stays open late", "Late-night orders for snacks and essentials.", None),
        ("front", "front", "Betting front", "Collects ₹500 and ₹1,000 bets around match nights and cashes out at once.", None),
        ("careful_front", "disguised_front", "Careful betting front", "Odd amounts like ₹497, shop hours, small volume, slow start.", None),
    ],
    "mobile": [
        ("festival", "honest", "Diwali phone sales", "Phone and accessory sales climb before Diwali. Nothing else changes.", 2.1),
        ("online", "online", "Starts selling online", "Accessory orders from buyers all over India.", None),
        ("new_branch", "grower", "Opens a second branch", "Sales double for good, with many new local customers.", None),
        ("bulk", "bulk", "Bulk corporate orders", "Occasional orders of several phones for an office.", None),
        ("front", "front", "Betting front", "Collects ₹500 and ₹1,000 bets around match nights and cashes out at once.", None),
        ("careful_front", "disguised_front", "Careful betting front", "Odd amounts like ₹497, shop hours, small volume, slow start.", None),
    ],
}
STARTS = {"early": ("25 Aug", "2026-08-25"), "mid": ("10 Sep", "2026-09-10"), "late": ("25 Sep", "2026-09-25")}


def _date(d):
    t = pd.Timestamp(d)
    return f"{t.day} {t.strftime('%b')}"


class Store:
    def __init__(self, log=print, tables=None, link=True):
        """tables=(merchants, transactions, cashouts, calendar) scores an in-memory replicate instead of data/."""
        if tables is None:
            if not (DATA / "transactions.csv").exists():
                log("First run: generating the simulated payments (about 30 seconds)...")
                S.generate_dataset(DATA)
            log("Loading payments...")
            self.cal = pd.read_csv(DATA / "calendar.csv", parse_dates=["date"])
            m = pd.read_csv(DATA / "merchants.csv", dtype=str).fillna("")
            tx = pd.read_csv(DATA / "transactions.csv", usecols=["merchant_id", "timestamp", "amount_inr", "payer_id",
                                                                "payer_state", "payment_mode"])
            tx["timestamp"] = pd.to_datetime(tx["timestamp"])
            cash = pd.read_csv(DATA / "cashouts.csv")
        else:
            md, tx, cash, cal = tables
            self.cal = cal.copy()
            self.cal["date"] = pd.to_datetime(self.cal["date"])
            m = md.astype(str).replace({"None": "", "nan": ""})
            tx = tx[["merchant_id", "timestamp", "amount_inr", "payer_id", "payer_state", "payment_mode"]]
        self.cal["festival"] = self.cal["festival"].fillna("")
        m["cat_key"] = m["category"].map(CAT_KEY)
        self.merchants = m
        self.mrow = m.set_index("merchant_id")
        self.dates = pd.DatetimeIndex(self.cal["date"])
        self.D = len(self.dates)
        self.today = self.D - 1
        self.tx = {mid: g.reset_index(drop=True) for mid, g in tx.groupby("merchant_id")}
        cash_by = {mid: g for mid, g in cash.groupby("merchant_id")}
        log(f"Scoring {len(m)} shops...")
        self.sig = {}
        for r in m.itertuples():
            ck = r.cat_key
            self.sig[r.merchant_id] = E.merchant_signals(self.tx[r.merchant_id], cash_by.get(r.merchant_id), self.cal,
                                                         ck, r.state, S.CATEGORIES[ck]["big"])
        self.groups = {}
        for (ck, city), g in m.groupby(["cat_key", "city"]):
            self.groups[(ck, city)] = E.peer_reference([self.sig[x] for x in g.merchant_id])
        self.res = {}
        self.links = {}
        self.score_all(m)
        self.ev_nolink = E.evaluate(self.res, m, self.dates[0]) if link else None
        if link:                                     # link test: nightly passes until the held set is stable
            homes = dict(zip(m.merchant_id, m.state))
            for _ in range(3):
                held = self.held_from()
                L = E.link_signal(self.tx, homes, held, self.D, self.dates[0])
                for mid, (share, count, partners) in L.items():
                    sg = self.sig[mid]
                    sg["x"]["ring_link"] = np.where(count >= E.LINK_MIN, share, 0.0)
                    sg.update(link_on=True, link_count=count, link_share=share)
                    self.links[mid] = dict(share=share, count=count, partners=partners)
                self.score_all(m)
                if self.held_from() == held:
                    break
        self.ev = E.evaluate(self.res, m, self.dates[0])
        self.summary = E.summarise(self.ev)
        log("Ready.")

    def score_all(self, m):
        for r in m.itertuples():
            s = self.sig[r.merchant_id]
            dr = E.drifts(s, self.groups[(r.cat_key, r.city)])
            s["drift"] = dr
            self.res[r.merchant_id] = dict(drift=dr, ladder=E.run_ladder(dr, r.merchant_id, r.answer_key),
                                           vrule=E.volume_rule(s))

    def run_variant(self, peer=True, link=True, **fixes):
        """Re-score every shop with one part switched off (ablation study). Leaves the live results untouched."""
        m, D = self.merchants, self.D
        sig = {k: dict(v, x=dict(v["x"], ring_link=np.zeros(D))) for k, v in self.sig.items()}

        def score():
            out = {}
            for r in m.itertuples():
                dr = E.drifts(sig[r.merchant_id], self.groups[(r.cat_key, r.city)] if peer else None)
                out[r.merchant_id] = dict(drift=dr, ladder=E.run_ladder(dr, r.merchant_id, r.answer_key, fixes=fixes),
                                          vrule=E.volume_rule(sig[r.merchant_id]))
            return out

        held_of = lambda res: {k: int(np.argmax(v["ladder"]["level"] >= 4)) for k, v in res.items()
                               if (v["ladder"]["level"] >= 4).any()}
        res = score()
        if link:
            homes = dict(zip(m.merchant_id, m.state))
            for _ in range(3):
                held = held_of(res)
                for k, (share, count, _) in E.link_signal(self.tx, homes, held, D, self.dates[0]).items():
                    sig[k]["x"]["ring_link"] = np.where(count >= E.LINK_MIN, share, 0.0)
                res = score()
                if held_of(res) == held:
                    break
        return E.evaluate(res, m, self.dates[0])

    def held_from(self):
        return {mid: int(np.argmax(r["ladder"]["level"] >= 4)) for mid, r in self.res.items()
                if (r["ladder"]["level"] >= 4).any()}

    # ------------------------------------------------------------ helpers
    def iso(self, d):
        return str(self.dates[d].date())

    def focus_day(self, lad, last):
        """A case file shows the evidence from the latest escalation, else today."""
        lv = lad["level"]
        if lv[last] == 0:
            return last, None
        ups = [d for d in range(1, last + 1) if lv[d] > lv[d - 1]]
        d = ups[-1] if ups else last
        return d, f"Evidence from {_date(self.dates[d])}, when the shop moved to '{E.LEVELS[int(lv[d])]['label']}'"

    def radar(self, sig, peer, d):
        def pack(src):
            out = []
            for a in RADAR_AXES:
                v = float(src(a["key"]))
                lo = a.get("min", 0.0)
                f = float(np.clip((v - lo) / (a["max"] - lo), 0, 1))
                out.append(dict(value=round(v, 3), norm=round(0.18 + 0.82 * f ** 0.5, 3)))
            return out
        L, N = sig["level"], sig["normal"]
        return dict(now=pack(lambda k: L[k][d]), normal=pack(lambda k: N[k]),
                    typical=pack(lambda k: peer["levels"][k][d]) if peer is not None else None)

    def glyph(self, mid, d):
        """Tiny shape for the merchant list: this shop now vs its own normal."""
        r = self.radar(self.sig[mid], None, d)
        return dict(now=[x["norm"] for x in r["now"]], normal=[x["norm"] for x in r["normal"]])

    # ------------------------------------------------------------ meta + overview
    def meta(self):
        return dict(
            today=self.iso(self.today), dates=[self.iso(d) for d in range(self.D)],
            festival=self.cal["festival"].tolist(), match=self.cal["is_match_day"].astype(bool).tolist(),
            big_match=self.cal["is_big_match"].astype(bool).tolist(), baseline_days=E.BASELINE_DAYS,
            levels=E.LEVELS, replies={k: v["label"] for k, v in E.REPLIES.items()},
            category_replies=E.CATEGORY_REPLIES, radar_axes=RADAR_AXES,
            categories=[dict(key=k, label=v["label"], short=SHORT[k], noun=NOUN[k], mcc=v["mcc"], big=v["big"],
                             amount_labels=E.AMOUNT_LABELS[k]) for k, v in S.CATEGORIES.items()],
            cities=[dict(key=c, state=v["state"]) for c, v in S.CITIES.items()],
            scenarios={k: [dict(key=s[0], label=s[2], blurb=s[3], fraud=s[1] in S.FRAUD) for s in v] for k, v in SCENARIOS.items()},
            starts=[dict(key=k, label=v[0]) for k, v in STARTS.items()],
            summary=self.summary, kinds=S.KINDS,
        )

    def overview(self):
        d = self.today
        rows = []
        for r in self.merchants.itertuples():
            lad = self.res[r.merchant_id]["ladder"]
            fd, _ = self.focus_day(lad, d)
            t = lad["traits"][fd]
            flags = [E.TRAIT_LABEL[E.TRAITS[i]] for i in np.argsort(-t) if t[i] >= E.DRIFT_ON and E.TRAITS[i] != "volume"][:2]
            e = self.ev.set_index("mid").loc[r.merchant_id]
            rows.append(dict(id=r.merchant_id, name=r.name, category=r.cat_key, city=r.city, area=r.area,
                             level=int(lad["level"][d]), score=int(round(lad["score"][fd])), flags=flags,
                             vol_ratio=round(float(self.sig[r.merchant_id]["vratio"][d]), 2),
                             glyph=self.glyph(r.merchant_id, fd), story=r.merchant_id in self.story_ids(),
                             kind=r.answer_key, kind_label=S.KINDS[r.answer_key], fraud=bool(e.fraud),
                             ours=bool(e.caught or e.disrupted), asked=bool(e.asked),
                             vol=bool(e.vol_caught or e.vol_disrupted)))
        return dict(today=self.iso(d), merchants=rows)

    def story_ids(self):
        if not hasattr(self, "_story"):
            ev = self.ev.set_index("mid")
            pick = list(STORY)

            def first(mask):
                c = ev[mask]
                return c.index[0] if len(c) else None
            k = first((ev.kind == "khata") & (ev.city == "Mumbai") & ~ev.disrupted) or first((ev.kind == "khata") & ~ev.disrupted)
            o = first((ev.kind == "online") & ev.asked & ~ev.disrupted) or first(ev.kind == "online")
            f = first((ev.kind == "front") & (ev.category == "mobile") & (ev.city == "Mumbai") & ev.caught)
            self._story = [x for x in pick + [k, o, f] if x]
        return self._story

    # ------------------------------------------------------------ category profiles
    def profiles(self):
        out = []
        for ck, C in S.CATEGORIES.items():
            ids = self.merchants[self.merchants.cat_key == ck].merchant_id.tolist()
            sigs = [self.sig[i] for i in ids]
            med = lambda k: float(np.median([s["normal"][k] for s in sigs]))
            norm = {k: med(k) for k in ["big", "round", "night", "outstate", "repeat", "cashout", "bill", "per_day"]}
            norm["match_lift"] = 1.0
            radar = []
            for a in RADAR_AXES:
                v = norm[a["key"]]
                lo = a.get("min", 0.0)
                f = float(np.clip((v - lo) / (a["max"] - lo), 0, 1))
                radar.append(dict(value=round(v, 3), norm=round(0.18 + 0.82 * f ** 0.5, 3)))
            H = np.sum([s["HB"] for s in sigs], axis=0)
            top = sorted(np.argsort(-H)[:2].tolist())
            hours = [round(float(x) / H.sum(), 4) for x in H]
            out.append(dict(key=ck, label=C["label"], noun=NOUN[ck], mcc=C["mcc"], radar=radar, hours=hours,
                            facts=dict(bill=round(norm["bill"]), per_day=round(norm["per_day"]),
                                       repeat=round(norm["repeat"], 3), outstate=round(norm["outstate"], 3),
                                       cashout=round(norm["cashout"], 3), big=round(norm["big"], 3), big_level=C["big"],
                                       busiest=top)))
        # festival check: typical weekly sales per category and city, honest shops touched on festival days
        fest_days = np.array([bool(f) for f in self.cal["festival"]])
        lines = {}
        for (ck, city), g in self.groups.items():
            lines[f"{ck}|{city}"] = [round(float(v), 2) for v in g["vratio"]]
        touched = 0
        for r in self.ev[~self.ev.fraud].itertuples():
            lv = self.res[r.mid]["ladder"]["level"]
            touched += bool((lv[fest_days] >= 3).any())
        honest_n = int((~self.ev.fraud).sum())
        return dict(categories=out, lines=lines, festival_touched=touched, honest=honest_n)

    # ------------------------------------------------------------ case file
    def build(self, sig, dr, lad, vr, last, info, peer, tx=None):
        ck = sig["category"]
        d, focus_note = self.focus_day(lad, last)
        reply = lad["reply"] if (lad["reply_from"] is not None and d >= lad["reply_from"] - 1) else None
        events = [dict(e, date=self.iso(e["day"])) for e in lad["events"] if e["day"] <= last]
        vflag = np.where(vr[:last + 1])[0]
        chk = None
        if lad["ask_day"] is not None and lad["ask_day"] <= last:
            c = E.check_reply(dr, min(lad["ask_day"] + 1, self.D - 1), lad["reply"]) if lad["reply"] else None
            chk = dict(asked_on=self.iso(lad["ask_day"]), reply=lad["reply"],
                       reply_label=E.REPLIES[lad["reply"]]["label"] if lad["reply"] else None, check=c)
        nz = lambda a: [round(float(x) / a.sum(), 4) if a.sum() else 0 for x in a]
        payments = []
        if tx is not None and len(tx):
            day = self.dates[d]
            t = tx[(tx["timestamp"] >= day) & (tx["timestamp"] < day + pd.Timedelta(days=1))].sort_values("timestamp")
            t = t.tail(20).iloc[::-1]
            payments = [dict(time=x.timestamp.strftime("%H:%M"), amount=int(x.amount_inr), state=x.payer_state,
                             mode=x.payment_mode if "payment_mode" in t.columns else "",
                             payer=str(x.payer_id)[-6:]) for x in t.itertuples()]
        L, N = sig["level"], sig["normal"]
        declared = None
        if info.get("declared_bill"):
            declared = dict(bill=info["declared_bill"], monthly=info["declared_monthly"],
                            bill_normal=round(N["bill"]), bill_now=round(float(L["bill"][d])),
                            monthly_now=round(float(sig["vol"][max(0, d - 29):d + 1].sum())),
                            monthly_normal=round(N["sales_month"]))
        noun = NOUN[ck]
        return dict(
            **{k: v for k, v in info.items() if not k.startswith("declared_")},
            category=ck, category_label=S.CATEGORIES[ck]["label"], noun=noun, mcc=S.CATEGORIES[ck]["mcc"],
            home=sig["home"], today=self.iso(last), level=int(lad["level"][last]), score=int(round(lad["score"][d])),
            score_today=int(round(lad["score"][last])),
            focus_day=self.iso(d), focus_note=focus_note, drifting=int(lad["nd"][d]),
            score_series=[int(round(v)) for v in lad["score"]], level_series=[int(v) for v in lad["level"]],
            vol_series=[round(float(v), 2) for v in sig["vratio"]],
            peer_vol_series=[round(float(v), 2) for v in peer["vratio"]] if peer is not None else None,
            peer_size=peer["size"] if peer is not None else 0,
            radar=self.radar(sig, peer, d), radar_long=[AXIS_LONG[a["key"]].format(big=f"₹{sig['big_level']:,}", home=sig["home"]) for a in RADAR_AXES],
            traits=E.describe(sig, peer, dr, d, lad["traits"][d], noun),
            tests=E.tests(sig, peer, dr, d, reply, noun),
            evidence=dict(hours_now=nz(sig["HW"][d]), hours_normal=nz(sig["HB"]), amounts_now=nz(sig["BW"][d]),
                          amounts_normal=nz(sig["BB"]), amount_labels=E.AMOUNT_LABELS[ck]),
            events=events, checkin=chk, payments=payments, declared=declared,
            replies=E.CATEGORY_REPLIES[ck],
            volume_rule=dict(days=int(len(vflag)), first=self.iso(int(vflag[0])) if len(vflag) else None, today=bool(vr[last])),
            sales_today=int(sig["vol"][last]), payments_today=int(sig["n"][last]),
        )

    def merchant(self, mid):
        r = self.mrow.loc[mid]
        res = self.res[mid]
        info = dict(id=mid, name=r["name"], area=r["area"], city=r["city"],
                    declared_bill=int(r["declared_avg_bill_inr"]), declared_monthly=int(r["declared_monthly_sales_inr"]),
                    answer=dict(kind=r["answer_key"], label=S.KINDS[r["answer_key"]], note=r["story_note"],
                                change_date=r["change_start_date"]))
        out = self.build(self.sig[mid], res["drift"], res["ladder"], res["vrule"], self.today, info,
                         self.groups[(r["cat_key"], r["city"])], self.tx[mid])
        held = self.held_from()
        part = sorted(self.links.get(mid, {}).get("partners", {}).items(), key=lambda kv: -kv[1])
        out["links"] = dict(on=bool(self.links), partners=[
            dict(id=x, name=self.mrow.loc[x, "name"], city=self.mrow.loc[x, "city"], shared=n,
                 level=int(self.res[x]["ladder"]["level"][self.today]), held_on=self.iso(held[x])) for x, n in part[:6]],
            more=max(0, len(part) - 6))
        return out

    def reply(self, mid, reason):
        r = self.res[mid]
        lad = r["ladder"]
        day = min(lad["ask_day"] + 1 if lad["ask_day"] is not None else self.today, self.D - 1)
        out = E.check_reply(r["drift"], day, reason)
        out["checked_on"] = self.iso(day)
        out["level_label"] = E.LEVELS[out["level"]]["label"]
        return out

    # ------------------------------------------------------------ results
    def results(self):
        ev = self.ev
        groups = []
        for city in S.CITIES:
            for ck in S.CATEGORIES:
                g = ev[(ev.city == city) & (ev.category == ck)]
                f, h = g[g.fraud], g[~g.fraud]
                groups.append(dict(city=city, category=ck, label=S.CATEGORIES[ck]["label"], shops=int(len(g)),
                                   fronts=int(len(f)), caught=int(f.caught.sum()), honest=int(len(h)),
                                   disrupted=int(h.disrupted.sum()), asked=int((h.asked & ~h.disrupted).sum()),
                                   vol_disrupted=int(h.vol_disrupted.sum())))
        hard = []
        for kind in ["night_orders", "khata", "online", "stadium", "sweeper", "grower", "delivery", "bulk"]:
            g = ev[ev.kind == kind]
            if not len(g):
                continue
            hard.append(dict(kind=kind, label=S.KINDS[kind], shops=int(len(g)), left_alone=int((~g.asked).sum()),
                             asked_cleared=int((g.asked & ~g.disrupted).sum()), disrupted=int(g.disrupted.sum()),
                             vol_hit=int(g.vol_disrupted.sum()), example=g.iloc[0].mid))
        fronts = [dict(id=r.mid, name=r.name, category=r.category, city=r.city, kind=r.kind,
                       caught=bool(r.caught), days=None if pd.isna(r.days_to_act) else int(r.days_to_act),
                       max_level=int(r.max_level), vol_days=int(r.vol_days))
                  for r in ev[ev.fraud].sort_values(["kind", "days_to_act"]).itertuples()]
        rules = [dict(name="TrueShape", note="Shape vs own normal, peers, context and shared payers", caught=self.summary["trueshape"]["caught"],
                      disrupted=self.summary["trueshape"]["disrupted"])]
        for name, note, fn in [
            ("Sales-limit rule", "Flag when weekly sales reach 2x the shop's normal",
             lambda m, g: self.sig[m]["vratio"] >= 2),
            ("Smarter sales rule", "Flag when weekly sales reach 2x what the typical shop in its group did",
             lambda m, g: self.sig[m]["vratio"] / np.maximum(self.groups[g]["vratio"], 1e-6) >= 2)]:
            hit = {r.mid: bool(fn(r.mid, (r.category, r.city)).any()) for r in ev.itertuples()}
            rules.append(dict(name=name, note=note, caught=int(sum(hit[m] for m in ev[ev.fraud].mid)),
                              disrupted=int(sum(hit[m] for m in ev[~ev.fraud].mid))))
        missed = ev[ev.fraud & ~ev.caught]
        if not hasattr(self, "_stress"):
            self._stress = E.stress_tests({m: r["drift"] for m, r in self.res.items()}, ev)
        return dict(summary=self.summary, groups=groups, hard=hard, fronts=fronts, rules=rules, stress=self._stress,
                    validation=self.validation(),
                    missed=[dict(id=r.mid, name=r.name, category=r.category, city=r.city, max_level=int(r.max_level),
                                 start=self.mrow.loc[r.mid, "change_start_date"]) for r in missed.itertuples()])

    @staticmethod
    def validation():
        """Out-of-sample results written by validate.py (None if it has not been run)."""
        f = Path(__file__).resolve().parent / "validation.json"
        try:
            v = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        for r in v.values():
            r.pop("disrupted_ids", None)
            r.pop("per_dataset", None)
        return v

    # ------------------------------------------------------------ simulator + upload
    def simulate(self, category, city, scenario, start="mid", seed=None):
        sc = next(s for s in SCENARIOS[category] if s[0] == scenario)
        kind = sc[1]
        if kind == "honest":
            cd = None
        elif kind == "stadium":
            cd = (pd.Timestamp("2026-08-20") - self.dates[0]).days
        else:
            cd = (pd.Timestamp(STARTS[start][1]) - self.dates[0]).days
        seed = int(np.random.default_rng().integers(1, 10 ** 6)) if seed is None else int(seed)
        C = S.CATEGORIES[category]
        rate = float(np.mean(C["rate"]))
        tx, co = S.simulate_merchant("SIM", category, city, kind, rate, cd, seed=seed, fest_sens=sc[4])
        tx = tx.rename(columns={"answer_key_source": "_src"})
        sig = E.merchant_signals(tx, co, self.cal, category, S.CITIES[city]["state"], C["big"])
        peer = self.groups[(category, city)]
        dr = E.drifts(sig, peer)
        sig["drift"] = dr
        lad = E.run_ladder(dr, "SIM", kind)
        avg = round(C["typical_bill"], -1)
        info = dict(id="SIM", name=f"Test {SHORT[category].lower()}", area="Simulated", city=city,
                    declared_bill=int(avg), declared_monthly=int(round(rate * 30 * avg, -4)),
                    answer=dict(kind=kind, label=sc[2], note=sc[3], change_date=self.iso(cd) if cd is not None else ""))
        out = self.build(sig, dr, lad, E.volume_rule(sig), self.today, info, peer, tx)
        out.update(scenario=scenario, seed=seed, payments_total=int(len(tx)), fraud=kind in S.FRAUD)
        return out

    def sample_csv(self, mid="M004"):
        t = self.tx[mid][["timestamp", "amount_inr", "payer_id", "payer_state"]].copy()
        t["timestamp"] = t["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
        return t.to_csv(index=False)

    @staticmethod
    def _parse_times(s):
        """Read timestamps in ISO (2026-07-01 07:13) or Indian day-first form (01-07-2026 07:13, 01/07/2026)."""
        s = s.astype(str).str.strip()
        iso = s.str.match(r"^\d{4}-\d{1,2}-\d{1,2}")
        if iso.mean() >= 0.5:
            return pd.to_datetime(s, errors="coerce", format="ISO8601")
        return pd.to_datetime(s, errors="coerce", dayfirst=True, format="mixed")

    def analyze(self, raw: bytes, filename, category, city):
        if raw[:4] in (b"PK\x03\x04", b"%PDF") or b"\x00" in raw[:2048]:
            raise ValueError("That is not a CSV file. In Excel, use File > Save As > CSV, then upload the .csv file.")
        try:
            df = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(raw), encoding="latin-1")
        except pd.errors.ParserError:
            raise ValueError("Could not read that file as a CSV. Upload a comma-separated file with a header row.")
        df.columns = [str(c).strip().lower() for c in df.columns]
        if "amount" in df.columns and "amount_inr" not in df.columns:
            df = df.rename(columns={"amount": "amount_inr"})
        if "timestamp" not in df.columns and {"date", "time"} <= set(df.columns):
            df["timestamp"] = df["date"].astype(str) + " " + df["time"].astype(str)
        need = {"timestamp", "amount_inr", "payer_id"}
        if not need <= set(df.columns):
            raise ValueError("The file needs these columns: timestamp (or date and time), amount_inr (or amount), payer_id. payer_state is optional.")
        df["timestamp"] = self._parse_times(df["timestamp"])
        df["amount_inr"] = pd.to_numeric(df["amount_inr"], errors="coerce")
        df = df.dropna(subset=["timestamp", "amount_inr"])
        if df.empty:
            raise ValueError("No usable rows. Check the timestamp and amount columns.")
        if "merchant_id" in df.columns and df["merchant_id"].nunique() > 1:
            raise ValueError("The file holds more than one shop. Upload one shop's payments at a time.")
        first, last = df["timestamp"].min().normalize(), df["timestamp"].max().normalize()
        days = (last - first).days + 1
        if days < 28:
            raise ValueError(f"The file covers {days} days. TrueShape needs at least 4 weeks of payments.")
        C = S.CATEGORIES[category]
        home = S.CITIES[city]["state"]
        in_range = abs((first - self.dates[0]).days) <= 3 and last <= self.dates[-1]
        if in_range:
            cal, peer, base = self.cal, self.groups[(category, city)], E.BASELINE_DAYS
        else:
            dates = pd.date_range(first, last, freq="D")
            cal = pd.DataFrame({"date": dates, "is_match_day": False, "is_big_match": False, "festival": ""})
            peer, base = None, min(E.BASELINE_DAYS, max(14, int(days * 0.4)))
        sig = E.merchant_signals(df, None, cal, category, home, C["big"], base)
        dr = E.drifts(sig, peer)
        sig["drift"] = dr
        lad = E.run_ladder(dr, "UPLOAD", None)
        info = dict(id="UPLOAD", name=Path(filename).stem[:40] or "Uploaded shop", area="Uploaded file", city=city, answer=None)
        out = self.build(sig, dr, lad, E.volume_rule(sig), len(cal) - 1, info, peer, df)
        out.update(rows=int(len(df)), peer_used=peer is not None)
        if peer is None:
            out["dates"] = [str(x.date()) for x in pd.DatetimeIndex(cal["date"])]
        return out
