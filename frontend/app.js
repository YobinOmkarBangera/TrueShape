/* TrueShape v2 frontend. Talks to the FastAPI backend (/api/...). In the shareable single-file demo,
   window.SNAPSHOT holds pre-computed API answers so the page works without a server. */
"use strict";

// ------------------------------------------------------------------ API
const LIVE = !window.SNAPSHOT;
const api = {
  async get(path) {
    if (!LIVE) return snapGet(path);
    const r = await fetch(path);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `The server answered ${r.status}.`);
    return r.json();
  },
  async post(path, body, isForm) {
    if (!LIVE) return snapPost(path, body);
    const r = await fetch(path, isForm ? { method: "POST", body } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `The server answered ${r.status}.`);
    return r.json();
  },
};
function snapGet(path) {
  const S = window.SNAPSHOT;
  const simple = { "/api/meta": "meta", "/api/overview": "overview", "/api/profiles": "profiles", "/api/results": "results" };
  if (simple[path]) return S[simple[path]];
  const m = path.match(/^\/api\/merchants\/(\w+)$/);
  if (m && S.merchants[m[1]]) return S.merchants[m[1]];
  throw new Error("This page is not in the demo snapshot.");
}
function snapPost(path, body) {
  const S = window.SNAPSHOT;
  const m = path.match(/^\/api\/merchants\/(\w+)\/reply$/);
  if (m) return S.replies[m[1]][body.reason];
  if (path === "/api/simulate") return S.sims[`${body.category}|${body.city}|${body.scenario}|${body.start}`];
  throw new Error("Uploading a file needs the full app running on a laptop (python run.py).");
}

// ------------------------------------------------------------------ helpers
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const lc = l => `var(--l${l})`;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmtD = iso => { if (!iso) return ""; const [, m, d] = iso.split("-").map(Number); return `${d} ${MONTHS[m - 1]}`; };
const fmtDY = iso => { if (!iso) return ""; const [y, m, d] = iso.split("-").map(Number); return `${d} ${MONTHS[m - 1]} ${y}`; };
const pct = v => `${Math.round(v * 100)}%`;
const inr = v => "₹" + Math.round(v).toLocaleString("en-IN");
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
let META = null, OVERVIEW = null, PROFILES = null, RESULTS = null;
const state = { city: "all", cat: "all", filter: "action", q: "", key: false, showAll: false,
  tcat: "bakery", tcity: "Hyderabad", tsc: "front", tstart: "mid", ucat: "bakery", ucity: "Hyderabad", fcity: "Mumbai" };
const CAT = () => Object.fromEntries(META.categories.map(c => [c.key, c]));
const catTag = k => `<span class="cat" style="--cc:var(--c-${k})"><i></i>${esc(CAT()[k].short)}</span>`;

function pill(level, lg) {
  const L = META.levels[level];
  return `<span class="pill${lg ? " lg" : ""}" style="--lc:${lc(level)}">${esc(lg ? L.label : L.short)}</span>`;
}
function svg(vb, inner, cls = "", label = "") {
  return `<svg viewBox="${vb}" class="${cls}" role="img" aria-label="${esc(label)}" preserveAspectRatio="xMidYMid meet">${inner}</svg>`;
}

// ------------------------------------------------------------------ shapes (the signature element)
function polyPts(vals, cx, cy, r) {
  const n = vals.length;
  return vals.map((v, i) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; return `${(cx + Math.cos(a) * r * v).toFixed(1)},${(cy + Math.sin(a) * r * v).toFixed(1)}`; }).join(" ");
}
function glyph(g, level) {
  const c = lc(level >= 2 ? Math.max(level, 3) : level);
  const ring = polyPts([1, 1, 1, 1, 1, 1], 22, 22, 19);
  return svg("0 0 44 44", `<polygon points="${ring}" fill="var(--sunk)" stroke="var(--line)"/>
    <polygon points="${polyPts(g.normal, 22, 22, 19)}" fill="none" stroke="var(--faint)" stroke-dasharray="2 2"/>
    <polygon points="${polyPts(g.now, 22, 22, 19)}" fill="${c}" fill-opacity=".28" stroke="${c}" stroke-width="1.6" stroke-linejoin="round"/>`,
    "glyph", "This shop's current shape against its own normal");
}
function radar(R, color, opts = {}) {
  const axes = META.radar_axes, n = axes.length, cx = 220, cy = 178, rad = opts.small ? 118 : 128;
  const pt = (i, f) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; return [cx + Math.cos(a) * rad * f, cy + Math.sin(a) * rad * f]; };
  const poly = vals => vals.map((v, i) => pt(i, v.norm).map(c => c.toFixed(1)).join(",")).join(" ");
  let g = "";
  [0.25, 0.5, 0.75, 1].forEach(f => { g += `<polygon points="${axes.map((_, i) => pt(i, f).join(",")).join(" ")}" fill="none" stroke="var(--line)"/>`; });
  axes.forEach((a, i) => {
    const [x, y] = pt(i, 1); g += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="var(--line)"/>`;
    const [lx, ly] = pt(i, 1.19);
    const anchor = Math.abs(lx - cx) < 8 ? "middle" : lx > cx ? "start" : "end";
    g += `<text x="${lx.toFixed(1)}" y="${(ly + (ly < cy - 40 ? -2 : ly > cy + 40 ? 12 : 4)).toFixed(1)}" text-anchor="${anchor}" font-size="${opts.small ? 21 : 13}" font-weight="600" fill="var(--muted)">${esc(a.label)}</text>`;
  });
  if (R.typical) g += `<polygon points="${poly(R.typical)}" fill="var(--typical)" fill-opacity=".2" stroke="var(--typical)" stroke-width="1.5"/>`;
  if (R.normal) g += `<polygon points="${poly(R.normal)}" fill="none" stroke="var(--ink)" stroke-width="1.6" stroke-dasharray="5 4" opacity=".7"/>`;
  g += `<polygon points="${poly(R.now)}" fill="${color}" fill-opacity=".2" stroke="${color}" stroke-width="2.4" stroke-linejoin="round" class="${reduced() ? "" : "pop"}" style="transform-origin:${cx}px ${cy}px"/>`;
  R.now.forEach((v, i) => { const [x, y] = pt(i, v.norm); g += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" fill="${color}" stroke="var(--surface)" stroke-width="2"/>`; });
  return `<svg viewBox="-60 0 560 360" class="radar" role="img" aria-label="${esc(opts.label || "Business shape")}">${g}</svg>`;
}
const fmtAxis = (a, v) => a.fmt === "x" ? `${v.value.toFixed(1)}×` : pct(v.value);

function gauge(score, level) {
  const r = 52, C = 2 * Math.PI * r, f = Math.max(0.01, score / 100);
  return `<div class="gauge">${svg("0 0 128 128", `
    <circle cx="64" cy="64" r="${r}" fill="none" stroke="var(--sunk)" stroke-width="11"/>
    <circle cx="64" cy="64" r="${r}" fill="none" stroke="${lc(level)}" stroke-width="11" stroke-linecap="round" stroke-dasharray="${(C * f).toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 64 64)"/>
    <text x="64" y="71" text-anchor="middle" font-family="Bricolage Grotesque, system-ui, sans-serif" font-size="32" font-weight="700" fill="var(--ink)">${score}</text>
    <text x="64" y="89" text-anchor="middle" font-size="11" fill="var(--muted)">out of 100</text>`, "", `Mismatch score ${score} out of 100`)}
    <span class="kicker">Mismatch score</span></div>`;
}

function bars(normal, now, labels, title) {
  const W = 380, H = 156, L = 30, B = 22, T = 8, n = normal.length;
  const max = Math.max(0.05, ...normal, ...now) * 1.1;
  const bw = (W - L) / n, y = v => T + (H - B - T) * (1 - v / max);
  let g = "";
  [0, 0.5, 1].forEach(f => { const v = max * f, yy = y(v); g += `<line x1="${L}" x2="${W}" y1="${yy}" y2="${yy}" stroke="var(--line)"/><text x="${L - 5}" y="${yy + 3.5}" text-anchor="end" font-size="10" fill="var(--faint)">${Math.round(v * 100)}%</text>`; });
  for (let i = 0; i < n; i++) {
    const w = bw * 0.36, x0 = L + i * bw + bw * 0.12;
    const bar = (x, v, fill, op, lab) => { const h = H - B - y(v); return h > 0.4 ? `<path d="M${x.toFixed(1)},${(H - B).toFixed(1)}V${(y(v) + Math.min(3, h)).toFixed(1)}q0,-${Math.min(3, h).toFixed(1)} ${Math.min(3, w / 2).toFixed(1)},-${Math.min(3, h).toFixed(1)}H${(x + w - Math.min(3, w / 2)).toFixed(1)}q${Math.min(3, w / 2).toFixed(1)},0 ${Math.min(3, w / 2).toFixed(1)},${Math.min(3, h).toFixed(1)}V${(H - B).toFixed(1)}Z" fill="${fill}" opacity="${op}"><title>${esc(lab)}: ${Math.round(v * 100)}%</title></path>` : ""; };
    g += bar(x0, normal[i], "var(--typical)", .6, `Normal weeks, ${labels[i] || "hour " + i}`);
    g += bar(x0 + w + 2, now[i], "var(--accent)", 1, `Last 7 days, ${labels[i] || "hour " + i}`);
    if (labels[i]) g += `<text x="${(L + i * bw + bw / 2).toFixed(1)}" y="${H - 6}" text-anchor="middle" font-size="10" fill="var(--faint)">${esc(labels[i])}</text>`;
  }
  return svg(`0 0 ${W} ${H}`, g, "", title);
}

// ------------------------------------------------------------------ the main timeline (two panels, one x-axis)
function timeline(p, host) {
  const dates = p.dates || META.dates, n = dates.length;
  const fest = p.dates ? [] : META.festival, match = p.dates ? [] : META.match;
  const W = 760, L = 40, R = 14, top = [16, 132], bot = [170, 268], H = 300;
  const x = i => L + (i / (n - 1)) * (W - L - R);
  const vmax = Math.max(3, ...p.vol_series.map(v => Math.min(v, 12))) * 1.08;
  const yv = v => top[1] - (Math.min(v, vmax) / vmax) * (top[1] - top[0]);
  const ys = v => bot[1] - (v / 100) * (bot[1] - bot[0]);
  let g = "";
  const b = META.baseline_days;
  g += `<rect x="${x(0)}" y="${top[0]}" width="${x(b - 1) - x(0)}" height="${bot[1] - top[0]}" fill="var(--sunk)" opacity=".7"/>`;
  g += `<text x="${(x(0) + x(b - 1)) / 2}" y="${bot[1] - 8}" text-anchor="middle" font-size="11" fill="var(--faint)">Learning this shop's normal (first ${b} days)</text>`;
  let run = null, lastLab = -1;
  for (let i = 0; i <= n; i++) {
    const f = i < n ? fest[i] : "";
    if (f && run === null) run = i;
    if (run !== null && (!f || f !== fest[run])) {
      g += `<rect x="${x(run) - 2}" y="${top[0]}" width="${x(i - 1) - x(run) + 4}" height="${bot[1] - top[0]}" fill="var(--festival)"/>`;
      if (fest[run] !== "Navratri") { const wd = fest[run].length * 6, endx = x(i - 1) + 2, right = x(run) + 3 + wd > W - R; const lx = right ? endx : x(run) + 3, ly = top[0] + 11 + ((right ? endx - wd : lx) < lastLab ? 12 : 0); g += `<text x="${lx}" y="${ly}" text-anchor="${right ? "end" : "start"}" font-size="10.5" font-weight="600" fill="var(--warn)">${esc(fest[run])}</text>`; lastLab = right ? endx : lx + wd; }
      run = f ? i : null;
    }
  }
  const step = vmax > 7 ? 2 : 1;
  for (let v = 0; v <= vmax; v += step) g += `<line x1="${L}" x2="${W - R}" y1="${yv(v)}" y2="${yv(v)}" stroke="var(--line)"/><text x="${L - 6}" y="${yv(v) + 3.5}" text-anchor="end" font-size="10" fill="var(--faint)">${v}×</text>`;
  [0, 50, 100].forEach(v => { g += `<line x1="${L}" x2="${W - R}" y1="${ys(v)}" y2="${ys(v)}" stroke="var(--line)"/><text x="${L - 6}" y="${ys(v) + 3.5}" text-anchor="end" font-size="10" fill="var(--faint)">${v}</text>`; });
  g += `<text x="${L}" y="${top[0] - 5}" font-size="11.5" font-weight="700" fill="var(--muted)">Weekly sales vs normal</text>`;
  g += `<text x="${L}" y="${bot[0] - 7}" font-size="11.5" font-weight="700" fill="var(--muted)">Mismatch score</text>`;
  if (vmax >= 2) g += `<line x1="${L}" x2="${W - R}" y1="${yv(2)}" y2="${yv(2)}" stroke="var(--bad)" stroke-dasharray="4 4" opacity=".8"/><text x="${x(b) + 6}" y="${yv(2) - 4}" font-size="10" fill="var(--bad)">Sales-limit rule (2×)</text>`;
  const W0 = 6;   // the first 6 days have less than a full week of data
  const path = (arr, f) => arr.slice(W0).map((v, j) => `${j ? "L" : "M"}${x(j + W0).toFixed(1)},${f(v).toFixed(1)}`).join("");
  if (p.peer_vol_series) g += `<path d="${path(p.peer_vol_series, yv)}" fill="none" stroke="var(--typical)" stroke-width="2"/>`;
  g += `<path d="${path(p.vol_series, yv)} L${x(n - 1)},${yv(0)} L${x(W0)},${yv(0)}Z" fill="var(--accent)" opacity=".08"/>`;
  g += `<path d="${path(p.vol_series, yv)}" fill="none" stroke="var(--accent)" stroke-width="2"/>`;
  for (let i = 1; i < n; i++) g += `<line x1="${x(i - 1).toFixed(1)}" y1="${ys(p.score_series[i - 1]).toFixed(1)}" x2="${x(i).toFixed(1)}" y2="${ys(p.score_series[i]).toFixed(1)}" stroke="${lc(p.level_series[i])}" stroke-width="2.4" stroke-linecap="round"/>`;
  match.forEach((m, i) => { if (m) g += `<rect x="${x(i) - .8}" y="${bot[1] + 5}" width="1.6" height="${META.big_match[i] ? 9 : 6}" fill="var(--match)" opacity="${META.big_match[i] ? .9 : .45}"/>`; });
  (p.events || []).forEach(e => {
    const i = dates.indexOf(e.date); if (i < 0) return;
    if (e.type === "ask") g += `<circle cx="${x(i)}" cy="${ys(p.score_series[i])}" r="7" fill="var(--surface)" stroke="var(--l2)" stroke-width="2"/><text x="${x(i)}" y="${ys(p.score_series[i]) + 4}" text-anchor="middle" font-size="10" font-weight="700" fill="var(--l2)">?</text>`;
    if (e.type === "level" && e.level >= 3) g += `<circle cx="${x(i)}" cy="${ys(p.score_series[i])}" r="5" fill="${lc(e.level)}" stroke="var(--surface)" stroke-width="2"/>`;
  });
  dates.forEach((d, i) => { if (d.endsWith("-01") || i === 0) g += `<text x="${x(i)}" y="${H - 2}" text-anchor="${i === 0 ? "start" : "middle"}" font-size="10.5" fill="var(--faint)">${fmtD(d)}</text>`; });
  g += `<line class="hov" x1="0" x2="0" y1="${top[0]}" y2="${bot[1]}" stroke="var(--ink)" stroke-dasharray="3 3" opacity="0"/>`;
  g += `<rect x="${L}" y="0" width="${W - L - R}" height="${H}" fill="transparent"/>`;
  host.innerHTML = svg(`0 0 ${W} ${H}`, g, "", "Weekly sales against normal, and the mismatch score over time") + `<div class="tip" hidden></div>`;
  const el = host.querySelector("svg"), tip = host.querySelector(".tip"), hov = el.querySelector(".hov");
  const move = ev => {
    const r = el.getBoundingClientRect(), px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) / r.width * W;
    const i = Math.max(0, Math.min(n - 1, Math.round((px - L) / (W - L - R) * (n - 1))));
    hov.setAttribute("x1", x(i)); hov.setAttribute("x2", x(i)); hov.setAttribute("opacity", ".5");
    tip.hidden = false; tip.style.left = `${x(i) / W * 100}%`; tip.style.top = `${ys(p.score_series[i]) / H * 100}%`;
    tip.innerHTML = `<b>${fmtD(dates[i])}</b>${fest[i] ? ", " + esc(fest[i]) : ""}${match[i] ? ", match day" : ""}<br>Sales ${p.vol_series[i].toFixed(1)}× normal${p.peer_vol_series ? ` (typical ${p.peer_vol_series[i].toFixed(1)}×)` : ""}<br>Score ${p.score_series[i]}: ${esc(META.levels[p.level_series[i]].label)}`;
  };
  el.addEventListener("mousemove", move); el.addEventListener("touchmove", move, { passive: true });
  el.addEventListener("mouseleave", () => { tip.hidden = true; hov.setAttribute("opacity", "0"); });
}

// ------------------------------------------------------------------ case file blocks
function shapeBlock(p) {
  const color = lc(p.level >= 2 ? Math.max(p.level, 3) : p.level);
  const rows = META.radar_axes.map((a, i) => {
    const ref = p.radar.typical ? Math.max(p.radar.typical[i].norm, p.radar.normal[i].norm) : p.radar.normal[i].norm;
    const hot = p.radar.now[i].norm - ref > 0.15;
    return `<span>${esc(p.radar_long[i])}</span><span class="v">${fmtAxis(a, p.radar.normal[i])}</span><span class="v">${p.radar.typical ? fmtAxis(a, p.radar.typical[i]) : "–"}</span><span class="v ${hot ? "hot" : ""}">${fmtAxis(a, p.radar.now[i])}</span>`;
  }).join("");
  const sw = (c, dash, fill) => `<svg width="26" height="12" aria-hidden="true"><rect x="1" y="2" width="24" height="8" rx="2" fill="${fill || "none"}" fill-opacity=".25" stroke="${c}" stroke-width="2" ${dash ? 'stroke-dasharray="4 3"' : ""}/></svg>`;
  return `<section class="card">
    <h2>Business shape</h2><p class="sub">Each corner is one habit. An honest shop can grow and keep its shape. A betting front changes shape.</p>
    <div class="shape">
      <div>${radar(p.radar, color, { label: `Shape of ${p.name}` })}</div>
      <div class="stack">
        <div class="shapekey">
          ${p.radar.typical ? `<div class="k">${sw("var(--typical)", false, "var(--typical)")}<span>Typical ${esc(p.noun.replace(/ies$/, "y").replace(/s$/, ""))} in ${esc(p.city)}, same week (${p.peer_size} shops)</span></div>` : ""}
          <div class="k">${sw("var(--ink)", true)}<span>This shop in its normal weeks</span></div>
          <div class="k">${sw(color, false, color)}<span><b>This shop now</b> (last 7 days)</span></div>
        </div>
        <div class="axisvals"><span class="h">Habit</span><span class="h v">Normal</span><span class="h v">Peers</span><span class="h v">Now</span>${rows}</div>
        ${p.focus_note ? `<p class="focus">${esc(p.focus_note)}.</p>` : ""}
      </div>
    </div></section>`;
}
function declaredBlock(p) {
  if (!p.declared) return "";
  const d = p.declared;
  const hotBill = d.bill_now > 1.6 * d.bill, hotMonth = d.monthly_now > 1.8 * d.monthly;
  return `<section class="card"><h2>Declared vs actual</h2><p class="sub">What the shop told the payment provider at onboarding, next to what its payments show.</p>
    <div class="declared">
      <div class="dv"><h4>Average bill</h4><div class="three"><div><span>Declared</span><b>${inr(d.bill)}</b></div><div><span>Normal weeks</span><b>${inr(d.bill_normal)}</b></div><div><span>Now</span><b class="${hotBill ? "hot" : ""}">${inr(d.bill_now)}</b></div></div></div>
      <div class="dv"><h4>Sales in 30 days</h4><div class="three"><div><span>Declared</span><b>${inr(d.monthly)}</b></div><div><span>Normal weeks</span><b>${inr(d.monthly_normal)}</b></div><div><span>Last 30 days</span><b class="${hotMonth ? "hot" : ""}">${inr(d.monthly_now)}</b></div></div></div>
    </div></section>`;
}
function testsBlock(p) {
  const card = t => {
    const c = t.passed === null ? "var(--faint)" : t.passed ? "var(--good)" : "var(--bad)";
    const lab = t.passed === null ? "No data" : t.passed ? "Passes" : "Flags";
    return `<div class="test" style="--tc:${c}"><div class="top"><h4>${esc(t.name)}</h4><span class="chip ${t.passed === null ? "" : t.passed ? "ok" : "bad"}">${lab}</span></div><div class="q">${esc(t.question)}</div><p>${esc(t.text)}</p></div>`;
  };
  return `<section class="card"><h2>Three tests</h2><p class="sub">A shop moves up the ladder only when its own history, its peers and the context all point the same way.</p>
    <div class="tests">${p.tests.map(card).join("")}</div></section>`;
}
function traitsBlock(p) {
  const verdict = s => ({ unusual: `<span class="chip bad">Unusual</span>`, explained: `<span class="chip warn">Changed, explained</span>`,
    normal: `<span class="chip ok">Normal</span>`, grew: `<span class="chip info">Grew, not a concern alone</span>` }[s]);
  const rows = p.traits.map(t => `<tr><td><div class="tl">${esc(t.label)}</div><div class="ts">${esc(t.sentence)}</div></td>
    <td class="v">${esc(t.normal)}</td><td class="v">${esc(t.now)}</td><td class="v">${esc(t.peers)}</td><td>${verdict(t.status)}<div class="unit">${esc(t.unit)}</div></td></tr>`).join("");
  return `<section class="card"><h2>Fingerprint check</h2><p class="sub">The six habits behind the shape. Peers means the typical ${esc(p.noun.replace(/ies$/, "y").replace(/s$/, ""))} in ${esc(p.city)} over the same 7 days.</p>
    <div class="scroll" style="margin-top:12px"><table class="ttable"><thead><tr><th>Habit</th><th>Normal</th><th>Now</th><th>Peers</th><th>Verdict</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
}
function evidenceBlock(p) {
  const hrs = Array.from({ length: 24 }, (_, h) => h % 6 === 0 ? (h === 0 ? "12 AM" : h === 12 ? "12 PM" : h < 12 ? `${h} AM` : `${h - 12} PM`) : "");
  const key = `<div class="ckey"><span><i style="background:var(--typical);opacity:.6;height:9px;width:10px"></i>Normal weeks</span><span><i style="background:var(--accent);height:9px;width:10px"></i>Last 7 days</span></div>`;
  const rows = (p.payments || []).map(x => `<tr><td>${esc(x.time)}</td><td class="r">${inr(x.amount)}</td><td class="${x.state && x.state !== p.home ? "far" : ""}">${esc(x.state || "–")}</td><td>${esc(x.mode)}</td><td class="muted">…${esc(x.payer)}</td></tr>`).join("");
  return `<div class="grid2">
    <section class="card"><h2>When customers pay</h2><p class="sub">Share of payments by hour of day.</p><div style="margin-top:10px">${bars(p.evidence.hours_normal, p.evidence.hours_now, hrs, "Payments by hour")}</div>${key}</section>
    <section class="card"><h2>What customers pay</h2><p class="sub">Share of payments by amount band, starting at the value shown.</p><div style="margin-top:10px">${bars(p.evidence.amounts_normal, p.evidence.amounts_now, p.evidence.amount_labels, "Payments by amount")}</div>${key}</section>
  </div>
  ${rows ? `<section class="card"><h2>Raw payments</h2><p class="sub">The latest 20 payments on ${fmtDY(p.focus_day)}, straight from the transaction data. Payer states outside ${esc(p.home)} are marked.</p>
    <div class="scroll" style="margin-top:10px"><table class="ptable"><thead><tr><th>Time</th><th class="r" style="text-align:right">Amount</th><th>Payer state</th><th>Mode</th><th>Payer</th></tr></thead><tbody>${rows}</tbody></table></div></section>` : ""}`;
}
function ladderParts(p) {
  const reached = l => p.level_series.some(v => v >= l);
  const steps = META.levels.map((L, i) => `<div class="step ${i === p.level ? "on" : reached(i) && i < p.level ? "past" : ""}" style="--lc:${lc(i)}"><span class="n">${i}</span><div><b>${esc(L.label)}</b><span>${esc(L.meaning)}</span></div></div>`).join("");
  const log = (p.events || []).slice().reverse().map(e => {
    const c = e.type === "level" ? lc(e.level) : e.type === "ask" ? lc(2) : e.type === "noreply" ? "var(--bad)" : "var(--accent)";
    return `<li style="--lc:${c}"><time>${fmtDY(e.date)}</time>${esc(e.text)}</li>`;
  }).join("") || `<li><time>${fmtDY(p.today)}</time>No action taken. The merchant has never been contacted.</li>`;
  const v = p.volume_rule, fraud = p.answer && /front/.test(p.answer.kind);
  const vr = v.days
    ? `<span class="chip ${fraud ? "info" : "bad"}">Sales-limit rule</span><span>A rule that flags any shop selling 2× its normal would have flagged this shop on <b>${v.days} day${v.days > 1 ? "s" : ""}</b>, starting ${fmtD(v.first)}.${p.level <= 1 && !fraud && p.answer ? " TrueShape never touched its money." : ""}</span>`
    : `<span class="chip">Sales-limit rule</span><span>A rule that flags any shop selling 2× its normal would <b>never</b> have flagged this shop.${p.level >= 3 ? " TrueShape caught it from its shape." : ""}</span>`;
  return { steps, log, vr };
}
function phone(p) {
  const ck = p.checkin;
  let thread = "";
  if (ck) {
    thread += `<div class="msg sys">Hi ${esc(p.name)}, your payments this week look different from your usual pattern. Has something changed in your business? Pick one below. It takes 10 seconds and keeps your payouts on time.<small>Sent ${fmtD(ck.asked_on)}</small></div>`;
    if (ck.reply) thread += `<div class="msg me">${esc(ck.reply_label)}<small>${esc(p.name)}</small></div>`;
    thread += ck.check ? resultMsg(ck.check) : `<div class="msg res" style="--rc:var(--bad)">No answer yet. Payouts are delayed until the shop replies or the team reviews the account.</div>`;
  } else {
    thread += `<div class="msg sys">No check-in has been sent. ${esc(p.name)} has never been contacted.</div><div class="msg sys">Demo: pick an answer below to see how TrueShape would judge it.</div>`;
  }
  const opts = p.replies.map(k => `<button type="button" data-reason="${k}" aria-pressed="${ck && ck.reply === k}">${esc(META.replies[k])}</button>`).join("");
  return `<div class="phone"><div class="screen">
    <div class="top"><span class="av" aria-hidden="true">${esc(p.name[0])}</span><div><b>${esc(p.name)}</b><small>Merchant app, payments</small></div></div>
    <div class="thread" id="thread" aria-live="polite">${thread}</div>
    <div class="opts"><span class="lbl">${ck ? "Try a different answer" : "What changed?"}</span>${opts}</div></div></div>`;
}
function resultMsg(c) {
  const color = c.outcome === "continue" ? "var(--bad)" : "var(--good)";
  return `<div class="msg res ${reduced() ? "" : "pop"}" style="--rc:${color}">${esc(c.verdict)}${c.explained.length ? `<br><b>Explained:</b> ${esc(c.explained.join(", "))}` : ""}${c.unexplained.length ? `<br><b>Not explained:</b> ${esc(c.unexplained.join(", "))}` : ""}${c.level_label ? `<br><b>Next step:</b> ${esc(c.level_label)}` : ""}<small>Checked automatically against the payment pattern</small></div>`;
}
function wirePhone(p) {
  $$(".opts button").forEach(b => b.addEventListener("click", async () => {
    $$(".opts button").forEach(x => x.setAttribute("aria-pressed", x === b));
    const th = $("#thread"), keep = th.querySelector(".msg.sys")?.outerHTML || "";
    th.innerHTML = keep + `<div class="msg me">${esc(b.textContent)}<small>${esc(p.name)}</small></div><div class="msg sys">Checking…</div>`;
    try { th.lastElementChild.outerHTML = resultMsg(await api.post(`/api/merchants/${p.id}/reply`, { reason: b.dataset.reason })); }
    catch (e) { th.lastElementChild.outerHTML = `<div class="msg res" style="--rc:var(--bad)">${esc(e.message)}</div>`; }
  }));
}

function caseBody(p, opts = {}) {
  const { steps, log, vr } = ladderParts(p);
  const label = p.id === "SIM" ? "Simulated shop" : p.id === "UPLOAD" ? "Uploaded file" : `Case file ${p.id}`;
  return `
  <section class="card casehead">
    <div>
      <span class="kicker">${esc(label)}</span>
      <h1 style="margin-top:4px">${esc(p.name)}</h1>
      <div class="reg"><span>Registered as <b>${esc(p.category_label)}</b>, MCC ${p.mcc}</span><span>${esc(p.area)}${p.city ? ", " + esc(p.city) : ""}</span><span>${p.payments_today} payments, ${inr(p.sales_today)} on ${fmtD(p.today)}</span></div>
      <div class="state">${pill(p.level, true)}<span class="meaning">${esc(META.levels[p.level].meaning)}</span></div>
      ${p.answer && !opts.noKey ? `<div class="reveal"><button class="btn" id="reveal" type="button">Reveal what this shop really is</button><div class="answer" id="answer" hidden><b>Answer key:</b> ${esc(p.answer.label)}${p.answer.change_date ? `, from ${fmtD(p.answer.change_date)}` : ""}. ${esc(p.answer.note)}</div></div>` : ""}
    </div>
    ${gauge(p.score, p.level)}
  </section>
  ${shapeBlock(p)}
  ${declaredBlock(p)}
  <section class="card"><h2>Volume can change. Shape shouldn't.</h2><p class="sub">Top: weekly sales against this shop's normal. Bottom: the mismatch score, coloured by the action taken. Ticks along the bottom are cricket match days. Hover for details.</p>
    <div class="chartwrap" id="tl" style="margin-top:12px"></div>
    <div class="ckey"><span><i style="background:var(--accent)"></i>This shop's sales</span>${p.peer_vol_series ? `<span><i style="background:var(--typical)"></i>Typical ${esc(p.noun.replace(/ies$/, "y").replace(/s$/, ""))} in ${esc(p.city)}</span>` : ""}<span><i style="background:var(--bad);height:2px"></i>Sales-limit rule (2×)</span><span><i style="background:var(--festival);height:10px;outline:1px solid var(--warn)"></i>Festival</span><span><i style="background:var(--l2);width:10px;height:10px;border-radius:50%"></i>Check-in sent</span></div>
  </section>
  ${testsBlock(p)}
  ${traitsBlock(p)}
  ${evidenceBlock(p)}
  <section class="card"><div class="act">
    <div><h2>Proportionate response</h2><p class="sub">Small doubts get small steps. Money is touched only when several habits disagree with the registered business.</p>
      <div class="ladder">${steps}</div><div class="vrule">${vr}</div></div>
    <div>${opts.noPhone ? `<h2>Case log</h2>` : `<h2 style="margin-bottom:12px">What the merchant sees</h2>${phone(p)}<h2 style="margin-top:22px">Case log</h2>`}<ul class="log">${log}</ul></div>
  </div></section>`;
}
function wireCase(root, p) {
  timeline(p, $("#tl", root));
  const rv = $("#reveal", root);
  if (rv) rv.addEventListener("click", () => { $("#answer", root).hidden = false; rv.hidden = true; });
  if ($("#thread", root)) wirePhone(p);
}

// ------------------------------------------------------------------ page: overview
function seg(id, items, current, label) {
  return `<div class="seg" role="group" aria-label="${esc(label)}" id="${id}">${items.map(([k, t]) => `<button type="button" data-k="${k}" aria-pressed="${k === current}">${esc(t)}</button>`).join("")}</div>`;
}
function wireSeg(root, id, fn) {
  $$(`#${id} button`, root).forEach(b => b.addEventListener("click", () => {
    $$(`#${id} button`, root).forEach(x => x.setAttribute("aria-pressed", x === b)); fn(b.dataset.k);
  }));
}
async function pageOverview(root) {
  OVERVIEW = OVERVIEW || await api.get("/api/overview");
  root.innerHTML = `
  <div class="filters">
    ${seg("fcity", [["all", "Both cities"], ["Hyderabad", "Hyderabad"], ["Mumbai", "Mumbai"]], state.city, "City")}
    ${seg("fcat", [["all", "All shops"], ...META.categories.map(c => [c.key, c.short === "Mobile shop" ? "Mobile shops" : c.short === "Kirana" ? "Kiranas" : "Bakeries"])], state.cat, "Category")}
  </div>
  <div class="hero" id="hero"></div>
  <section class="card">
    <div class="row between">
      <div><h2>Shops</h2><p class="sub">Each shop is drawn as its own shape: dashed is its normal, filled is now. Click a shop to open its case file.</p></div>
      <div class="row">
        ${seg("flist", [["action", "Needs attention"], ["story", "Case studies"], ["all", "All"]], state.filter, "Which shops")}
        <input class="search" id="q" type="search" placeholder="Search name, area or ID" value="${esc(state.q)}" aria-label="Search shops">
        <label class="small muted row" style="gap:6px"><input type="checkbox" id="key" ${state.key ? "checked" : ""}> Show answer key</label>
      </div>
    </div>
    <div class="mlist" id="mlist"></div><div class="more" id="more"></div>
  </section>`;
  const inScope = () => OVERVIEW.merchants.filter(m => (state.city === "all" || m.city === state.city) && (state.cat === "all" || m.category === state.cat));
  const drawHero = () => {
    const ms = inScope(), c = META.levels.map((_, i) => ms.filter(m => m.level === i).length), act = c[2] + c[3] + c[4] + c[5];
    const fronts = ms.filter(m => m.fraud), honest = ms.filter(m => !m.fraud);
    const s = { ours: [fronts.filter(m => m.ours).length, honest.filter(m => m.ours).length, honest.filter(m => m.asked && !m.ours).length],
      vol: [fronts.filter(m => m.vol).length, honest.filter(m => m.vol).length] };
    const where = state.city === "all" ? "Hyderabad and Mumbai" : state.city;
    const what = state.cat === "all" ? "shops" : CAT()[state.cat].noun;
    const dots = f => ms.map(m => `<i class="dot ${m.fraud ? (m[f] ? "front" : "front missed") : m[f] ? "hurt" : (f === "ours" && m.asked ? "asked" : "")}" title="${esc(m.name)}"></i>`).join("");
    $("#hero").innerHTML = `
      <section class="card">
        <span class="kicker">Today, ${fmtDY(OVERVIEW.today)}, ${esc(where)}</span>
        <h1 class="headline">${ms.length} ${esc(what)} checked. ${act} need action.</h1>
        <p class="tagline">Volume can change. Shape shouldn't.</p>
        <p class="muted">TrueShape learns how each shop normally takes payments, compares it with similar shops in the same city, and flags the ones that stop looking like the business they registered as. Shops that simply grow are left alone.</p>
        <div class="statusbar" aria-hidden="true">${c.map((k, i) => k ? `<i style="width:${k / ms.length * 100}%;background:${lc(i)}"></i>` : "").join("")}</div>
        <div class="legend6">${c.map((k, i) => `<div style="--lc:${lc(i)}"><b>${k}</b><span>${esc(META.levels[i].label)}</span></div>`).join("")}</div>
      </section>
      <section class="card">
        <span class="kicker">Test on 126 days of simulated payments</span>
        <h2>Same ${ms.length} shops, two ways of checking</h2>
        <div class="compare">
          <div class="method ours"><h4>TrueShape</h4><p class="rule">Shape against own normal, peers and context</p><div class="dots">${dots("ours")}</div>
            <div class="stats"><div class="stat good"><b>${s.ours[0]} of ${fronts.length}</b><span>betting fronts stopped</span></div><div class="stat good"><b>${s.ours[1]}</b><span>honest shops disrupted</span></div></div></div>
          <div class="method"><h4>Sales-limit rule</h4><p class="rule">Flag when weekly sales reach 2× normal</p><div class="dots">${dots("vol")}</div>
            <div class="stats"><div class="stat"><b>${s.vol[0]} of ${fronts.length}</b><span>betting fronts flagged</span></div><div class="stat bad"><b>${s.vol[1]}</b><span>honest shops disrupted</span></div></div></div>
        </div>
        <div class="dotkey"><span><i class="dot front"></i>Betting front, stopped</span><span><i class="dot front missed"></i>Front, on watch only</span><span><i class="dot hurt"></i>Honest shop, payouts hit</span><span><i class="dot asked"></i>Honest shop, asked once</span><span><i class="dot"></i>Honest shop, left alone</span></div>
      </section>`;
  };
  const drawList = () => {
    let ms = inScope();
    if (state.filter === "action") ms = ms.filter(m => m.level >= 1);
    if (state.filter === "story") ms = ms.filter(m => m.story);
    if (state.q) { const q = state.q.toLowerCase(); ms = ms.filter(m => `${m.name} ${m.area} ${m.id}`.toLowerCase().includes(q)); }
    ms.sort((a, b) => b.level - a.level || b.score - a.score || a.name.localeCompare(b.name));
    const shown = state.showAll ? ms : ms.slice(0, 40);
    $("#mlist").innerHTML = shown.map(m => `<button type="button" class="mrow" data-id="${m.id}">
      ${glyph(m.glyph, m.level)}
      <span style="min-width:0"><div class="nm">${esc(m.name)}</div><div class="ar">${catTag(m.category)}<span>${esc(m.area)}, ${esc(m.city)}</span><span>${m.id}</span>${state.key ? `<span class="key">${esc(m.kind_label)}</span>` : ""}<span class="pill-inline">${pill(m.level)}</span></div></span>
      <span class="pillcol">${pill(m.level)}</span>
      <span class="why">${m.flags.map(f => `<span class="chip bad">${esc(f)}</span>`).join("") || (m.vol_ratio >= 1.6 ? `<span class="chip info">Sales ${m.vol_ratio.toFixed(1)}×, shape normal</span>` : `<span class="chip">Shape normal</span>`)}</span>
      <span class="sc" title="Mismatch score">${m.score}</span><span class="go" aria-hidden="true">›</span></button>`).join("") || `<p class="muted" style="padding:16px 4px">No shops match these filters.</p>`;
    $("#more").innerHTML = ms.length > 40 && !state.showAll ? `<button class="btn" type="button" id="showall">Show all ${ms.length} shops</button>` : "";
    const sa = $("#showall"); if (sa) sa.addEventListener("click", () => { state.showAll = true; drawList(); });
  };
  drawHero(); drawList();
  wireSeg(root, "fcity", k => { state.city = k; state.showAll = false; drawHero(); drawList(); });
  wireSeg(root, "fcat", k => { state.cat = k; state.showAll = false; drawHero(); drawList(); });
  wireSeg(root, "flist", k => { state.filter = k; state.showAll = false; drawList(); });
  $("#q").addEventListener("input", e => { state.q = e.target.value; drawList(); });
  $("#key").addEventListener("change", e => { state.key = e.target.checked; drawList(); });
  $("#mlist").addEventListener("click", e => { const b = e.target.closest(".mrow"); if (b) location.hash = `case-${b.dataset.id}`; });
}

// ------------------------------------------------------------------ page: category shapes
async function pageShapes(root) {
  PROFILES = PROFILES || await api.get("/api/profiles");
  const P = PROFILES;
  const hourName = h => h === 0 ? "12 AM" : h === 12 ? "12 PM" : h < 12 ? `${h} AM` : `${h - 12} PM`;
  const cards = P.categories.map(c => {
    const f = c.facts;
    return `<section class="card shapecard">
      <h3 style="--cc:var(--c-${c.key})"><i></i>${esc(c.label)}</h3><p class="small muted">MCC ${c.mcc}. Median of all ${esc(c.noun)} in their first 45 days.</p>
      ${radar({ now: c.radar }, `var(--c-${c.key})`, { small: true, label: `Typical shape of a ${c.label}` })}
      <dl class="facts">
        <div><dt>Average bill</dt><dd>${inr(f.bill)}</dd></div>
        <div><dt>Payments a day</dt><dd>${f.per_day}</dd></div>
        <div><dt>Returning customers</dt><dd>${pct(f.repeat)}</dd></div>
        <div><dt>Payments of ${inr(f.big_level)}+</dt><dd>${pct(f.big)}</dd></div>
        <div><dt>Busiest hours</dt><dd>${f.busiest.map(hourName).join(", ")}</dd></div>
        <div><dt>Money pulled out in 1 hour</dt><dd>${pct(f.cashout)}</dd></div>
      </dl></section>`;
  }).join("");
  root.innerHTML = `
  <section class="card"><h1 class="headline">Every business has its own normal.</h1>
    <p class="sub" style="margin-top:10px">Nobody wrote rules for bakeries, kiranas or mobile shops. TrueShape measures each category's normal shape from the data, then compares every shop only with shops like it in the same city. The same six habits and the same steps work for any business.</p></section>
  <div class="grid3">${cards}</div>
  <section class="card">
    <div class="row between"><div><h2>Festivals lift everyone, so nobody is flagged</h2>
      <p class="sub">Typical weekly sales against normal, by category. Shaded bands are festivals. Because each shop is compared with its own group in the same week, a festival rush cancels out.</p></div>
      ${seg("fescity", [["Hyderabad", "Hyderabad"], ["Mumbai", "Mumbai"]], state.fcity, "City")}</div>
    <div class="chartwrap" id="fes" style="margin-top:12px"></div>
    <div class="ckey">${P.categories.map(c => `<span><i style="background:var(--c-${c.key})"></i>${esc(c.label)}</span>`).join("")}<span><i style="background:var(--festival);height:10px;outline:1px solid var(--warn)"></i>Festival</span></div>
    <p style="margin-top:14px"><b>${P.festival_touched} of ${P.honest}</b> honest shops had their money touched on any festival day.</p>
  </section>`;
  const drawFest = () => {
    const dates = META.dates, n = dates.length, W = 760, H = 250, L = 40, R = 104, T = 14, B = 26;
    const series = P.categories.map(c => ({ c, v: P.lines[`${c.key}|${state.fcity}`] }));
    const vmax = Math.max(2, ...series.flatMap(s => s.v)) * 1.08;
    const x = i => L + i / (n - 1) * (W - L - R), y = v => H - B - (v / vmax) * (H - B - T);
    let g = "", run = null, lastLab = -1;
    for (let i = 0; i <= n; i++) {
      const f = i < n ? META.festival[i] : "";
      if (f && run === null) run = i;
      if (run !== null && (!f || f !== META.festival[run])) {
        g += `<rect x="${x(run) - 2}" y="${T}" width="${x(i - 1) - x(run) + 4}" height="${H - B - T}" fill="var(--festival)"/>`;
        if (META.festival[run] !== "Navratri") { const lx = x(run) + 3, ly = H - B - 8 - (lx < lastLab ? 13 : 0); g += `<text x="${lx}" y="${ly}" font-size="10.5" font-weight="600" fill="var(--warn)">${esc(META.festival[run])}</text>`; lastLab = lx + META.festival[run].length * 6; }
        run = f ? i : null;
      }
    }
    for (let v = 0; v <= vmax; v += 0.5) g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" opacity="${v % 1 ? .5 : 1}"/>${v % 1 ? "" : `<text x="${L - 6}" y="${y(v) + 3.5}" text-anchor="end" font-size="10" fill="var(--faint)">${v}×</text>`}`;
    const ends = [];
    series.forEach(s => {
      g += `<path d="${s.v.slice(6).map((v, j) => `${j ? "L" : "M"}${x(j + 6).toFixed(1)},${y(v).toFixed(1)}`).join("")}" fill="none" stroke="var(--c-${s.c.key})" stroke-width="2"/>`;
      ends.push({ y: y(s.v[n - 1]), t: `${s.c.label.split(" ")[0]} ${s.v[n - 1].toFixed(1)}×`, k: s.c.key });
    });
    ends.sort((a, b) => a.y - b.y); for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 13) ends[i].y = ends[i - 1].y + 13;
    ends.forEach(e => { g += `<text x="${W - R + 6}" y="${e.y + 4}" font-size="11" font-weight="600" fill="var(--ink)">${esc(e.t)}</text>`; });
    dates.forEach((d, i) => { if (d.endsWith("-01")) g += `<text x="${x(i)}" y="${H - 6}" text-anchor="middle" font-size="10.5" fill="var(--faint)">${fmtD(d)}</text>`; });
    g += `<line class="hov" y1="${T}" y2="${H - B}" stroke="var(--ink)" stroke-dasharray="3 3" opacity="0"/><rect x="${L}" y="0" width="${W - L - R}" height="${H}" fill="transparent"/>`;
    const host = $("#fes");
    host.innerHTML = svg(`0 0 ${W} ${H}`, g, "", `Typical weekly sales by category in ${state.fcity}`) + `<div class="tip" hidden></div>`;
    const el = host.querySelector("svg"), tip = host.querySelector(".tip"), hov = el.querySelector(".hov");
    el.addEventListener("mousemove", ev => {
      const r = el.getBoundingClientRect(), px = (ev.clientX - r.left) / r.width * W;
      const i = Math.max(0, Math.min(n - 1, Math.round((px - L) / (W - L - R) * (n - 1))));
      hov.setAttribute("x1", x(i)); hov.setAttribute("x2", x(i)); hov.setAttribute("opacity", ".5");
      tip.hidden = false; tip.style.left = `${x(i) / W * 100}%`; tip.style.top = `${T / H * 100 + 8}%`;
      tip.innerHTML = `<b>${fmtD(dates[i])}</b>${META.festival[i] ? ", " + esc(META.festival[i]) : ""}<br>${series.map(s => `${esc(s.c.label)}: ${s.v[i].toFixed(2)}×`).join("<br>")}`;
    });
    el.addEventListener("mouseleave", () => { tip.hidden = true; hov.setAttribute("opacity", "0"); });
  };
  drawFest();
  wireSeg(root, "fescity", k => { state.fcity = k; drawFest(); });
}

// ------------------------------------------------------------------ page: case
async function pageCase(root, id) {
  const p = await api.get(`/api/merchants/${id}`);
  root.innerHTML = `<div class="crumb"><a href="#overview">‹ All shops</a><span class="muted small">Data as of ${fmtDY(p.today)}</span></div>${caseBody(p)}`;
  wireCase(root, p);
}

// ------------------------------------------------------------------ page: try it live
function pageTry(root) {
  const scenarios = () => META.scenarios[state.tcat];
  if (!scenarios().some(s => s.key === state.tsc)) state.tsc = scenarios()[0].key;
  root.innerHTML = `
  <div class="try">
    <div class="stack">
      <section class="card stack"><div><h2>Run a live test</h2><p class="sub">Pick a shop and what happens to it. The backend generates four months of payments for a brand-new shop and runs the engine on it, exactly as it runs on real merchants.</p></div>
        <div class="field"><span>Category</span>${seg("tcat", META.categories.map(c => [c.key, c.label]), state.tcat, "Category")}</div>
        <div class="field"><span>City</span>${seg("tcity", META.cities.map(c => [c.key, c.key]), state.tcity, "City")}</div>
        <div class="field"><span>What happens</span><div class="scen" id="scen"></div></div>
        <div class="field"><span>The change starts on</span>${seg("tstart", META.starts.map(s => [s.key, s.label]), state.tstart, "Start date")}</div>
        <button class="btn primary" id="run" type="button">Generate payments and check</button>
        ${LIVE ? "" : `<p class="small muted">Demo version: each test is a pre-computed run. The full app generates a fresh shop every time.</p>`}
      </section>
      <section class="card stack"><div><h2>Check your own file</h2><p class="sub">Upload one shop's payments as a CSV with columns timestamp, amount_inr and payer_id (payer_state optional), covering at least four weeks.</p></div>
        <div class="row"><label class="field"><span>Category</span><select id="ucat">${META.categories.map(c => `<option value="${c.key}" ${c.key === state.ucat ? "selected" : ""}>${esc(c.label)}</option>`).join("")}</select></label>
          <label class="field"><span>City</span><select id="ucity">${META.cities.map(c => `<option ${c.key === state.ucity ? "selected" : ""}>${esc(c.key)}</option>`).join("")}</select></label></div>
        <label class="drop" id="drop"><input type="file" id="file" accept=".csv,text/csv" hidden ${LIVE ? "" : "disabled"}>
          <b>${LIVE ? "Drop a CSV here or click to choose" : "Available in the full app"}</b><span>${LIVE ? `Or try <a href="/api/sample.csv">the sample file</a> (Golden Crust Bakery, Hyderabad)` : "Run TrueShape on a laptop to upload files."}</span></label>
        <p class="err" id="uperr" hidden></p>
      </section>
    </div>
    <div id="result" class="stack"><section class="card"><p class="muted">Choose a shop on the left and press <b>Generate payments and check</b>.</p></section></div>
  </div>`;
  const drawScen = () => {
    $("#scen").innerHTML = scenarios().map(s => `<button type="button" data-s="${s.key}" aria-pressed="${state.tsc === s.key}"><span class="tagf" style="color:${s.fraud ? "var(--bad)" : "var(--good)"}">${s.fraud ? "Fraud" : "Honest change"}</span><b>${esc(s.label)}</b><span>${esc(s.blurb)}</span></button>`).join("");
    $$("#scen button").forEach(b => b.addEventListener("click", () => { state.tsc = b.dataset.s; $$("#scen button").forEach(x => x.setAttribute("aria-pressed", x === b)); }));
  };
  drawScen();
  wireSeg(root, "tcat", k => { state.tcat = k; if (!scenarios().some(s => s.key === state.tsc)) state.tsc = scenarios()[0].key; drawScen(); });
  wireSeg(root, "tcity", k => { state.tcity = k; });
  wireSeg(root, "tstart", k => { state.tstart = k; });
  const show = (p, head) => {
    const res = $("#result");
    res.innerHTML = head + caseBody(p, { noPhone: true, noKey: true });
    wireCase(res, p);
    res.scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "start" });
  };
  $("#run").addEventListener("click", async () => {
    const btn = $("#run"); btn.disabled = true; btn.textContent = "Generating payments…";
    try {
      const p = await api.post("/api/simulate", { category: state.tcat, city: state.tcity, scenario: state.tsc, start: state.tstart });
      const first = p.level_series.findIndex(v => v >= 3), d = META.dates;
      const startI = p.answer.change_date ? d.indexOf(p.answer.change_date) : -1;
      const verdict = p.fraud
        ? (first >= 0 ? `Caught. Payouts delayed on ${fmtD(d[first])}${startI >= 0 ? `, ${first - startI} days after the betting started` : ""}.` : "Not stopped yet. The shop is on quiet watch.")
        : (first >= 0 ? `Payouts were delayed on ${fmtD(d[first])}. This honest shop was disrupted.` : p.level_series.some(v => v >= 2) ? "Left alone after one quick question." : "Left alone. Never contacted.");
      show(p, `<section class="card"><span class="kicker">${p.payments_total.toLocaleString("en-IN")} payments generated for: ${esc(p.answer.label)}, ${esc(CAT()[p.category].label)}, ${esc(p.city)}</span>
        <p class="verdictline" style="margin-top:6px">${esc(verdict)}</p><p class="small muted" style="margin-top:4px">Sales-limit rule: ${p.volume_rule.days ? `flagged it on ${p.volume_rule.days} days` : "never flagged it"}.</p></section>`);
    } catch (e) { $("#result").innerHTML = `<section class="card"><p class="err">${esc(e.message)}</p></section>`; }
    btn.disabled = false; btn.textContent = "Generate payments and check";
  });
  $("#ucat").addEventListener("change", e => { state.ucat = e.target.value; });
  $("#ucity").addEventListener("change", e => { state.ucity = e.target.value; });
  if (LIVE) {
    const upload = async f => {
      const er = $("#uperr"); er.hidden = true;
      const fd = new FormData(); fd.append("file", f); fd.append("category", state.ucat); fd.append("city", state.ucity);
      try {
        const p = await api.post("/api/analyze", fd, true);
        show(p, `<section class="card"><span class="kicker">${p.rows.toLocaleString("en-IN")} payments read from ${esc(f.name)}</span>
          <p class="verdictline" style="margin-top:6px">${esc(META.levels[p.level].label)}, mismatch score ${p.score}</p>
          <p class="small muted" style="margin-top:4px">${p.peer_used ? `Compared with the ${p.peer_size} ${esc(p.noun)} in ${esc(p.city)}.` : "The dates differ from the peer group, so only the self test ran."}</p></section>`);
      } catch (e) { er.textContent = e.message; er.hidden = false; }
    };
    $("#file").addEventListener("change", e => e.target.files[0] && upload(e.target.files[0]));
    const d = $("#drop");
    ["dragenter", "dragover"].forEach(t => d.addEventListener(t, e => { e.preventDefault(); d.classList.add("over"); }));
    ["dragleave", "drop"].forEach(t => d.addEventListener(t, e => { e.preventDefault(); d.classList.remove("over"); }));
    d.addEventListener("drop", e => e.dataTransfer.files[0] && upload(e.dataTransfer.files[0]));
  }
}

// ------------------------------------------------------------------ page: results
async function pageResults(root) {
  RESULTS = RESULTS || await api.get("/api/results");
  const R = RESULTS, s = R.summary, t = s.trueshape;
  const daysOf = k => R.fronts.filter(f => f.kind === k && f.days !== null).map(f => f.days);
  const bold = daysOf("front"), careful = daysOf("disguised_front");
  const span = a => a.length ? (Math.min(...a) === Math.max(...a) ? `${a[0]}` : `${Math.min(...a)} to ${Math.max(...a)}`) : "–";
  const ruleRows = R.rules.map((r, i) => `<div class="rulebar"><div><h4>${esc(r.name)}</h4><p>${esc(r.note)}</p></div>
    <div class="bars">
      <div class="hbar"><span>Fronts stopped</span><span class="track"><i style="width:${r.caught / s.fronts * 100}%;background:${i === 0 ? "var(--accent)" : "var(--typical)"}"></i></span><b>${r.caught}/${s.fronts}</b></div>
      <div class="hbar"><span>Honest shops hit</span><span class="track"><i style="width:${Math.max(r.disrupted ? 1 : 0, r.disrupted / s.honest * 100)}%;background:var(--l3)"></i></span><b>${r.disrupted}/${s.honest}</b></div>
    </div></div>`).join("");
  const groups = R.groups.map(g => `<tr><td>${esc(g.city)}</td><td>${catTag(g.category)}</td><td class="r">${g.shops}</td><td class="r">${g.caught} of ${g.fronts}</td><td class="r">${g.disrupted}</td><td class="r">${g.asked}</td><td class="r">${g.vol_disrupted}</td></tr>`).join("");
  const hard = R.hard.map(h => `<tr><td><a href="#case-${h.example}">${esc(h.label.replace("Honest: ", "").replace(/^./, c => c.toUpperCase()))}</a></td><td class="r">${h.shops}</td><td class="r">${h.left_alone}</td><td class="r">${h.asked_cleared}</td><td class="r">${h.disrupted}</td><td class="r">${h.vol_hit}</td></tr>`).join("");
  const fronts = R.fronts.slice().sort((a, b) => (a.kind === "front" ? 0 : 1) - (b.kind === "front" ? 0 : 1) || (a.days ?? 99) - (b.days ?? 99)).map(f => `<tr><td><a href="#case-${f.id}">${esc(f.name)}</a></td><td>${catTag(f.category)}</td><td>${esc(f.city)}</td><td>${f.kind === "front" ? "Bold" : "Careful"}</td><td>${f.caught ? pill(Math.max(3, f.max_level)) : pill(f.max_level)}</td><td class="r">${f.days === null ? "–" : f.days + " days"}</td><td class="r">${f.vol_days}</td></tr>`).join("");
  root.innerHTML = `
  <section class="card"><h1 class="headline">${t.caught} of ${s.fronts} betting fronts stopped. ${t.disrupted} of ${s.honest} honest shops disrupted.</h1>
    <p class="sub" style="margin-top:10px">Tested on ${s.shops} simulated shops over 126 days, with an answer key the engine never sees. Bold fronts had their payouts delayed ${span(bold)} days after their first bet; careful ones took ${span(careful)} days. ${t.asked_only} honest shops with genuinely unusual changes were asked one question and cleared.</p></section>
  <section class="card"><h2>Against simpler rules</h2><p class="sub">Two common ways to watch merchants, run on the same shops. The plain sales rule also flags every festival rush; the smarter one compares with the group but misses careful fronts.</p>
    <div class="rules">${ruleRows}</div></section>
  <section class="card"><h2>By city and category</h2><p class="sub">It works the same way in every group, without any category-specific rules.</p>
    <div class="scroll" style="margin-top:12px"><table class="gtable"><thead><tr><th>City</th><th>Category</th><th class="r">Shops</th><th class="r">Fronts stopped</th><th class="r">Honest disrupted</th><th class="r">Asked once, cleared</th><th class="r">Sales rule: honest hit</th></tr></thead><tbody>${groups}</tbody></table></div></section>
  <section class="card"><h2>The hardest honest shops</h2><p class="sub">Shops whose business really changed, built to look suspicious. Click a type to open an example.</p>
    <div class="scroll" style="margin-top:12px"><table class="htable"><thead><tr><th>Change</th><th class="r">Shops</th><th class="r">Never contacted</th><th class="r">Asked once, cleared</th><th class="r">Payouts hit</th><th class="r">Sales rule hit</th></tr></thead><tbody>${hard}</tbody></table></div></section>
  <section class="card"><h2>Every betting front</h2><p class="sub">Days to act counts from the first bet to the day payouts were delayed.</p>
    <div class="scroll" style="margin-top:12px"><table class="gtable"><thead><tr><th>Shop</th><th>Category</th><th>City</th><th>Type</th><th>Highest step</th><th class="r">Days to act</th><th class="r">Sales rule days</th></tr></thead><tbody>${fronts}</tbody></table></div></section>
  <section class="card"><h2>Limits</h2>
    <ul class="limits">
      <li>${R.missed.length} careful fronts were not stopped. All of them started late (${R.missed.map(m => fmtD(m.start)).join(", ")}) and stayed small after the cricket season ended. They sit on Watch, so they are monitored, not missed entirely.</li>
      <li>Careful fronts take two to three weeks to surface. Linking shops that share the same payers would catch networks sooner.</li>
      <li>The data is simulated. The thresholds (25, 40, 55, 70) would be tuned on real data by running TrueShape silently next to existing checks first.</li>
      <li>Payer location is not always known for in-store UPI. Without it, Who pays relies on returning customers, which is always known.</li>
    </ul></section>`;
}

// ------------------------------------------------------------------ page: how it works
function pageHow(root) {
  root.innerHTML = `
  <section class="card"><h1 class="headline">Every business has a shape. Fraud changes it.</h1>
    <p class="sub" style="margin-top:10px">A betting front can register with genuine documents, and each ₹500 payment looks harmless. What it cannot hide is that, taken together, its payments stop looking like the business it registered as: wrong amounts, wrong hours, wrong customers, money leaving too fast, and sales that follow cricket instead of festivals.</p></section>
  <section class="card"><h2>Five steps, every day, for every shop</h2>
    <div class="pipe">
      <div class="pstep"><span class="ix">1</span><h4>Collect</h4><p>Payments, payers and settlements the payment provider already records. Nothing new is asked of the merchant.</p></div>
      <div class="pstep"><span class="ix">2</span><h4>Fingerprint</h4><p>Summarise the last 7 days as six habits: payment sizes, shop hours, who pays, where the money goes, what drives sales, and volume.</p></div>
      <div class="pstep"><span class="ix">3</span><h4>Three tests</h4><p>Self: against its own first 45 days. Peers: against the same category in the same city that week. Context: against the calendar and the merchant's answer.</p></div>
      <div class="pstep"><span class="ix">4</span><h4>Score</h4><p>Unexplained changes become a 0 to 100 mismatch score. With fewer than two odd habits, a shop can never go past Watch.</p></div>
      <div class="pstep"><span class="ix">5</span><h4>Respond</h4><p>Watch, ask, delay, hold, suspend and report. A fitting answer moves the shop to the trusted lane.</p></div>
    </div></section>
  <section class="card"><h2>What data it uses</h2><p class="sub">All of it is already held by a payment aggregator. The prototype uses simulated data with the same columns.</p>
    <div class="scroll" style="margin-top:12px"><table class="dtable"><thead><tr><th>Data</th><th>Where it comes from</th><th>What it reveals</th></tr></thead><tbody>
      <tr><td>Declared business</td><td>Onboarding form and KYC: category code, city, expected bill and monthly sales</td><td>Which peer group to compare with, and what the shop promised</td></tr>
      <tr><td>Payment time and amount</td><td>Every transaction processed</td><td>Shop hours, payment sizes, round amounts</td></tr>
      <tr><td>Payer ID</td><td>Masked UPI handle or card token</td><td>Returning locals or one-time payers</td></tr>
      <tr><td>Payer location</td><td>Card issuer, IP or device data, where available</td><td>Local customers or payers from across India</td></tr>
      <tr><td>Settlements</td><td>The provider's own payout and instant-settlement records</td><td>Money staying in the business or pulled out at once</td></tr>
      <tr><td>Event calendar</td><td>Public festival and cricket schedules</td><td>Sales that follow festivals or matches</td></tr>
      <tr><td>Merchant's answer</td><td>The two-tap "What changed?" check-in</td><td>A genuine reason, or one that does not fit the evidence</td></tr>
    </tbody></table></div></section>
  <section class="card"><h2>Guardrails for honest merchants</h2>
    <ul class="guard">
      <li><b>Volume is never enough</b>Selling more is shown, but cannot move a shop past Watch on its own.</li>
      <li><b>Two habits must agree</b>One odd habit keeps a shop at Watch. Money is touched only when several drift together.</li>
      <li><b>Compare with the right herd</b>A Mumbai kirana is compared with Mumbai kiranas. If they all spike at Ganesh Chaturthi, nobody is flagged.</li>
      <li><b>Ask before acting</b>A 10-second check-in comes before any delay. A fitting answer clears the shop and becomes its new normal.</li>
      <li><b>Step by step</b>Delay before hold, hold before suspend. Levels come down one step at a time.</li>
      <li><b>People decide the big steps</b>Holds and suspensions go to an analyst with the evidence already written up.</li>
    </ul></section>
  <section class="card"><h2>How it is built</h2><p class="sub">A transparent comparison engine: plain statistics and stated rules, no machine learning and no fraud labels needed. Every decision comes with a sentence that explains it.</p>
    <div class="arch">
      <div><b>Screens</b>This app: HTML, CSS and JavaScript, with hand-drawn SVG charts.</div>
      <div><b>API</b>Python FastAPI: overview, case files, merchant replies, results, live simulation, file upload.</div>
      <div><b>Engine</b>Python, pandas and NumPy: fingerprint, three tests, score and response ladder.</div>
      <div><b>Data</b>Simulated: 168 shops, about 16.6 lakh payments over 126 days. In production: the provider's transaction stream.</div>
    </div></section>`;
}

// ------------------------------------------------------------------ router
const ROUTES = { overview: pageOverview, shapes: pageShapes, try: pageTry, results: pageResults, how: pageHow };
async function route() {
  const h = (location.hash || "#overview").slice(1), root = $("#view");
  $$(".tabs a").forEach(a => a.setAttribute("aria-current", a.dataset.r === h || (h.startsWith("case-") && a.dataset.r === "overview") ? "page" : "false"));
  root.innerHTML = `<p class="loading">Loading…</p>`;
  try {
    META = META || await api.get("/api/meta");
    if (h.startsWith("case-")) await pageCase(root, h.slice(5));
    else await (ROUTES[h] || pageOverview)(root);
  } catch (e) {
    root.innerHTML = `<section class="card"><h2>This page could not load</h2><p class="err" style="margin-top:8px">${esc(e.message)}</p><p class="muted small" style="margin-top:8px">If you are running the full app, check that the window running python run.py is still open.</p></section>`;
  }
  window.scrollTo(0, 0);
}
document.addEventListener("DOMContentLoaded", () => {
  const m = $("#mode");
  if (m) { m.className = LIVE ? "mode" : "mode demo"; m.innerHTML = `<i></i>${LIVE ? "Live, connected to the engine" : "Demo with pre-computed data"}`; }
  addEventListener("hashchange", route);
  route();
});
