"""
TrueShape engine v2 (Team Dhurandhar).   "Volume can change. Shape shouldn't."

A transparent, rule-based comparison engine (no machine learning, no training,
no labels). For every merchant, every day:

  1 FINGERPRINT   last 7 days of payments -> six habits
  2 SELF TEST     compare with the shop's own first 45 days
  3 PEER TEST     subtract what the typical shop of the SAME CATEGORY in the
                  SAME CITY did over the same 7 days (festivals cancel out)
  4 CONTEXT TEST  cricket match days, and the merchant's own explanation
  5 DECIDE        unexplained habits -> 0-100 mismatch score -> response ladder

Columns used: timestamp, amount_inr, payer_id, payer_state (transactions);
share_pulled_out_within_1h (cash-outs); is_match_day (calendar).
The answer key is used only by evaluate().
"""
from __future__ import annotations
import numpy as np
import pandas as pd

BASELINE_DAYS = 45
WIN = 7
CAL_WIN = 21
DRIFT_ON = 0.5
AMOUNT_EDGES = {
    "bakery": [0, 100, 200, 300, 500, 800, 1200, 2000, 5000, 10 ** 9],
    "kirana": [0, 100, 200, 300, 500, 800, 1200, 2000, 5000, 10 ** 9],
    "mobile": [0, 200, 400, 700, 1000, 2000, 5000, 10000, 20000, 10 ** 9],
}
AMOUNT_LABELS = {
    "bakery": ["<₹100", "₹100", "₹200", "₹300", "₹500", "₹800", "₹1.2k", "₹2k", "₹5k+"],
    "kirana": ["<₹100", "₹100", "₹200", "₹300", "₹500", "₹800", "₹1.2k", "₹2k", "₹5k+"],
    "mobile": ["<₹200", "₹200", "₹400", "₹700", "₹1k", "₹2k", "₹5k", "₹10k", "₹20k+"],
}

TRAITS = ["sizes", "hours", "payers", "cashout", "events", "volume"]
TRAIT_LABEL = {"sizes": "Payment sizes", "hours": "Shop hours", "payers": "Who pays",
               "cashout": "Where the money goes", "events": "What drives sales", "volume": "Sales volume"}
TRAIT_WEIGHT = {"sizes": .45, "hours": .35, "payers": .45, "cashout": .50, "events": .40, "volume": .25}
SIGNALS = {   # signal -> (habit, drift starts, full drift)
    "mix_shift": ("sizes", .03, .20), "big_shift": ("sizes", .05, .25), "round_shift": ("sizes", .04, .20),
    "night_shift": ("hours", .03, .15),
    "repeat_drop": ("payers", .08, .30), "outstate_shift": ("payers", .05, .30),
    "cashout_shift": ("cashout", .08, .40),
    "match_lift": ("events", .25, 1.00),
    "volume": ("volume", .50, 1.50),
}

LEVELS = [
    dict(key="clear", label="All clear", short="Clear", meaning="No action. The shop is not contacted."),
    dict(key="watch", label="Watch", short="Watch", meaning="Monitored quietly. The merchant sees nothing."),
    dict(key="ask", label="Ask: what changed?", short="Asked", meaning="A two-tap check-in in the merchant app. Money flows as normal."),
    dict(key="delay", label="Delay payouts", short="Delayed", meaning="Settlement moves from next day to 3 days. The shop keeps selling."),
    dict(key="hold", label="Hold funds", short="Held", meaning="New payouts held while a risk analyst reviews the case."),
    dict(key="suspend", label="Suspend & report", short="Suspended", meaning="Account suspended. Suspicious transaction report filed with FIU-IND."),
]

# Every possible answer to "What changed?" and which signals it can honestly explain
REPLIES = {
    "festival": dict(label="Festival or seasonal rush", explains={"volume", "big_shift", "mix_shift"}),
    "phone_sale": dict(label="Festival or phone-sale season", explains={"volume", "big_shift", "mix_shift"}),
    "new_branch": dict(label="Opened a new branch", explains={"volume", "repeat_drop"}),
    "delivery": dict(label="Started home delivery", explains={"volume", "repeat_drop"}),
    "late_night": dict(label="Started late-night orders", explains={"hours", "sizes"}),
    "bulk": dict(label="Taking bulk or corporate orders", explains={"sizes", "volume"}),
    "venue": dict(label="Shop is near a stadium or event venue", explains={"events", "volume", "payers"}),
    "khata": dict(label="Regulars are paying their monthly credit (khata)", explains={"sizes"}),
    "online": dict(label="Started selling online across India", explains={"payers", "volume"}),
    "savings": dict(label="I move daily takings to my savings account", explains={"cashout"}),
    "other": dict(label="Something else (I'll explain)", explains=set()),
}
CATEGORY_REPLIES = {
    "bakery": ["festival", "new_branch", "late_night", "bulk", "venue", "delivery", "savings", "other"],
    "kirana": ["festival", "new_branch", "delivery", "late_night", "khata", "savings", "other"],
    "mobile": ["phone_sale", "new_branch", "online", "bulk", "delivery", "savings", "other"],
}
SCRIPTED_REPLY = {"grower": "new_branch", "night_orders": "late_night", "bulk": "bulk", "stadium": "venue",
                  "sweeper": "savings", "delivery": "delivery", "khata": "khata", "online": "online",
                  "front": "festival", "disguised_front": "delivery"}
SILENT = {"M005"}            # story: the careful front never answers


def front_replies(mid):
    """Some fronts answer with a false excuse, others stay silent (fixed, so runs repeat)."""
    if mid == "M004":
        return True
    if mid in SILENT or not mid[1:].isdigit():
        return mid not in SILENT
    return int(mid[1:]) % 5 in (0, 1, 3)


def explained(reply, sig):
    if reply is None:
        return False
    ex = REPLIES[reply]["explains"]
    return sig in ex or SIGNALS[sig][0] in ex


# ------------------------------------------------------------------ step 1: fingerprint
def _js(p, q):
    p = p / p.sum() if p.sum() else p
    q = q / q.sum() if q.sum() else q
    m = .5 * (p + q)
    kl = lambda a, b: np.sum(a[a > 0] * np.log2(a[a > 0] / b[a > 0]))
    return .5 * kl(p, m) + .5 * kl(q, m)


def _roll(x, w=WIN):
    pad = [(w, 0)] + [(0, 0)] * (x.ndim - 1)
    c = np.cumsum(np.pad(x, pad), axis=0)
    return c[w:] - c[:-w]


def merchant_signals(tx, cash, cal, category, home_state, big_level, baseline_days=BASELINE_DAYS):
    """Daily habit levels and changes for ONE merchant, before the peer test."""
    dates = pd.DatetimeIndex(cal["date"])
    D = len(dates)
    ts = pd.to_datetime(tx["timestamp"])
    di = (ts.dt.normalize() - dates[0]).dt.days.values
    keep = (di >= 0) & (di < D)
    ts, di = ts[keep], di[keep]
    amt = tx["amount_inr"].values[keep].astype(float)
    payer = tx["payer_id"].values[keep]
    hour = ts.dt.hour.values
    has_state = "payer_state" in tx.columns
    outst = (tx["payer_state"].fillna(home_state).values[keep] != home_state).astype(float) if has_state else np.zeros(len(amt))
    order = np.lexsort((ts.values, payer))
    t_s, p_s = ts.values[order], payer[order]
    same = np.r_[False, p_s[1:] == p_s[:-1]]
    gap = np.r_[np.inf, (t_s[1:] - t_s[:-1]) / np.timedelta64(1, "D")]
    ret = np.zeros(len(amt)); ret[order] = (same & (gap <= 30)).astype(float)

    cnt = lambda w=None: np.bincount(di, weights=w, minlength=D).astype(float)
    n, vol = cnt(), cnt(amt)
    big = cnt((amt >= big_level).astype(float))
    rnd = cnt(((amt >= 100) & (amt % 100 == 0)).astype(float))
    night = cnt(((hour >= 23) | (hour < 5)).astype(float))
    out, rep = cnt(outst), cnt(ret)
    H = np.zeros((D, 24)); np.add.at(H, (di, hour), 1)
    edges = AMOUNT_EDGES[category]
    nb = len(edges) - 1
    bucket = np.clip(np.searchsorted(edges, amt, side="right") - 1, 0, nb - 1)
    B = np.zeros((D, nb)); np.add.at(B, (di, bucket), 1)

    has_cash = cash is not None and len(cash) > 0
    co = np.zeros(D)
    if has_cash:
        c = cash.copy(); c["date"] = pd.to_datetime(c["date"])
        co = c.set_index("date")["share_pulled_out_within_1h"].reindex(dates).fillna(0).values

    b = slice(0, baseline_days)
    nW, volW = _roll(n), _roll(vol)
    nB = max(1.0, n[b].sum())
    sh = lambda a: _roll(a) / np.maximum(nW, 1)
    shb = lambda a: float(a[b].sum() / nB)
    level = {"big": sh(big), "round": sh(rnd), "night": sh(night), "outstate": sh(out), "repeat": sh(rep),
             "cashout": _roll(co) / WIN, "bill": volW / np.maximum(nW, 1)}
    normal = {"big": shb(big), "round": shb(rnd), "night": shb(night), "outstate": shb(out), "repeat": shb(rep),
              "cashout": float(co[b].mean()), "bill": float(vol[b].sum() / nB),
              "per_day": float(n[b].mean()), "sales_month": float(vol[b].sum() / baseline_days * 30)}
    vratio = volW / max(1.0, vol[b].sum() / baseline_days * WIN)

    match = cal["is_match_day"].values.astype(bool)
    lift = np.zeros(D)
    for d in range(D):
        lo = max(0, d - CAL_WIN + 1)
        mm = match[lo:d + 1]
        if mm.sum() >= 3 and (~mm).sum() >= 3:
            a = n[lo:d + 1]
            lift[d] = np.log2((a[mm].mean() + 1) / (a[~mm].mean() + 1))
    level["match_lift"] = 2 ** lift
    normal["match_lift"] = 1.0

    HW, BW = _roll(H), _roll(B)
    HB, BB = H[b].sum(0), B[b].sum(0)
    mix = np.array([_js(BW[d], BB) if nW[d] else 0.0 for d in range(D)])
    x = {
        "mix_shift": mix, "big_shift": level["big"] - normal["big"], "round_shift": level["round"] - normal["round"],
        "night_shift": level["night"] - normal["night"], "repeat_drop": normal["repeat"] - level["repeat"],
        "outstate_shift": level["outstate"] - normal["outstate"],
        "cashout_shift": level["cashout"] - normal["cashout"] if has_cash else np.zeros(D),
        "match_lift": lift, "volume": np.log2(np.maximum(vratio, 1e-6)),
    }
    return dict(D=D, n=n, vol=vol, level=level, normal=normal, vratio=vratio, x=x, HW=HW, HB=HB, BW=BW, BB=BB,
                has_cash=has_cash, has_state=has_state, category=category, home=home_state, big_level=big_level)


# ------------------------------------------------------------------ steps 2-4: tests
LEVEL_KEYS = ["big", "round", "night", "outstate", "repeat", "cashout", "match_lift", "bill"]


def peer_reference(sigs):
    """The typical shop of a group, each day: the median across the group's shops."""
    ref = {k: np.median(np.stack([s["x"][k] for s in sigs]), axis=0) for k in SIGNALS}
    ref["levels"] = {k: np.median(np.stack([s["level"][k] for s in sigs]), axis=0) for k in LEVEL_KEYS}
    ref["vratio"] = np.median(np.stack([s["vratio"] for s in sigs]), axis=0)
    ref["size"] = len(sigs)
    return ref


def drifts(sig, peer):
    out = {}
    for k, (_, lo, hi) in SIGNALS.items():
        adj = sig["x"][k] - (peer[k] if peer is not None else 0)
        d = np.clip((adj - lo) / (hi - lo), 0, 1)
        d[:WIN - 1] = 0
        out[k] = d
    return out


def trait_scores(dr, day, reply=None, reply_from=None):
    t = {k: 0.0 for k in TRAITS}
    for k, (trait, _, _) in SIGNALS.items():
        v = dr[k][day]
        if reply is not None and (reply_from is None or day >= reply_from) and explained(reply, k):
            v *= .15
        t[trait] = max(t[trait], float(v))
    return t


def mismatch(t):
    """Unexplained habits -> 0-100. Fewer than two shape habits drifting caps it at 39 (Watch)."""
    nd = sum(t[k] >= DRIFT_ON for k in TRAITS if k != "volume")
    r = 1.0
    for k in TRAITS:
        r *= 1 - TRAIT_WEIGHT[k] * t[k]
    s = 100 * (1 - r)
    return (min(s, 39) if nd <= 1 else s), nd


def level_for(s, nd):
    lv = 0
    if s >= 25: lv = 1
    if s >= 40 and nd >= 2: lv = 2
    if s >= 55 and nd >= 2: lv = 3
    if s >= 70 and nd >= 3: lv = 4
    return lv


def check_reply(dr, day, reply):
    before = trait_scores(dr, day)
    after = trait_scores(dr, day, reply, None)
    s_after, nd_after = mismatch(after)
    exp = [TRAIT_LABEL[k] for k in TRAITS if before[k] >= DRIFT_ON and after[k] < DRIFT_ON]
    left = [TRAIT_LABEL[k] for k in TRAITS if after[k] >= DRIFT_ON and k != "volume"]
    if not left and not exp:
        verdict, outcome = "Nothing unusual to explain. No action needed.", "clear"
    elif not left:
        verdict, outcome = "The answer explains every change. The shop moves to the trusted lane and this becomes its new normal.", "trusted"
    else:
        verdict, outcome = "The answer does not explain: " + ", ".join(x.lower() for x in left) + ". The case continues.", "continue"
    return dict(reply=reply, reply_label=REPLIES[reply]["label"], explained=exp, unexplained=left,
                score=round(s_after), level=level_for(s_after, nd_after), outcome=outcome, verdict=verdict)


# ------------------------------------------------------------------ step 5: decide
def run_ladder(dr, mid, kind=None):
    D = len(next(iter(dr.values())))
    reply = reply_from = None
    if kind in ("front", "disguised_front"):
        replies = front_replies(mid)
    else:
        replies = kind in SCRIPTED_REPLY
    score, level, nds = np.zeros(D), np.zeros(D, int), np.zeros(D, int)
    traits = np.zeros((D, len(TRAITS)))
    events, ask_day, hold_streak, prev, disputed = [], None, 0, 0, False
    for d in range(D):
        t = trait_scores(dr, d, reply, reply_from)
        traits[d] = [t[k] for k in TRAITS]
        s, nd = mismatch(t)
        score[d], nds[d] = s, nd
        lv = level_for(score[max(0, d - 2):d + 1].mean(), nd)
        if ask_day is not None and reply is None and d - ask_day >= 3:
            lv = min(lv + 1, 4) if lv >= 2 else 3             # no answer: payouts stay delayed
        if disputed:
            lv = max(lv, 3)                                    # answer did not fit: analyst review
        hold_streak = hold_streak + 1 if lv >= 4 else 0
        if hold_streak >= 5 and (t["cashout"] >= DRIFT_ON or t["events"] >= DRIFT_ON):
            lv = 5
        if prev == 5:
            lv = 5                                             # only a human lifts a suspension
        if prev >= 3 and lv < prev - 1:
            lv = prev - 1                                      # step down one level at a time
        level[d] = lv
        if lv >= 2 and ask_day is None:
            ask_day = d
            events.append(dict(day=d, type="ask", text="Sent the 'What changed?' check-in"))
        if lv != prev:
            events.append(dict(day=d, type="level", level=int(lv), text=f"{LEVELS[prev]['label']} → {LEVELS[lv]['label']}"))
        if ask_day is not None and reply is None and replies and d == ask_day + 1:
            reply, reply_from = SCRIPTED_REPLY[kind], d + 1
            chk = check_reply(dr, d, reply)
            disputed = chk["outcome"] == "continue"
            events.append(dict(day=d, type="reply", text=f"Merchant replied: \"{REPLIES[reply]['label']}\""))
            events.append(dict(day=d, type="check", text=chk["verdict"]))
        if ask_day is not None and reply is None and d == ask_day + 3:
            events.append(dict(day=d, type="noreply", text="No answer to the check-in after 3 days"))
        prev = lv
    return dict(score=score, level=level, traits=traits, nd=nds, events=events, ask_day=ask_day,
                reply=reply, reply_from=reply_from)


def volume_rule(sig):
    """A typical sales-limit rule: flag when weekly sales reach 2x normal."""
    return sig["vratio"] >= 2.0


# ------------------------------------------------------------------ plain language
def _pct(v):
    return f"{100 * v:.0f}%"


def describe(sig, peer, dr, day, traits_today, noun):
    """One row per habit: normal, now, peers, verdict and a sentence."""
    L, N = sig["level"], sig["normal"]
    P = peer["levels"] if peer is not None else None
    pv = lambda k: float(P[k][day]) if P is not None else None
    big = f"₹{sig['big_level']:,}"
    rows = []

    def row(key, normal, now, peers, unit, sentence):
        v = traits_today[TRAITS.index(key)]
        raw = max(dr[k][day] for k, (tr, _, _) in SIGNALS.items() if tr == key)
        status = "unusual" if v >= DRIFT_ON else ("explained" if raw >= DRIFT_ON else "normal")
        if key == "volume":
            status = "grew" if raw >= DRIFT_ON else "normal"
        rows.append(dict(key=key, label=TRAIT_LABEL[key], normal=normal, now=now, peers=peers, unit=unit,
                         score=round(v, 2), status=status, sentence=sentence))

    row("sizes", _pct(N["big"]), _pct(L["big"][day]), _pct(pv("big")) if P else "–", f"of payments are {big} or more",
        f"Round amounts like ₹500 or ₹1,000 are {_pct(L['round'][day])} of payments, against {_pct(N['round'])} in this shop's normal weeks.")
    row("hours", _pct(N["night"]), _pct(L["night"][day]), _pct(pv("night")) if P else "–", "of payments between 11 PM and 5 AM",
        f"{_pct(L['night'][day])} of payments arrive between 11 PM and 5 AM. Normally {_pct(N['night'])}.")
    row("payers", _pct(N["outstate"]) if sig["has_state"] else "–", _pct(L["outstate"][day]) if sig["has_state"] else "–",
        _pct(pv("outstate")) if P else "–", f"of payers are outside {sig['home']}",
        f"Returning customers: {_pct(N['repeat'])} normally, {_pct(L['repeat'][day])} now.")
    row("cashout", _pct(N["cashout"]) if sig["has_cash"] else "–", _pct(L["cashout"][day]) if sig["has_cash"] else "–",
        _pct(pv("cashout")) if P else "–", "of money pulled out within an hour",
        f"{noun.capitalize()} take the normal next-day settlement. Pulling money out the moment it arrives is how collection accounts work."
        if sig["has_cash"] else "No cash-out data in this file.")
    row("events", "1.0×", f"{L['match_lift'][day]:.1f}×", f"{pv('match_lift'):.1f}×" if P else "–",
        "payments on cricket match days vs other days",
        f"{noun.capitalize()} get busier at festivals and weekends. Cricket matches should not matter to them.")
    row("volume", "1.0×", f"{sig['vratio'][day]:.1f}×", f"{float(peer['vratio'][day]):.1f}×" if P else "–",
        "of normal weekly sales", "Shown for context. A shop selling more is not suspicious by itself.")
    return rows


def tests(sig, peer, dr, day, reply, noun):
    raw = {}
    for k, (tr, lo, hi) in SIGNALS.items():
        own = np.clip((sig["x"][k][day] - lo) / (hi - lo), 0, 1)
        raw.setdefault(tr, []).append((own, dr[k][day]))
    self_changed = [TRAIT_LABEL[t] for t, v in raw.items() if t != "volume" and max(a for a, _ in v) >= DRIFT_ON]
    peer_changed = [TRAIT_LABEL[t] for t, v in raw.items() if t != "volume" and max(b for _, b in v) >= DRIFT_ON]
    q = {"self": "Has this shop changed compared with its own normal weeks?",
         "peer": f"Are other {noun} in the same city changing the same way this week?",
         "ctx": "Do the changes fit real events and what the merchant told us?"}
    out = [dict(name="Self test", question=q["self"], passed=not self_changed,
                text="Its pattern matches its own normal weeks." if not self_changed
                else "Changed from its own normal: " + ", ".join(x.lower() for x in self_changed) + ".")]
    if peer is None:
        out.append(dict(name="Peer test", question=q["peer"], passed=None, text="No peer group for these dates."))
    else:
        cancelled = [x for x in self_changed if x not in peer_changed]
        if not peer_changed:
            txt = (f"Other {noun} changed the same way this week ({', '.join(x.lower() for x in cancelled)}), so this is the season, not the shop."
                   if cancelled else f"In line with other {noun} this week.")
        else:
            txt = f"Other {noun} did not change like this: " + ", ".join(x.lower() for x in peer_changed) + "."
        out.append(dict(name="Peer test", question=q["peer"], passed=not peer_changed, text=txt))
    ev = dr["match_lift"][day] >= DRIFT_ON
    if reply:
        chk = check_reply(dr, day, reply)
        txt = f"Merchant said: \"{REPLIES[reply]['label']}\". " + chk["verdict"]
        if ev and not explained(reply, "match_lift"):
            txt += " Sales also jump on cricket match days."
        out.append(dict(name="Context test", question=q["ctx"], passed=chk["outcome"] != "continue", text=txt))
    else:
        out.append(dict(name="Context test", question=q["ctx"], passed=not ev,
                        text=f"Sales jump on cricket match days, which {noun} have no reason for." if ev
                        else "Sales follow festivals and weekends, as they should."))
    return out


# ------------------------------------------------------------------ evaluation
def evaluate(results, merchants, start):
    rows = []
    for m in merchants.itertuples():
        r = results[m.merchant_id]
        lv, vr = r["ladder"]["level"], r["vrule"]
        fraud = m.answer_key in ("front", "disguised_front")
        cd = (pd.Timestamp(m.change_start_date) - start).days if isinstance(m.change_start_date, str) and m.change_start_date else None
        first = int(np.argmax(lv >= 3)) if (lv >= 3).any() else None
        rows.append(dict(mid=m.merchant_id, name=m.name, category=m.cat_key, city=m.city, kind=m.answer_key,
                         fraud=fraud, max_level=int(lv.max()),
                         caught=bool((lv >= 3).any()) if fraud else False,
                         disrupted=bool((lv >= 3).any()) if not fraud else False,
                         asked=bool((lv >= 2).any()),
                         days_to_act=(first - cd) if (fraud and first is not None and cd is not None) else None,
                         vol_caught=bool(vr.any()) if fraud else False,
                         vol_disrupted=bool(vr.any()) if not fraud else False, vol_days=int(vr.sum())))
    return pd.DataFrame(rows)


def summarise(ev):
    f, h = ev[ev.fraud], ev[~ev.fraud]
    days = f.days_to_act.dropna()
    return dict(shops=int(len(ev)), fronts=int(len(f)), honest=int(len(h)),
                trueshape=dict(caught=int(f.caught.sum()), disrupted=int(h.disrupted.sum()),
                               asked_only=int((h.asked & ~h.disrupted).sum()),
                               median_days=float(days.median()) if len(days) else None,
                               min_days=int(days.min()) if len(days) else None,
                               max_days=int(days.max()) if len(days) else None),
                volume_rule=dict(caught=int(f.vol_caught.sum()), disrupted=int(h.vol_disrupted.sum())))
