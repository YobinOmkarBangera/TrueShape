"""Build dist/trueshape_demo.html: the frontend plus pre-computed API answers, for sharing without a server.
Run:  python build_demo.py"""
import json
import re
from pathlib import Path

from backend.service import Store, SCENARIOS, STARTS
from backend import engine as E
from backend import simulator as Sim

root = Path(__file__).resolve().parent
st = Store()
snap = dict(meta=st.meta(), overview=st.overview(), profiles=st.profiles(), results=st.results(),
            merchants={}, replies={}, sims={})
for mid in st.res:
    m = st.merchant(mid)
    snap["merchants"][mid] = m
    snap["replies"][mid] = {r: st.reply(mid, r) for r in E.CATEGORY_REPLIES[m["category"]]}
for cat in Sim.CATEGORIES:
    for city in Sim.CITIES:
        for sc in SCENARIOS[cat]:
            for start in STARTS:
                snap["sims"][f"{cat}|{city}|{sc[0]}|{start}"] = st.simulate(cat, city, sc[0], start, seed=2026)

html = (root / "frontend/index.html").read_text(encoding="utf-8")
css = (root / "frontend/styles.css").read_text(encoding="utf-8")
js = (root / "frontend/app.js").read_text(encoding="utf-8")
head = "\n".join(re.findall(r"<title>.*?</title>|<meta name=\"claude:[^>]+>|<link rel=\"(?:icon|preconnect|stylesheet)\" href=\"https://fonts[^>]+>|<link rel=\"icon\"[^>]+>", html))
body = re.search(r"<body>(.*)</body>", html, re.S).group(1).replace('<script src="app.js"></script>', "")
data = json.dumps(snap, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
out = f"<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n{head}\n<style>\n{css}\n</style>\n{body}\n<script>window.SNAPSHOT={data};</script>\n<script>\n{js}\n</script>\n"
(root / "dist").mkdir(exist_ok=True)
(root / "dist/trueshape_demo.html").write_text(out, encoding="utf-8")
print("dist/trueshape_demo.html", len(out.encode("utf-8")) // 1024, "KB")
