"""
TrueShape v2 - synthetic payment simulator (Team Dhurandhar).

3 categories (bakery, kirana, mobile & accessories) x 2 cities (Hyderabad,
Mumbai) x 28 shops = 168 merchants, 1 Jul - 3 Nov 2026 (126 days).

Produces the data a payment aggregator already holds:
  merchants.csv     declared business details (+ answer key, for scoring only)
  transactions.csv  one row per payment
  cashouts.csv      one row per merchant-day: money pulled out within 1 hour
  calendar.csv      festivals (real 2026 dates) and cricket match days (invented)
ALL DATA IS SYNTHETIC.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

START = pd.Timestamp("2026-07-01")
END = pd.Timestamp("2026-11-03")
DAYS = pd.date_range(START, END, freq="D")
N_DAYS = len(DAYS)                       # 126

CITIES = {
    "Hyderabad": dict(state="Telangana", ganesh=1.0,
                      areas=["Kondapur", "Madhapur", "Gachibowli", "Ameerpet", "Kukatpally", "Banjara Hills", "Begumpet",
                             "Secunderabad", "Dilsukhnagar", "Miyapur", "Jubilee Hills", "Tarnaka", "LB Nagar",
                             "Manikonda", "Uppal", "Himayatnagar", "Mehdipatnam", "Attapur"]),
    "Mumbai": dict(state="Maharashtra", ganesh=1.25,
                   areas=["Andheri", "Bandra", "Dadar", "Borivali", "Malad", "Goregaon", "Powai", "Ghatkopar", "Kurla",
                          "Chembur", "Vile Parle", "Lower Parel", "Matunga", "Mulund", "Kandivali", "Santacruz",
                          "Girgaon", "Sion"]),
}
ALL_STATES = ["Telangana", "Maharashtra", "Andhra Pradesh", "Karnataka", "Tamil Nadu", "Uttar Pradesh", "Bihar",
              "West Bengal", "Rajasthan", "Gujarat", "Delhi", "Madhya Pradesh", "Odisha", "Kerala", "Punjab",
              "Haryana", "Assam", "Jharkhand"]


# ------------------------------------------------------------------ calendar
def _day(s):
    return (pd.Timestamp(s) - START).days


def make_calendar(seed=26):
    rng = np.random.default_rng(seed)
    fest = {k: np.ones(N_DAYS) for k in ["ganesh", "dussehra", "diwali"]}
    name = [""] * N_DAYS
    # Ganesh Chaturthi 14 Sep, festival runs to Anant Chaturdashi 24 Sep
    for off, m in zip(range(-2, 11), [1.3, 1.7, 2.3, 1.6, 1.4, 1.3, 1.2, 1.2, 1.2, 1.2, 1.3, 1.4, 1.7]):
        d = _day("2026-09-14") + off; fest["ganesh"][d] = m; name[d] = "Ganesh Chaturthi"
    # Navratri 11-19 Oct, Dussehra 20 Oct
    for d in range(_day("2026-10-11"), _day("2026-10-20")):
        fest["dussehra"][d] = 1.15; name[d] = "Navratri"
    for off, m in [(-1, 1.6), (0, 2.4), (1, 1.2)]:
        d = _day("2026-10-20") + off; fest["dussehra"][d] = max(fest["dussehra"][d], m); name[d] = "Dussehra" if off == 0 else name[d] or "Dussehra"
    # Diwali shopping run-up (Diwali is 8 Nov, after the data ends)
    for i, d in enumerate(range(_day("2026-10-27"), N_DAYS)):
        fest["diwali"][d] = 1.1 + 0.11 * i; name[d] = "Diwali shopping"
    match = np.zeros(N_DAYS, bool)
    a, b = _day("2026-08-20"), _day("2026-10-21") + 1
    match[a:b] = rng.random(b - a) < 0.65
    big = match & (rng.random(N_DAYS) < 0.25)
    return pd.DataFrame({"date": DAYS, "weekday": DAYS.day_name(), "festival": name,
                         "ganesh_x": fest["ganesh"], "dussehra_x": fest["dussehra"], "diwali_x": fest["diwali"],
                         "is_match_day": match, "is_big_match": big})


CAL = make_calendar()
_MATCH, _BIG = CAL["is_match_day"].values, CAL["is_big_match"].values


def _norm(a):
    a = np.asarray(a, float)
    return a / a.sum()


def _hours(pairs):
    h = np.zeros(24)
    for k, v in pairs.items():
        h[k] = v
    return _norm(h)


# ------------------------------------------------------------------ category profiles
BAKERY_HOURS = _norm([0, 0, 0, 0, 0, 0, .2, 2.5, 4.5, 4, 2.5, 2.2, 2.8, 2.4, 2, 2.2, 3, 4.2, 4.8, 4.5, 3.5, 2.2, .9, .1])
KIRANA_HOURS = _norm([0, 0, 0, 0, 0, 0, .6, 2.8, 4.2, 3.8, 2.8, 2.2, 2, 1.6, 1.3, 1.5, 2.2, 3.4, 4.4, 4.8, 4.2, 3, 1.4, .2])
MOBILE_HOURS = _norm([0, 0, 0, 0, 0, 0, 0, 0, 0, .3, 1.8, 3, 3.6, 3.4, 2.8, 2.6, 2.8, 3.3, 4, 4.4, 4.2, 3.2, 1.2, 0])
BET_HOURS = _norm([3, 2.5, 1.6, .8, .3, .1, .1, .2, .3, .4, .5, .6, .8, .9, 1, 1.4, 2.2, 3.5, 5, 6, 6, 5.5, 4.8, 4])
NIGHT_ORDER_HOURS = _hours({21: 1.5, 22: 3, 23: 4, 0: 2.5, 1: .6})
STADIUM_HOURS = _hours({15: .05, 16: .1, 17: .15, 18: .2, 19: .15, 20: .12, 21: .1, 22: .08, 23: .05})

BAKERY_MENU = np.array([25, 30, 40, 45, 60, 80, 90, 110, 120, 150, 180, 220, 250, 320, 380, 450])
CAKES = np.array([450, 500, 550, 650, 750, 850, 900, 1000, 1200, 1500])
KIRANA_ITEMS = np.array([10, 12, 15, 20, 22, 25, 28, 30, 35, 40, 45, 48, 52, 55, 60, 65, 72, 80, 88, 95, 110, 120,
                         135, 150, 165, 180, 210, 240, 275, 320, 399, 450, 520])
RECHARGE = np.array([19, 29, 99, 155, 199, 239, 249, 299, 349, 399, 449, 479, 549, 599, 666, 719, 749, 839, 859, 999])
ACCESSORY = np.array([149, 199, 249, 299, 349, 399, 449, 499, 599, 699, 799, 999, 1299, 1499, 1999])
REPAIR = np.array([350, 450, 600, 800, 1200, 1500, 2500])
PHONES = np.array([7999, 9499, 10999, 12999, 14999, 17999, 21999, 27999])


def bakery_amounts(rng, n, fest=1.0, d=0):
    k = rng.choice([1, 2, 3, 4], n, p=[.35, .35, .2, .1])
    idx = rng.integers(0, len(BAKERY_MENU), (n, 4))
    amt = (BAKERY_MENU[idx] * (np.arange(4) < k[:, None])).sum(1).astype(float)
    cake = rng.random(n) < 0.06 * fest
    amt[cake] += CAKES[rng.integers(0, len(CAKES), cake.sum())] * (0.9 + 0.2 * rng.random(cake.sum()))
    return np.round(amt).astype(int)


def kirana_amounts(rng, n, fest=1.0, d=0):
    k = np.minimum(rng.geometric(0.45, n), 12)
    idx = rng.integers(0, len(KIRANA_ITEMS), (n, 12))
    amt = (KIRANA_ITEMS[idx] * (np.arange(12) < k[:, None])).sum(1).astype(float)
    dom = DAYS[d].day
    p_month = 0.10 if dom <= 5 else 0.02                    # monthly grocery run after salary day
    big = rng.random(n) < p_month * fest
    amt[big] = rng.integers(1200, 4500, big.sum())
    return np.round(amt).astype(int)


def mobile_amounts(rng, n, fest=1.0, d=0):
    kind = rng.choice(4, n, p=_norm([.55, .35, .07, .03 * fest]))
    amt = np.where(kind == 0, RECHARGE[rng.integers(0, len(RECHARGE), n)],
          np.where(kind == 1, ACCESSORY[rng.integers(0, len(ACCESSORY), n)],
          np.where(kind == 2, REPAIR[rng.integers(0, len(REPAIR), n)], PHONES[rng.integers(0, len(PHONES), n)])))
    return amt.astype(int)


CATEGORIES = {
    "bakery": dict(label="Bakery", mcc=5462, rate=(30, 95), amounts=bakery_amounts, hours=BAKERY_HOURS,
                   p_regular=(.55, .68), p_out=.03, cashout=(2, 30), fest_w=dict(ganesh=1.0, dussehra=1.0, diwali=0.9),
                   big=500, typical_bill=380,
                   prefix=["Sri", "New", "Royal", "Fresh", "Golden", "Sunrise", "Krishna", "Lakshmi", "Cream", "Daily",
                           "City", "Star", "Classic", "Sweet", "Honey", "Oven", "Modern", "Kamat"],
                   suffix=["Bakery", "Bakers", "Cake House", "Bake Studio", "Bakery & Cafe", "Patisserie", "Cakes",
                           "Sweets & Bakes"]),
    "kirana": dict(label="Kirana / grocery", mcc=5411, rate=(60, 120), amounts=kirana_amounts, hours=KIRANA_HOURS,
                   p_regular=(.65, .78), p_out=.02, cashout=(2, 30), fest_w=dict(ganesh=.6, dussehra=.5, diwali=1.2),
                   big=500, typical_bill=330,
                   prefix=["Sri Balaji", "Laxmi", "Om Sai", "New Gupta", "Ganesh", "Annapurna", "Sai Ram", "Patel",
                           "Mahalaxmi", "Jai Bhavani", "Shree Krishna", "Venkateswara", "Siddhi Vinayak", "Durga"],
                   suffix=["Kirana", "General Stores", "Provision Store", "Supermart", "Kirana & General",
                           "Daily Needs", "Stores"]),
    "mobile": dict(label="Mobile & accessories", mcc=4812, rate=(25, 55), amounts=mobile_amounts, hours=MOBILE_HOURS,
                   p_regular=(.40, .55), p_out=.05, cashout=(3, 25), fest_w=dict(ganesh=.3, dussehra=.6, diwali=1.5),
                   big=2000, typical_bill=1030,
                   prefix=["Sai", "Royal", "Galaxy", "Jai Mata Di", "Smart", "Krishna", "New Star", "Hello",
                           "Connect", "Speed", "Mobile", "City", "Prime", "Metro"],
                   suffix=["Mobiles", "Mobile Point", "Mobiles & Accessories", "Communication", "Recharge Point",
                           "Mobile Care", "Telecom"]),
}

# honest changes per category (kind -> count in each city), the rest stay plain honest
CHANGES = {
    "bakery": {"grower": 2, "night_orders": 2, "bulk": 1, "stadium": 1, "sweeper": 1, "delivery": 1},
    "kirana": {"grower": 2, "khata": 2, "night_orders": 1, "delivery": 2, "sweeper": 1},
    "mobile": {"grower": 2, "online": 2, "bulk": 1, "sweeper": 1, "delivery": 1},
}
KINDS = {
    "honest": "Honest, no change",
    "grower": "Honest: opened a second branch",
    "night_orders": "Honest: started late-night orders",
    "bulk": "Honest: started bulk / corporate orders",
    "stadium": "Honest: shop next to a cricket stadium",
    "sweeper": "Honest: moves takings to savings every morning",
    "delivery": "Honest: started home delivery",
    "khata": "Honest: regulars settle monthly credit (khata)",
    "online": "Honest: started selling online across India",
    "front": "Betting front",
    "disguised_front": "Careful betting front",
}
FRAUD = {"front", "disguised_front"}
BET_STAKES = np.array([100, 200, 300, 500, 1000, 2000, 5000, 10000])
BET_P = _norm([.10, .17, .08, .27, .22, .10, .05, .01])


class Regulars:
    def __init__(self, rng, prefix, n, home):
        self.rng, self.prefix, self.n, self.home = rng, prefix, max(10, n), home
        w = 1 / np.arange(1, self.n + 1) ** 0.8
        self.w = w / w.sum()
        self.walk = 0

    def draw(self, n, p_regular, p_out, far_states=None):
        rng = self.rng
        reg = rng.random(n) < p_regular
        ids = np.empty(n, object)
        ids[reg] = [f"{self.prefix}R{x}" for x in rng.choice(self.n, reg.sum(), p=self.w)]
        nw = int((~reg).sum())
        ids[~reg] = [f"{self.prefix}W{self.walk + j}" for j in range(nw)]
        self.walk += nw
        st = np.full(n, self.home, object)
        far = (~reg) & (rng.random(n) < p_out)
        pool = far_states or [s for s in ALL_STATES if s != self.home]
        st[far] = rng.choice(pool, far.sum())
        return ids, st


class Bettors:
    def __init__(self, rng, prefix, home):
        self.rng, self.prefix, self.home, self.ids, self.st = rng, prefix, home, [], []
        self.others = [s for s in ALL_STATES if s != home]

    def draw(self, n, p_return=0.35):
        rng = self.rng
        k = rng.binomial(n, p_return) if self.ids else 0
        pick = rng.integers(0, len(self.ids), k) if k else []
        ids = [self.ids[j] for j in pick]
        st = [self.st[j] for j in pick]
        for _ in range(n - k):
            pid = f"{self.prefix}B{len(self.ids)}"
            s = self.home if rng.random() < .12 else self.others[rng.integers(len(self.others))]
            self.ids.append(pid); self.st.append(s); ids.append(pid); st.append(s)
        return np.array(ids, object), np.array(st, object)


def simulate_merchant(mid, category, city, kind, rate, change_day, seed, fest_sens=None):
    rng = np.random.default_rng(seed)
    C, home = CATEGORIES[category], CITIES[city]["state"]
    amounts, hours = C["amounts"], C["hours"]
    cd = 10 ** 9 if change_day is None else int(change_day)
    fs = rng.uniform(.7, 1.15) if fest_sens is None else fest_sens
    w = C["fest_w"]
    fest_series = (1 + (CAL["ganesh_x"].values - 1) * w["ganesh"] * CITIES[city]["ganesh"] * fs
                   + (CAL["dussehra_x"].values - 1) * w["dussehra"] * fs
                   + (CAL["diwali_x"].values - 1) * w["diwali"] * fs)
    p_reg = rng.uniform(*C["p_regular"])
    book = Regulars(rng, f"{mid}-", int(rate * 6), home)
    book2 = Regulars(rng, f"{mid}-b", int(rate * 5), home)
    bettors = Bettors(rng, f"{mid}-", home)
    parts, cash = [], []
    for d, day in enumerate(DAYS):
        wk = day.dayofweek >= 5
        fest = fest_series[d]
        after = d >= cd
        lam = rate * (1.2 if wk else 1.0) * fest
        if kind in FRAUD and after:
            lam *= .45 if kind == "front" else .8
        n = rng.poisson(lam)
        A = [amounts(rng, n, fest, d)]; Hh = [rng.choice(24, n, p=hours)]
        i0, s0 = book.draw(n, p_reg, C["p_out"])
        I, S, SRC = [i0], [s0], [np.full(n, "shop", object)]
        co = rng.beta(*C["cashout"])

        def add(a, h, i, s, src="shop"):
            A.append(np.asarray(a, int)); Hh.append(np.asarray(h, int)); I.append(i); S.append(s)
            SRC.append(np.full(len(a), src, object))

        if kind == "grower" and after:
            k = rng.poisson(rate * 1.1 * min(1, (d - cd + 1) / 14) * (1.2 if wk else 1) * fest)
            i2, s2 = book2.draw(k, min(p_reg, .15 + .03 * (d - cd)), C["p_out"])
            add(amounts(rng, k, fest, d), rng.choice(24, k, p=hours), i2, s2)
        if kind == "night_orders" and after:
            k = rng.poisson(rate * .35 * (1.4 if wk else 1))
            a = CAKES[rng.integers(0, len(CAKES), k)] if category == "bakery" else amounts(rng, k, fest, d)
            i3, s3 = book.draw(k, p_reg * .8, C["p_out"])
            add(a, rng.choice(24, k, p=NIGHT_ORDER_HOURS), i3, s3)
        if kind == "bulk" and after and rng.random() < .15:
            k = int(rng.integers(1, 4))
            a = rng.integers(15, 80, k) * 100 if category == "bakery" else rng.integers(4, 12, k) * 2999
            i4, s4 = book.draw(k, .2, C["p_out"])
            add(a, rng.choice([11, 12, 15, 16], k), i4, s4)
        if kind == "stadium" and after and _MATCH[d]:
            k = rng.poisson(rate * (.9 + (.8 if _BIG[d] else 0)))
            i5, s5 = book.draw(k, .15, .12)
            add(amounts(rng, k), rng.choice(24, k, p=STADIUM_HOURS), i5, s5)
        if kind == "sweeper" and after:
            co = rng.beta(12, 6)
        if kind == "delivery" and after:
            k = rng.poisson(rate * .4 * min(1, (d - cd + 1) / 10))
            i6, s6 = book2.draw(k, min(.5, .1 + .02 * (d - cd)), C["p_out"])
            add(amounts(rng, k, fest, d), rng.choice(24, k, p=hours), i6, s6)
        if kind == "khata" and after and DAYS[d].day <= 5:
            k = rng.poisson(rate * .12)
            i7, s7 = book.draw(k, .97, 0)
            add(rng.choice([1000, 1500, 2000, 2500, 3000, 3500, 4000, 5000], k), rng.choice(24, k, p=hours), i7, s7)
        if kind == "online" and after:
            k = rng.poisson(rate * .5 * min(1, (d - cd + 1) / 14))
            i8, s8 = book2.draw(k, .05, .75)
            add(ACCESSORY[rng.integers(0, len(ACCESSORY), k)], rng.choice(24, k, p=_norm(np.r_[np.full(7, .2), np.ones(17)])), i8, s8)
        if kind == "front" and after:
            k = rng.poisson(min(1, (d - cd + 1) / 7) * (35 + (140 if _MATCH[d] else 0) + (120 if _BIG[d] else 0)))
            a = rng.choice(BET_STAKES, k, p=BET_P)
            ib, sb = bettors.draw(k)
            add(a, rng.choice(24, k, p=BET_HOURS), ib, sb, "bet")
            co = min(.97, co + .9 * a.sum() / max(1, sum(x.sum() for x in A)))
        if kind == "disguised_front" and after:
            k = rng.poisson(min(1, (d - cd + 1) / 21) * (11 + (24 if _MATCH[d] else 0) + (20 if _BIG[d] else 0)))
            a = rng.choice(BET_STAKES[:6], k, p=_norm(BET_P[:6])) + rng.choice([-9, -7, -3, 3, 7, 9, -1, 1], k)
            ib, sb = bettors.draw(k)
            add(a, rng.choice(24, k, p=_norm(.55 * hours + .45 * BET_HOURS)), ib, sb, "bet")
            co = min(.95, co + .75 * a.sum() / max(1, sum(x.sum() for x in A)))

        amt = np.concatenate(A)
        if len(amt):
            h = np.concatenate(Hh)
            ts = day.to_datetime64() + (h * 60 + rng.integers(0, 60, len(amt))).astype("timedelta64[m]")
            src = np.concatenate(SRC)
            card_p = .25 if category == "mobile" else .1
            mode = np.where(src == "bet", rng.choice(["UPI QR", "UPI link"], len(amt), p=[.75, .25]),
                            rng.choice(["UPI QR", "Card", "UPI link"], len(amt), p=[1 - card_p - .03, card_p, .03]))
            parts.append(pd.DataFrame({"merchant_id": mid, "timestamp": ts, "amount_inr": amt,
                                       "payer_id": np.concatenate(I), "payer_state": np.concatenate(S),
                                       "payment_mode": mode, "answer_key_source": src}))
        gross = int(amt.sum()) if len(amt) else 0
        cash.append((mid, day.date(), gross, int(round(gross * co)), round(float(co), 4)))
    tx = pd.concat(parts, ignore_index=True).sort_values("timestamp", ignore_index=True)
    co = pd.DataFrame(cash, columns=["merchant_id", "date", "gross_sales_inr", "pulled_out_within_1h_inr",
                                     "share_pulled_out_within_1h"])
    return tx, co


# ------------------------------------------------------------------ the 168 merchants
STORY = {   # Hyderabad bakeries from the first prototype
    "M001": dict(name="Sweet Crumbs Bakery", area="Kondapur", kind="honest", fest=1.3,
                 note="Ordinary bakery, very busy at Ganesh Chaturthi and Dussehra."),
    "M002": dict(name="Ovenly Bakes", area="Madhapur", kind="grower", change="2026-09-04",
                 note="Opens a second branch in early September. Sales double."),
    "M003": dict(name="Midnight Cakes", area="Gachibowli", kind="night_orders", change="2026-08-25",
                 note="Starts midnight birthday-cake delivery."),
    "M004": dict(name="Golden Crust Bakery", area="Ameerpet", kind="front", change="2026-09-09",
                 note="Real licence. Starts collecting cricket bets in September."),
    "M005": dict(name="Daily Bread Co.", area="Kukatpally", kind="disguised_front", change="2026-09-13",
                 note="Careful front: starts during Ganesh Chaturthi, odd amounts, shop hours."),
}
PER_GROUP = 28


def merchant_list(seed=26):
    rng = np.random.default_rng(seed)
    out, used, n = [], set(), 1
    story = iter(STORY.items())
    for city in CITIES:
        for g, cat in enumerate(CATEGORIES):
            C = CATEGORIES[cat]
            kinds = []
            for k, c in CHANGES[cat].items():
                kinds += [k] * c
            gi = list(CITIES).index(city) * 3 + g
            fronts = ["front", "front", "disguised_front"] if gi % 2 == 0 else ["front", "disguised_front", "disguised_front"]
            kinds += ["honest"] * (PER_GROUP - len(kinds) - 3)
            rng.shuffle(kinds)
            kinds += fronts
            if city == "Hyderabad" and cat == "bakery":          # the five story shops come first
                story_kinds = ["honest", "grower", "night_orders", "front", "disguised_front"]
                rest = kinds[:]
                for k in story_kinds:
                    rest.remove(k)
                kinds = story_kinds + rest
            for k in kinds:
                mid = f"M{n:03d}"
                m = dict(merchant_id=mid, category=cat, city=city, kind=k)
                if mid in STORY:
                    s = next(story)[1]
                    m.update(name=s["name"], area=s["area"], note=s["note"], fest=s.get("fest"))
                    m["change_day"] = _day(s["change"]) if "change" in s else None
                    used.add(s["name"])
                else:
                    while True:
                        nm = f"{C['prefix'][rng.integers(len(C['prefix']))]} {C['suffix'][rng.integers(len(C['suffix']))]}"
                        if nm not in used:
                            used.add(nm); break
                    m.update(name=nm, area=CITIES[city]["areas"][rng.integers(len(CITIES[city]["areas"]))], note="", fest=None)
                    if k == "stadium":
                        m["change_day"] = _day("2026-08-20")
                    elif k == "khata":
                        m["change_day"] = int(rng.integers(_day("2026-08-01"), _day("2026-09-01")))
                    elif k in FRAUD:
                        m["change_day"] = int(rng.integers(_day("2026-08-25"), _day("2026-10-05")))
                    elif k != "honest":
                        m["change_day"] = int(rng.integers(_day("2026-08-20"), _day("2026-10-15")))
                    else:
                        m["change_day"] = None
                lo, hi = C["rate"]
                m["rate"] = float(rng.uniform(lo, hi) if k not in FRAUD else rng.uniform(lo, (lo + hi) / 2 + 5))
                out.append(m); n += 1
    return out


def anonymise_payers(tx, seed=7):
    """Payer IDs in the raw data must not reveal who is a regular or a bettor."""
    codes, uniq = pd.factorize(tx["payer_id"])
    perm = np.random.default_rng(seed).permutation(len(uniq))
    tx["payer_id"] = pd.Series([f"PY{p:07d}" for p in perm])[codes].values
    return tx


def generate_dataset(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    ms = merchant_list()
    rng = np.random.default_rng(99)
    txs, cos = [], []
    for j, m in enumerate(ms):
        tx, co = simulate_merchant(m["merchant_id"], m["category"], m["city"], m["kind"], m["rate"],
                                   m["change_day"], seed=1000 + j, fest_sens=m.get("fest"))
        txs.append(tx); cos.append(co)
    tx = pd.concat(txs, ignore_index=True)
    tx = anonymise_payers(tx)
    tx.insert(0, "txn_id", [f"T{i:08d}" for i in range(1, len(tx) + 1)])
    tx["date"] = tx["timestamp"].dt.date
    tx["time"] = tx["timestamp"].dt.strftime("%H:%M")
    tx = tx[["txn_id", "merchant_id", "date", "time", "timestamp", "amount_inr", "payer_id", "payer_state",
             "payment_mode", "answer_key_source"]]
    tx.to_csv(out / "transactions.csv", index=False)
    pd.concat(cos, ignore_index=True).to_csv(out / "cashouts.csv", index=False)
    CAL.to_csv(out / "calendar.csv", index=False)
    rows = []
    for m in ms:
        C = CATEGORIES[m["category"]]
        onboard = pd.Timestamp("2025-01-01") + pd.Timedelta(days=int(rng.integers(0, 500)))
        avg = round(C["typical_bill"] * rng.uniform(.85, 1.15), -1)
        rows.append(dict(
            merchant_id=m["merchant_id"], name=m["name"], category=C["label"], mcc=C["mcc"], city=m["city"],
            state=CITIES[m["city"]]["state"], area=m["area"], onboarded_on=onboard.date(),
            declared_avg_bill_inr=int(avg), declared_monthly_sales_inr=int(round(m["rate"] * 30 * avg, -4)),
            answer_key=m["kind"], answer_key_label=KINDS[m["kind"]],
            change_start_date=str(DAYS[m["change_day"]].date()) if m["change_day"] is not None else "",
            story_note=m["note"]))
    md = pd.DataFrame(rows)
    md.to_csv(out / "merchants.csv", index=False)
    return md, tx


if __name__ == "__main__":
    import time
    t = time.time()
    md, tx = generate_dataset(Path(__file__).resolve().parent.parent / "data")
    print(len(md), "merchants", f"{len(tx):,} payments", f"{time.time() - t:.0f}s")
    print(md.groupby(["city", "category"]).size())
    print(md.answer_key.value_counts())
