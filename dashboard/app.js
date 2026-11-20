/* Studio dashboard. Live data from /api/state every 4 s. Colour = meaning only. */
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// 18 Nov: held videos belong to the healer (engine/healer.py); say what it is doing, in plain words
const HEAL_STEP = { replan: "making a new plan the owner agent asked for", known: "applying a fix it learned before", rebuild: "rebuilding with the newer code", simplify: "re-planned the failing scenes, rebuilding",
  code: "trying a code fix (checked before it goes live)", resume: "finishing the interrupted build" };
const healerLine = (j) => { const h = j.healer || {}; if (h.state === "parked") return "Healer parked it: " + (h.why || "every step tried") + ".";
  if (h.state === "fixed") return "Healer fixed it."; if (h.step) return "Healer: " + (HEAL_STEP[h.step] || h.step) + (h.result ? " (last: " + h.result + ")" : "") + ".";
  return "The healer picks it up on its next run (every 15 min)."; };
const K = { green: "var(--green)", amber: "var(--amber)", red: "var(--red)", blue: "var(--blue)", violet: "var(--violet)", teal: "var(--teal)", gray: "var(--gray)" };
const ST = {
  building: ["Building", K.blue, 1], prepped: ["Prepped", K.blue], waiting: ["Needs approval", K.violet], ready: ["Ready, not sent", K.violet],
  approved: ["Approved", K.teal], posted: ["Posted", K.green], held: ["Held", K.amber], on_hold: ["On hold", K.gray], queued: ["Queued", K.teal], rejected: ["Rejected", K.red], removed: ["Removed", K.gray], superseded: ["Replaced", K.gray], paused: ["Stopped midway", K.gray], made: ["Made", K.gray], cancelled: ["Cancelled", K.gray],
};
const LV = { ok: K.green, warn: K.amber, bad: K.red, info: K.gray, run: K.blue, wait: K.violet };
const P = {
  today: '<path d="M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z"/>', runs: '<path d="M4 6h16M4 12h10M4 18h6"/>', approve: '<path d="M20 6 9 17l-5-5"/>',
  channels: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  server: '<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/><path d="M7 7.5h.01M7 16.5h.01"/>',
  sources: '<path d="M9 7H6a3 3 0 0 0 0 6h3M15 7h3a3 3 0 0 1 0 6h-3M8 10h8"/>', activity: '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
  brain: '<circle cx="12" cy="12" r="2"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="18" r="2"/><path d="M6.5 7.5l4 3M17.5 7.5l-4 3M7.5 17.5l3-4M16.5 16.5l-3-3"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>', play: '<path d="m7 4 13 8-13 8z"/>', spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4M21 4v5h-5"/>',
};
const ic = (n) => `<svg viewBox="0 0 24 24">${P[n] || ""}</svg>`;
const NAV = [
  ["", [["today", "Today"], ["published", "Published"], ["runs", "Runs"], ["approvals", "Approvals"]]],
  ["Channels", [["channels", "All channels"]]],
  ["System", [["server", "Server"], ["sources", "Connected apps"], ["activity", "Activity log"]]],
  ["Knowledge", [["brain", "Brain"], ["radar", "Radar"]]],
  ["", [["settings", "Settings"]]],
];
const ICON = { published: "approve", radar: "spark", today: "today", runs: "runs", approvals: "approve", channels: "channels", server: "server", sources: "sources", activity: "activity", brain: "brain", settings: "settings" };
let S = null, prev = "", runFilter = "all", runCh = "all", logQ = "", logLvl = "all", fails = 0, srcCache = null, briefCache = null, drawerKey = null;

/* ---------- format ---------- */
const nf = (x) => (x == null ? "—" : x >= 1e5 ? (x / 1e5).toFixed(1).replace(".0", "") + "L" : x >= 1e4 ? (x / 1000).toFixed(1).replace(".0", "") + "k" : Number(x).toLocaleString("en-IN"));
const now = () => (S ? S.now : Date.now() / 1000);
const ago = (t) => { if (!t) return "—"; const d = Math.max(0, now() - t); return d < 60 ? "just now" : d < 3600 ? `${(d / 60) | 0} min ago` : d < 86400 ? `${(d / 3600) | 0} h ago` : `${(d / 86400) | 0} d ago`; };
const dur = (s) => (s == null ? "—" : s < 60 ? `${s | 0}s` : s < 3600 ? `${(s / 60) | 0}m ${String(s % 60 | 0).padStart(2, "0")}s` : s < 86400 ? `${(s / 3600) | 0}h ${String(((s % 3600) / 60) | 0).padStart(2, "0")}m` : `${(s / 86400) | 0}d ${(s % 86400 / 3600) | 0}h`);
const inT = (s) => (s == null ? "—" : s <= 0 ? "now" : s < 3600 ? `in ${Math.ceil(s / 60)} min` : `in ${(s / 3600) | 0} h ${((s % 3600) / 60) | 0} m`);
const ch = (id) => (S?.channels || []).find((c) => c.id === id) || { name: id, color: "#737373" };
// 19 Nov: the page's real profile picture (server job engine/brand.py keeps ~/studio-out/dp/<id>.jpg fresh); colour dot if none
const dp = (c, s = 22, x = "") => `<span class="dp" style="--c:${c.color};width:${s}px;height:${s}px;background-image:url(/dp/${c.id}.jpg)${x}" title="${esc(c.name)}"></span>`;
const badge = (k, j) => { let [t, c, run] = ST[k] || [k, K.gray]; if (k === "held" && j) t = j.held_state === "waiting" ? "Held · waits for a fix" : "Held · being rebuilt"; return `<span class="badge ${run ? "run" : ""}" style="--c:${c}"><i class="dot"></i>${t}</span>`; };
const lvlBadge = (l, t) => `<span class="badge" style="--c:${LV[l] || K.gray}"><i class="dot"></i>${esc(t)}</span>`;
const meter = (p, c) => `<div class="meter" style="--c:${c}"><i style="width:${Math.max(2, Math.min(100, p))}%"></i></div>`;
const thr = (v, w, b) => (v >= b ? K.red : v >= w ? K.amber : K.green);
const seg = (j) => `<div class="seg">${j.steps.map((s) => `<i class="${s.done ? "d" : s.active ? "a" : ""}" title="${esc(s.label)}"></i>`).join("")}</div>`;
function qualityChart(q) {
  const mx = Math.max(1, ...q.days.map((d) => d.videos));
  const bars = q.days.map((d) => { const h = (d.videos / mx) * 70, hp = (d.passed / mx) * 70;
    return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px"><div class="num" style="font-size:12px;font-weight:600">${d.rate == null ? "" : d.rate + "%"}</div>
    <div style="height:72px;width:70%;display:flex;flex-direction:column;justify-content:flex-end"><div style="height:${h - hp}px;background:color-mix(in srgb,var(--amber) 35%,transparent);border-radius:3px 3px 0 0"></div><div style="height:${hp}px;background:var(--green);border-radius:${h > hp ? 0 : 3}px ${h > hp ? 0 : 3}px 0 0"></div></div>
    <div class="faint" style="font-size:11px">${d.day.slice(8)}</div></div>`; }).join("");
  const rs = q.reasons.map(([r, n]) => `<div class="row" style="padding:6px 0"><span class="grow" style="font-size:12.5px">${esc(r)}</span><span class="num mut">${n}×</span></div>`).join("");
  return `<div style="display:flex;gap:6px;align-items:flex-end">${bars}</div>
  <div class="mut" style="font-size:12px;margin-top:6px"><span class="dot" style="--c:var(--green)"></span> passed first try &nbsp; <span class="dot" style="--c:var(--amber)"></span> held, then fixed or rebuilt · ${q.avg_reviews} reviews per video on average</div>
  ${rs ? `<div style="margin-top:10px;font-weight:500;font-size:12.5px">Most common reasons for a hold</div>${rs}` : ""}`;
}
function cpuSplit(s) {
  const n = Math.round(s.cpu_norm || 0), b = Math.round(s.cpu_bg || 0), f = Math.max(0, 100 - n - b);
  return `<div style="display:flex;justify-content:space-between;font-size:12.5px"><span class="mut">CPU</span><span class="num">${n + b}%</span></div>
  <div style="display:flex;height:8px;border-radius:99px;overflow:hidden;margin-top:5px;background:var(--sub);border:1px solid var(--line)">
   <i style="width:${n}%;background:${n >= 85 ? "var(--red)" : n >= 60 ? "var(--amber)" : "var(--blue)"}"></i><i style="width:${b}%;background:color-mix(in srgb,var(--gray) 45%,transparent)"></i></div>
  <div style="display:flex;gap:12px;font-size:12px;margin-top:5px" class="mut"><span><i class="dot" style="--c:var(--blue)"></i> priority ${n}%</span><span><i class="dot" style="--c:var(--gray)"></i> Studio background ${b}%</span><span>free ${f}%</span></div>
  <div class="faint" style="font-size:11.5px;margin-top:3px">Studio runs at low priority and only uses CPU nothing else needs.</div>`;
}
const curStep = (j) => (j.steps.find((s) => s.active) || {}).label;
function toast(t) { const e = $("#toast"); e.textContent = t; e.classList.add("on"); clearTimeout(e._t); e._t = setTimeout(() => e.classList.remove("on"), 2200); }
async function post(u, b) { const r = await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }); const j = await r.json(); if (!r.ok) throw new Error(j.error || r.status); return j; }

function chart(hist, key, color, max = 100, unit = "%") {
  if (!hist || hist.length < 3) return `<div class="empty">Collecting…</div>`;
  const w = 600, h = 120, n = hist.length, y = (v) => h - 4 - (Math.min(v, max) / max) * (h - 12);
  const d = hist.map((p, i) => `${i ? "L" : "M"}${((i / (n - 1)) * w).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(" ");
  const last = hist[n - 1][key];
  return `<div style="display:flex;justify-content:space-between;align-items:baseline"><span class="lbl">${{ cpu: "CPU", mem: "Memory", norm: "Priority CPU (job bot, Muse, dashboard)", load: "Load" }[key]}</span><span class="num" style="font-weight:600">${last}${unit}</span></div>
  <svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${[0.25, 0.5, 0.75].map((f) => `<line x1="0" x2="${w}" y1="${y(max * f)}" y2="${y(max * f)}" stroke="var(--line)" stroke-dasharray="2 4"/>`).join("")}
  <path d="${d} L${w} ${h} L0 ${h}Z" fill="${color}" opacity=".08"/><path d="${d}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>
  <div class="dl">last ${Math.round((hist[n - 1].t - hist[0].t) / 60)} min</div>`;
}
function spark(vals, color) {
  const v = (vals || []).filter((x) => x != null); if (v.length < 2) return `<span class="faint">—</span>`;
  const mn = Math.min(...v), mx = Math.max(...v), w = 90, h = 24;
  const d = v.map((x, i) => `${i ? "L" : "M"}${((i / (v.length - 1)) * w).toFixed(1)} ${(h - 3 - ((x - mn) / (mx - mn || 1)) * (h - 6)).toFixed(1)}`).join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" style="width:90px;height:24px"><path d="${d}" fill="none" stroke="${color}" stroke-width="1.5"/></svg>`;
}

/* ---------- shared pieces ---------- */
function runRow(j) {
  const c = ch(j.cid), cur = curStep(j);
  return `<div class="run row click" onclick="openJob('${j.cid}','${j.job}')" style="display:block">
   <div class="top">${dp(c, 20)}<div class="grow" style="min-width:0;flex:1"><div class="t" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(j.title)}</div>
   <div class="s mut">${esc(c.name)} · ${j.lang === "en" ? "English" : "Hindi"}</div></div>${badge(j.status, j)}</div>
   <div style="margin-top:10px">${seg(j)}</div>
   <div class="foot"><span>${cur ? `${esc(cur)}${j.eta != null ? ` · about ${dur(j.eta)} left` : ""}` : "Finishing"}</span><span class="num">${Math.round(j.pct * 100)}% · ${dur(j.started ? now() - j.started : null)}</span></div></div>`;
}
function needRow(n) {
  const act = n.kind === "approve" ? `<button class="btn sm ok" onclick="event.stopPropagation();decide('${n.cid}','${n.job}','approve')">Approve</button><button class="btn sm" onclick="event.stopPropagation();openJob('${n.cid}','${n.job}')">Review</button>`
    : n.kind === "task" ? `<button class="btn sm" onclick="event.stopPropagation();doneTask('${n.id}')">Mark done</button>` : `<a class="btn sm" href="#server">Open</a>`;
  return `<div class="row ${n.kind === "approve" ? "click" : ""}" ${n.kind === "approve" ? `onclick="openJob('${n.cid}','${n.job}')"` : ""}><i class="dot" style="--c:${LV[n.lvl]}"></i><div class="grow"><div class="t">${esc(n.title)}</div><div class="s">${esc(n.sub || "")}</div></div><div style="display:flex;gap:6px">${act}</div></div>`;
}
function issueRow(i) {
  return `<div class="row"><i class="dot" style="--c:${LV[i.lvl]}"></i><div class="grow"><div class="t" style="white-space:normal">${esc(i.title)}</div>${i.detail ? `<div class="s" style="white-space:normal">${esc(i.detail)}</div>` : ""}${i.fix ? `<div class="s" style="white-space:normal;color:var(--tx)">${esc(i.fix)}</div>` : ""}</div>${i.action === "reset-failed" ? `<button class="btn sm" onclick="resetFailed()">Clear</button>` : ""}</div>`;
}

/* ---------- pages ---------- */
const V = {
  today() {
    const d = new Date(now() * 1000), act = S.jobs.filter((j) => j.active);
    const fol = S.channels.reduce((a, c) => a + c.igF + c.fb, 0);
    const wait = (S.queue || S.jobs).filter((j) => ["waiting", "ready"].includes(j.status)).length, appr = (S.queue || S.jobs).filter((j) => j.status === "approved").length;
    const today = d.toISOString().slice(0, 10), made = S.activity.filter((a) => a.t.startsWith(today) && /rendered in/.test(a.msg)).length;
    const bad = S.issues.filter((i) => i.lvl === "bad").length, warn = S.issues.filter((i) => i.lvl === "warn").length;
    const s = S.server, b = briefCache;
    return `<div class="h1">${d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}</div>
    <div class="lead">${esc(S.doing)}.</div>
    <div class="card strip">
     <div><div class="lbl">Followers</div><div class="val">${nf(fol)}</div><div class="dl">${S.channels.length} channels · Instagram + Facebook</div></div>
     <div><div class="lbl"><i class="dot" style="--c:${K.violet}"></i>Needs approval</div><div class="val">${wait}</div><div class="dl">${appr} approved, waiting for a slot</div></div>
     <div><div class="lbl"><i class="dot" style="--c:${(S.quality.rate7 ?? 0) >= 70 ? K.green : (S.quality.rate7 ?? 0) >= 40 ? K.amber : K.red}"></i>First-pass rate</div><div class="val">${S.quality.rate7 == null ? "—" : S.quality.rate7 + "%"}</div><div class="dl">${S.quality.passed7} of ${S.quality.videos7} videos passed review on the first try (7 days) · ${made} rendered today</div></div>
     <div><div class="lbl"><i class="dot" style="--c:${act.length ? K.blue : K.gray}"></i>Building</div><div class="val">${act.length}</div><div class="dl">typical render ${dur(S.render_median)}</div></div>
     <div><div class="lbl"><i class="dot" style="--c:${bad ? K.red : warn ? K.amber : K.green}"></i>Health</div><div class="val">${bad ? bad + " <small>to fix</small>" : warn ? warn + " <small>to watch</small>" : "OK"}</div><div class="dl">priority CPU ${Math.round(s.cpu_norm || 0)}% · disk ${Math.round(s.disk_pct)}%</div></div>
    </div>
    <div class="cols" style="margin-top:16px">
     <div>
      <div class="card brief"><div class="hd">${ic("spark")}<span>Brief</span><span class="faint">${b && b.t ? "written " + ago(b.t) : ""}</span><button class="btn sm" style="margin-left:auto" onclick="loadBrief(1)">${ic("refresh")}Refresh</button></div>
       ${b && b.headline ? `<div class="hl">${esc(b.headline)}</div><ul>${(b.lines || []).map((l) => `<li>${esc(l)}</li>`).join("")}</ul>` : `<div class="mut" style="margin-top:8px">${b && b.error ? "Could not write the brief: " + esc(b.error) : "Writing the brief…"}</div>`}</div>
      <div class="sec"><h3>Needs you</h3><span class="mut">${S.needs.length}</span></div>
      <div class="card">${S.needs.map(needRow).join("") || `<div class="empty">Nothing needs you right now.</div>`}</div>
      <div class="sec"><h3>Accuracy</h3><span class="mut">share of videos that pass the final review on the first try</span></div>
      <div class="card pad">${qualityChart(S.quality)}</div>
      <div class="sec"><h3>Building now</h3><a class="r mut" href="#runs">All runs →</a></div>
      <div class="card">${act.map(runRow).join("") || `<div class="empty">Idle. Next: ${esc(S.schedule[0]?.name || "—")} ${inT(S.schedule[0]?.in)}.</div>`}</div>
     </div>
     <div>
      <div class="sec" style="margin-top:0"><h3>Server</h3><a class="r mut" href="#server">Details →</a></div>
      <div class="card pad">${cpuSplit(s)}${[["Memory", s.mem_pct, thr(s.mem_pct, 80, 92), `${s.mem_used_gb} / ${s.mem_total_gb} GB`], ["Disk", s.disk_pct, thr(s.disk_pct, 85, 93), `${s.disk_free_gb} GB free`], ["Load per core", (s.load[1] / s.cores / 4) * 100, thr(s.load[1] / s.cores, 3, 5), `${(s.load[1] / s.cores).toFixed(1)} (5 min)`]]
        .map(([l, v, c, t]) => `<div style="margin-top:10px"><div style="display:flex;justify-content:space-between;font-size:12.5px"><span class="mut">${l}</span><span class="num">${t}</span></div><div style="margin-top:5px">${meter(v, c)}</div></div>`).join("")}</div>
      <div class="sec"><h3>Issues</h3><span class="mut">${S.issues.length}</span></div>
      <div class="card">${S.issues.slice(0, 5).map(issueRow).join("") || `<div class="empty">No issues.</div>`}${S.issues.length > 5 ? `<a class="row mut" href="#server">${S.issues.length - 5} more →</a>` : ""}</div>
      <div class="sec"><h3>Coming up</h3></div>
      <div class="card">${S.schedule.map((t) => `<div class="row"><i class="dot ${t.running ? "live" : ""}" style="--c:${t.running ? K.blue : K.gray}"></i><div class="grow"><div class="t">${esc(t.name)}</div><div class="s">${t.last ? "last ran " + ago(t.last) : "not run yet"}</div></div><span class="num mut">${t.running ? "running" : inT(t.in)}</span></div>`).join("")}</div>
     </div>
    </div>`;
  },
  runs() {
    const F = [["all", "All"], ["active", "Building"], ["need", "Needs you"], ["held", "Held"], ["approved", "Approved"], ["posted", "Posted"], ["rejected", "Rejected"], ["removed", "Removed"], ["cancelled", "Cancelled"]];
    const gone = (j) => ["rejected", "removed", "cancelled"].includes(j.status);  // 18 Nov (owner): All hides removed/rejected
    const ok = (j) => (runFilter === "all" ? !gone(j) : (runFilter === "active" ? j.active : runFilter === "need" ? ["waiting", "ready"].includes(j.status) : j.status === runFilter));
    const list = S.jobs.filter((j) => ok(j) && (runCh === "all" || j.cid === runCh));
    return `<div class="h1">Runs</div><div class="lead">Every video the engine has made or is making. Click a row for the full timeline, review and log.</div>
    <div class="tools"><div class="tabs">${F.map(([k, t]) => `<button class="${runFilter === k ? "on" : ""}" onclick="runFilter='${k}';render(1)">${t} <span class="faint">${S.jobs.filter((j) => k === "all" ? !gone(j) : (k === "active" ? j.active : k === "need" ? ["waiting", "ready"].includes(j.status) : j.status === k)).length}</span></button>`).join("")}</div>
     <select onchange="runCh=this.value;render(1)"><option value="all">All pages</option>${S.channels.filter((c) => c.group === "Studio").map((c) => `<option value="${c.id}" ${runCh === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div>
    <div class="card tw" style="margin-top:12px"><table class="stack"><thead><tr><th>Status</th><th>Video</th><th class="hide-m">Page</th><th>Progress</th><th class="hide-m">Review</th><th class="hide-m">Updated</th></tr></thead><tbody>
    ${list.map((j) => { const c = ch(j.cid); return `<tr class="click" onclick="openJob('${j.cid}','${j.job}')"><td>${badge(j.status, j)}</td>
      <td><div class="tt">${esc(j.title)}</div><div class="mono faint">${esc(j.job)} · ${j.lang === "en" ? "EN" : "HI"}</div></td>
      <td class="hide-m"><span style="display:flex;gap:8px;align-items:center">${dp(c, 20)}${esc(c.name)}</span></td>
      <td style="min-width:170px">${seg(j)}<div class="mono faint" style="margin-top:4px">${j.active ? esc(curStep(j) || "") + " · " : ""}${Math.round(j.pct * 100)}%</div></td>
      <td class="hide-m">${j.review.ok === true ? `<span class="up">Passed</span>${j.review.score ? ` · ${j.review.score}/10` : ""}` : j.review.ok === false ? `<span class="dn">${(j.review.problems || []).length ? (j.review.problems.length + (j.review.problems.length > 1 ? " problems" : " problem")) : "Held"}</span>` : `<span class="faint">—</span>`}</td>
      <td class="hide-m mut">${ago(j.updated)}</td></tr>`; }).join("") || `<tr><td colspan="6" class="empty">No runs here.</td></tr>`}</tbody></table></div>`;
  },
  approvals() {
    const Q = S.queue || S.jobs;   // 20 Nov: full approval queue, not the newest-40 Runs list
    const w = Q.filter((j) => ["waiting", "ready"].includes(j.status)), held = Q.filter((j) => j.status === "held"), ap = Q.filter((j) => j.status === "approved");
    const card = (j) => { const c = ch(j.cid), base = `/media/${j.cid}/${j.job}/`;
      return `<div class="card pad"><div class="media"><div class="cover" onclick="openJob('${j.cid}','${j.job}')">${(j.files[j.final] || j.files["preview.mp4"]) ? `${j.files["cover.jpg"] ? `<img src="${base}cover-s.jpg?v=${j.updated}" onerror="this.onerror=null;this.src='${base}cover.jpg'">` : ""}<span class="pl">${ic("play")}${j.qc.dur ? Math.round(j.qc.dur) + "s" : "Play"}</span>` : `<div class="empty" style="padding:70px 8px;font-size:12px">No video yet<br>held before render</div>`}</div>
       <div style="min-width:0"><div style="display:flex;gap:8px;align-items:center">${dp(c, 20)}<span class="mut">${esc(c.name)} · ${j.lang === "en" ? "English" : "Hindi"}</span><span style="margin-left:auto">${badge(j.status, j)}</span></div>
       <div style="font-weight:600;font-size:14.5px;margin-top:6px">${esc(j.title)}</div>
       <div class="chips" style="margin-top:8px">${j.review.ok ? lvlBadge("ok", "Passed review") : ""}${j.review.score ? lvlBadge(j.review.score >= 8 ? "ok" : "warn", `Visual ${j.review.score}/10`) : ""}${j.qc.lufs ? lvlBadge("info", `${j.qc.lufs} LUFS`) : ""}</div>
       ${(j.review.problems || []).length ? `<ul class="mut" style="margin:8px 0 0 16px;font-size:12.5px">${j.review.problems.slice(0, 3).map((p) => `<li>${esc(String(p).slice(0, 160))}</li>`).join("")}</ul>` : ""}
       ${["waiting", "ready"].includes(j.status) ? `<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><button class="btn ok" onclick="decide('${j.cid}','${j.job}','approve')">Approve</button><button class="btn no" onclick="decide('${j.cid}','${j.job}','reject')">Reject</button><button class="btn" onclick="feedback('${j.cid}','${j.job}')">Feedback</button></div>`
        : j.status === "held" ? `<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;align-items:center"><span class="mut" style="font-size:12.5px">${esc(healerLine(j))}</span><button class="btn sm" onclick="decide('${j.cid}','${j.job}','approve')">Approve anyway</button><button class="btn sm no" onclick="if(confirm('Remove this video? It will never be posted.'))decide('${j.cid}','${j.job}','remove')">Remove</button></div>`
        : j.status === "approved" ? `<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><button class="btn sm no" onclick="if(confirm('Remove this video from the queue? It will never be posted.'))decide('${j.cid}','${j.job}','remove')">Remove</button></div>` : ""}
       </div></div></div>`; };
    return `<div class="h1">Approvals</div><div class="lead">Only videos that passed the server's review come here. Approving here or in Telegram does the same thing.${S.settings.auto_approve ? ` Auto-approve is on for scores of ${S.settings.min_score}/10 and up.` : ""}</div>
     <div class="sec"><i class="dot" style="--c:${K.violet}"></i><h3>Needs approval</h3><span class="mut">${w.length}</span></div><div class="g2">${w.map(card).join("") || `<div class="card empty">Nothing is waiting for you.</div>`}</div>
     ${held.length ? `<div class="sec"><i class="dot" style="--c:${K.amber}"></i><h3>Held by the server's reviewer</h3><span class="mut">${held.length} · nothing for you: the server fixes or rebuilds these, and they reach Telegram only after they pass</span></div><div class="g2">${held.map(card).join("")}</div>` : ""}
     ${ap.length ? `<div class="sec"><i class="dot" style="--c:${K.teal}"></i><h3>Approved, waiting for a slot</h3><span class="mut">${ap.length}</span></div><div class="g2">${ap.map(card).join("")}</div>` : ""}`;
  },
  channels() {
    const row = (c) => { const cnt = c.counts || {}, st = { live: ["Live", "ok"], warm: ["Warm-up", "warn"], off: ["Off", "info"], manual: ["Manual", "info"] }[c.status];
      return `<tr class="click" onclick="openChannel('${c.id}')"><td><span style="display:flex;gap:10px;align-items:center">${dp(c, 26)}<span><div style="font-weight:500">${esc(c.name)}</div><div class="faint" style="font-size:12px">@${esc(c.ig)}</div></span></span></td>
      <td>${lvlBadge(st[1], st[0])}<div class="faint" style="font-size:12px;margin-top:3px">${esc(c.note)}</div></td><td class="num">${nf(c.igF)}</td><td class="num hide-m">${nf(c.fb)}</td><td class="num hide-m">${nf(c.posts)}</td>
      <td class="hide-m" style="white-space:normal;min-width:210px">${Object.entries(cnt).filter(([, v]) => v).map(([k, v]) => `<span class="mut" style="margin-right:10px;display:inline-block">${v} ${(ST[k] || [k])[0].toLowerCase()}</span>`).join("") || `<span class="faint">—</span>`}</td><td class="hide-m">${spark(c.spark, c.color)}</td></tr>`; };
    const st = S.channels.filter((c) => c.group === "Studio"), bz = S.channels.filter((c) => c.group !== "Studio");
    const head = `<thead><tr><th>Channel</th><th>Status</th><th>IG followers</th><th class="hide-m">FB followers</th><th class="hide-m">IG posts</th><th class="hide-m">Videos</th><th class="hide-m">30 days</th></tr></thead>`;
    return `<div class="h1">Channels</div><div class="lead">${S.channels.length} channels. Follower numbers come from Meta every 30 minutes. Click one for its latest posts.</div>
     <div class="sec"><h3>Studio pages</h3><span class="mut">made by the engine</span></div><div class="card tw"><table>${head}<tbody>${st.map(row).join("")}</tbody></table></div>
     <div class="sec"><h3>Clipping campaigns</h3><span class="mut">Cut Capsule · ranked every 6 h from contentrewards.com · join on Whop, then add it below</span></div><div class="card tw"><table><thead><tr><th>Score</th><th>Campaign</th><th class="hide-m">Why</th><th></th></tr></thead><tbody>${((S.campaigns || {}).top || []).map((c) => `<tr><td class="num" style="font-weight:600">${c.score}</td><td class="w">${esc(c.brand || "")} · ${esc(c.title || "")}</td><td class="mut hide-m">${esc((c.why || []).join(" · "))}</td><td>${c.joined ? `<span class="badge" style="--c:var(--green)">Joined</span>` : `<a class="btn sm" target="_blank" href="${esc(c.url)}">Open ${ic("ext")}</a> <button class="btn sm" onclick="$('#srcU').value='${esc(c.url)}';$('#srcC').focus()">I joined</button>`}</td></tr>`).join("") || `<tr><td colspan="4" class="empty">No campaign data yet (first run within 6 h).</td></tr>`}</tbody></table></div>
     <div class="card pad" style="margin-top:10px"><div style="font-weight:600;margin-bottom:6px">Add a source you may clip (a joined campaign or a creator's OK)</div>
      <input id="srcU" type="text" placeholder="Campaign link (contentrewards.com/c/campaigns/...)" style="width:100%;box-sizing:border-box">
      <input id="srcC" type="text" placeholder="Footage: YouTube channels (@handle) and/or video links, separated by spaces" style="width:100%;box-sizing:border-box;margin-top:6px">
      <textarea id="srcR" rows="3" placeholder="Campaign rules, one per line (tags, length, sound, platforms...)" style="width:100%;box-sizing:border-box;margin-top:6px"></textarea>
      <div class="tools" style="margin:6px 0 0"><input id="srcT" type="text" placeholder="Caption must include (e.g. @creator #ad)" style="flex:1;min-width:180px"><label class="mut"><input id="srcW" type="checkbox"> no watermark</label><button class="btn pri" onclick="addSource()">Add + start clipping</button></div>
      <div class="mut" style="font-size:12.5px;margin-top:6px">Sources: ${((S.campaigns || {}).sources || []).map((s) => esc(s.key) + (s.active ? "" : " (off)")).join(", ") || "none yet"}. New uploads are clipped hourly while the laptop is on.</div></div>
     <div class="sec"><h3>Offer reels</h3><span class="mut">comment KEYWORD → follow → link in DM</span></div><div class="card tw"><table><thead><tr><th>Page</th><th>Keyword</th><th>Gift</th><th>Comments</th><th>Asked to follow</th><th>Links sent</th><th>New follows</th><th class="hide-m">Made</th></tr></thead><tbody>${(S.offers || []).map((o) => `<tr class="click" onclick="openJob('${o.cid}','${o.job}')"><td>${esc((ch(o.cid) || {}).name || o.cid)}</td><td class="mono" style="font-weight:600">${esc(o.kw)}</td><td>${o.url ? `<a target="_blank" href="${esc(o.url)}" onclick="event.stopPropagation()">${esc(o.gift)} ${ic("ext")}</a>` : `${esc(o.gift)} <span class="faint">(being made)</span>`}</td><td class="num">${nf(o.stats.comments || 0)}</td><td class="num">${nf(o.stats.asked || 0)}</td><td class="num">${nf(o.stats.delivered || 0)}</td><td class="num up">${nf(o.stats.new_follows || 0)}</td><td class="mut hide-m">${esc(o.made || "")}</td></tr>`).join("") || `<tr><td colspan="8" class="empty">No offer reels yet. About 1 in 4 new videos on Finance, Tech, Katha and Navkar Bhav will be one.</td></tr>`}</tbody></table></div>
     <div class="sec"><h3>Businesses</h3></div><div class="card tw"><table>${head}<tbody>${bz.map(row).join("")}</tbody></table></div>
     <div class="sec"><h3>Make a video now</h3></div><div class="card pad"><div class="tools" style="margin:0"><select id="mkc">${st.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select><input id="mkt" type="text" placeholder="Topic (optional) · Cut Capsule: paste a YouTube link (+ '5 clips')" style="flex:1;min-width:200px"><button class="btn pri" onclick="makeNow()">Start</button></div><div class="mut" style="margin-top:8px;font-size:12.5px">Runs in the background at low priority (the job bot always comes first). It appears under Runs within a few seconds.</div></div>`;
  },
  server() {
    const s = S.server;
    return `<div class="h1">Server</div><div class="lead">Oracle Ampere · ${s.cores} cores · ${s.mem_total_gb} GB · up ${Math.round(s.uptime_h / 24)} days. Sampled every 5 seconds.</div>
      <div class="g3" style="margin-top:16px"><div class="card pad">${cpuSplit(s)}<div style="margin-top:12px">${chart(s.hist, "norm", "var(--blue)")}</div></div><div class="card pad"><div class="lbl">Memory</div><div style="margin-top:12px">${chart(s.hist, "mem", "var(--violet)")}</div></div>
      <div class="card pad"><div class="lbl">Disk</div><div class="val">${Math.round(s.disk_pct)}%<small>${s.disk_free_gb} GB free of ${s.disk_total_gb}</small></div><div style="margin-top:10px">${meter(s.disk_pct, thr(s.disk_pct, 85, 93))}</div>
       <div class="lbl" style="margin-top:16px">Load (1 / 5 / 15 min)</div><div class="val num" style="font-size:18px">${s.load.join(" · ")}</div><div class="dl">${s.load[1] > s.cores * 3 ? "Overloaded: more work than cores" : s.load[1] > s.cores ? "Busy" : "Comfortable"}</div></div></div>
     <div class="sec"><h3>Issues</h3><span class="mut">${S.issues.length}</span></div><div class="card">${S.issues.map(issueRow).join("") || `<div class="empty">No issues.</div>`}</div>
     <div class="sec"><h3>Free Gemini keys</h3><span class="mut">today (resets 13:30 IST)${s.keys && s.keys.alerted ? " · all out at " + esc(s.keys.alerted) : ""}</span></div><div class="card tw"><table><thead><tr><th>Key</th><th>Calls OK</th><th>Failed</th><th>Out of quota today</th><th>Most used</th></tr></thead><tbody>${((s.keys && s.keys.list) || []).map((k) => { const top = Object.entries(k.models || {}).sort((a, b) => b[1] - a[1]).slice(0, 2).map((x) => esc(x[0].replace("gemini-", "")) + " " + x[1]).join(", "); const out = (k.out || []).length; return `<tr><td class="mono"><span style="display:flex;gap:8px;align-items:center"><i class="dot" style="--c:${(k.out || []).includes("*") ? K.red : out ? K.amber : K.green}"></i>${esc(k.id)}</span></td><td class="num">${k.ok}</td><td class="num">${k.fail}</td><td>${out ? esc((k.out || []).map((m) => m === "*" ? "all models" : m.replace("gemini-", "")).join(", ")) : `<span class="mut">none</span>`}</td><td class="mut">${top || "–"}</td></tr>`; }).join("") || `<tr><td colspan="5" class="empty">No keys found.</td></tr>`}</tbody></table></div>
     <div class="sec"><h3>Timers</h3></div><div class="card tw"><table><thead><tr><th>Job</th><th>Unit</th><th>Last run</th><th>Next run</th></tr></thead><tbody>${S.schedule.map((t) => `<tr><td><span style="display:flex;gap:8px;align-items:center"><i class="dot ${t.running ? "live" : ""}" style="--c:${t.running ? K.blue : K.gray}"></i>${esc(t.name)}</span></td><td class="mono faint">${esc(t.unit)}</td><td class="mut">${ago(t.last)}</td><td>${t.running ? `<span style="color:var(--blue)">running</span>` : inT(t.in)}</td></tr>`).join("")}</tbody></table></div>
     <div class="sec"><h3>Processes</h3><span class="mut">${S.running.length}</span></div><div class="card tw"><table><thead><tr><th>What</th><th>Command</th><th>Running for</th></tr></thead><tbody>${S.running.map((r) => `<tr><td>${esc(r.kind)}</td><td class="mono faint" style="white-space:normal;word-break:break-all">${esc(r.cmd)}</td><td class="num">${dur(r.age)}</td></tr>`).join("") || `<tr><td colspan="3" class="empty">Nothing running.</td></tr>`}</tbody></table></div>`;
  },
  sources() {
    const L = srcCache;
    return `<div class="h1">Connected apps</div><div class="lead">Every outside service the engine depends on, with its status. Keys stay on the server; none are shown here.</div>
     <div class="card tw" style="margin-top:16px"><table><thead><tr><th>App</th><th class="hide-m">Used for</th><th>Status</th><th class="hide-m">Last used</th><th></th></tr></thead><tbody>
     ${L ? L.map((x) => `<tr><td style="font-weight:500">${esc(x.name)}</td><td class="hide-m mut">${esc(x.what)}</td><td>${lvlBadge(x.lvl, x.lvl === "ok" ? "Working" : x.lvl === "warn" ? "Check" : x.lvl === "bad" ? "Broken" : "Not set up")}<div class="faint" style="font-size:12px;margin-top:3px;white-space:normal">${esc(x.detail)}</div></td><td class="hide-m mut">${ago(x.last)}</td><td>${x.test ? `<button class="btn sm" onclick="testSrc('${x.test}')">Test</button>` : ""}</td></tr>`).join("") : `<tr><td colspan="5" class="empty">Checking…</td></tr>`}</tbody></table></div>`;
  },
  activity() {
    const L = S.activity.filter((a) => (logLvl === "all" || (logLvl === "problems" ? ["bad", "warn"].includes(a.lvl) : a.cid === logLvl)) && (!logQ || a.msg.toLowerCase().includes(logQ.toLowerCase())));
    return `<div class="h1">Activity log</div><div class="lead">The engine's own log, newest first.</div>
     <div class="tools"><div class="tabs">${[["all", "All"], ["problems", "Problems"], ...S.channels.slice(0, 3).map((c) => [c.id, c.name])].map(([k, t]) => `<button class="${logLvl === k ? "on" : ""}" onclick="logLvl='${k}';render(1)">${esc(t)}</button>`).join("")}</div>
      <input type="text" placeholder="Search the log" value="${esc(logQ)}" oninput="logQ=this.value;clearTimeout(window._lq);window._lq=setTimeout(()=>{render(1);const i=document.querySelector('.tools input');i.focus();i.setSelectionRange(i.value.length,i.value.length)},250)" style="flex:1;min-width:180px"></div>
     <div class="card" style="margin-top:12px">${L.map((a) => `<div class="row" style="align-items:flex-start;padding:8px 16px"><span class="mono faint" style="width:44px;padding-top:1px">${a.t.slice(11, 16)}</span><i class="dot" style="--c:${LV[a.lvl]};margin-top:6px"></i>${a.cid ? `${dp(ch(a.cid), 20, ";margin-top:3px")}` : `<span style="width:9px"></span>`}<span class="grow" style="word-break:break-word">${esc(a.msg)}</span></div>`).join("") || `<div class="empty">No lines match.</div>`}</div>`;
  },
  brain() {
    setTimeout(loadLearned, 0);
    return `<div class="h1">Brain</div><div class="lead">What the engine has learned. Every page reads the shared lessons and every other page's lessons before it writes a script. Drag nodes; hover for the text.</div>
     <div class="card" style="margin-top:16px;overflow:hidden"><canvas id="brainc"></canvas><div class="leg"><span><i class="dot" style="--c:var(--ink)"></i>Shared brain</span>${S.channels.slice(0, 3).map((c) => `<span>${dp(c, 20)}${esc(c.name)}</span>`).join("")}<span><i class="dot" style="--c:var(--blue)"></i>Shared lesson</span><span><i class="dot" style="--c:var(--red)"></i>Mistake the reviewer caught</span><span><i class="dot" style="--c:var(--teal)"></i>Learned from repos</span><span><i class="dot" style="--c:var(--green)"></i>Video</span></div></div>
     <div class="sec"><h3>Learning</h3><span class="mut">GitHub links and files you send in Studio360, plus a weekly search of GitHub. Studio reads them, keeps what helps, and scores every item by results.</span></div>
     <div id="learned" class="card"><div class="empty">Loading…</div></div>`;
  },
  published() {
    return `<div class="h1">Published</div><div class="lead">Everything Studio has posted, on every page, newest first. Numbers come live from Instagram, Facebook and YouTube (refreshed every 20 min). Campaign clips show whether their link was submitted on Content Rewards.</div>
     <div id="pubTot" class="strip" style="margin-top:16px"><div><div class="lbl">Posts</div><div class="val">…</div></div></div>
     <div class="tools" style="margin-top:12px"><div class="tabs" id="pubTabs"></div><select id="pubCh" onchange="pubCh=this.value;drawPublished()"></select></div>
     <div id="pubGrid" class="pubgrid" style="margin-top:12px"><div class="card empty">Loading…</div></div>`;
  },
  radar() {
    setTimeout(loadRadar, 0);
    return `<div class="h1">Radar</div><div class="lead">Every morning Studio scans Reddit, Hacker News, GitHub, Hugging Face, Product Hunt, Google News and a Google web search for new FREE tools, models and platform features, and keeps only what fits us. Repos go to the learner, tips to the brain, features to the build list. Nothing paid, nothing signed up without you.</div>
     <div id="radar" class="card" style="margin-top:16px"><div class="empty">Loading…</div></div>`;
  },
  settings() {
    const st = S.settings;
    return `<div class="h1">Settings</div>
     <div class="card" style="margin-top:16px">
      <div class="row"><div class="grow"><div class="t">Auto-approve top videos</div><div class="s" style="white-space:normal">Videos that pass every review check and score at least the number below go straight into the posting queue. You still see them in Telegram, marked "auto-approved".</div></div><div class="sw ${st.auto_approve ? "on" : ""}" onclick="setS({auto_approve:${!st.auto_approve}})"></div></div>
      <div class="row"><div class="grow"><div class="t">Minimum visual score</div><div class="s">Only used when auto-approve is on.</div></div><select onchange="setS({min_score:+this.value})">${[8, 9, 10].map((n) => `<option ${st.min_score == n ? "selected" : ""}>${n}</option>`).join("")}</select></div>
      <div class="row"><div class="grow"><div class="t">Theme</div><div class="s">Saved on this device.</div></div><button class="btn" onclick="toggleTheme()">Switch to ${document.documentElement.dataset.theme === "dark" ? "light" : "dark"}</button></div>
      <div class="row"><div class="grow"><div class="t">Add to your phone's home screen</div><div class="s" style="white-space:normal">Open this page in Chrome or Safari, then Share or menu → Add to Home screen. It opens full screen like an app.</div></div></div>
     </div>`;
  },
};

/* ---------- drawer: one run ---------- */
async function openJob(cid, job) {
  drawerKey = `job:${cid}:${job}`; $("#drawer").classList.add("on"); $("#panel").innerHTML = `<div class="pb mut">Loading…</div>`;
  const d = await (await fetch(`/api/job?cid=${encodeURIComponent(cid)}&job=${encodeURIComponent(job)}`)).json();
  const c = ch(cid), base = `/media/${cid}/${job}/`, vid = d.files["preview.mp4"] ? "preview.mp4" : d.final, have = d.files["preview.mp4"] || d.files[d.final];
  const t0 = Math.min(...d.timeline.filter((r) => r.start).map((r) => r.start)), t1 = Math.max(...d.timeline.map((r) => (r.start || 0) + (r.dur || 0)), t0 + 1);
  const wf = d.timeline.map((r) => `<div class="r ${r.start == null ? "p" : ""}"><span>${esc(r.label)}</span><div class="tr">${r.start != null ? `<div class="b" style="--c:${r.active ? "var(--blue)" : "var(--green)"};left:${((r.start - t0) / (t1 - t0)) * 100}%;width:${(Math.max(r.dur || 0, 1) / (t1 - t0)) * 100}%"></div>` : ""}</div><span class="num mut" style="text-align:right;white-space:nowrap">${r.waited ? "waited " + dur(r.waited) : r.start != null ? dur(r.dur) : "—"}</span></div>`).join("");
  const rv = d.review_full || {};
  $("#panel").innerHTML = `<div class="ph">${dp(c, 34, ";margin-top:2px")}<div style="flex:1;min-width:0"><div style="font-weight:600;font-size:15px">${esc(d.title)}</div><div class="mut">${esc(c.name)} · ${d.lang === "en" ? "English" : "Hindi"} · <span class="mono">${esc(job)}</span></div></div>${badge(d.status, d)}<button class="icon-btn" onclick="closeDrawer()">${ic("x")}</button></div>
  <div class="pb">
   <div class="media"><div class="cover">${have ? `<video src="${base + vid}" poster="${d.files["cover.jpg"] ? base + "cover.jpg" : ""}" controls playsinline preload="none"></video>` : d.files["cover.jpg"] ? `<img src="${base}cover.jpg">` : `<div class="empty">No video yet</div>`}</div>
    <div><div class="kv"><span>Progress</span><span class="num">${Math.round(d.pct * 100)}%${d.active ? " · " + esc(curStep(d) || "") : ""}</span><span>Length</span><span>${d.qc.dur ? Math.round(d.qc.dur) + " s" : "—"}</span><span>Loudness</span><span>${d.qc.lufs ?? "—"} LUFS</span><span>Review</span><span>${d.review.ok === true ? `<span class="up">Passed</span>` : d.review.ok === false ? `<span class="dn">Held</span>` : "—"}${d.review.score ? ` · visual ${d.review.score}/10` : ""}</span><span>Updated</span><span>${ago(d.updated)}</span></div>
    ${["waiting", "ready", "held"].includes(d.status) ? `<div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap"><button class="btn ok" onclick="decide('${cid}','${job}','approve')">Approve</button><button class="btn no" onclick="decide('${cid}','${job}','reject')">Reject</button><button class="btn" onclick="feedback('${cid}','${job}')">Feedback</button></div>` : ""}</div></div>
   ${["posted", "approved", "removed"].includes(d.status) ? "" : `<h4>Change this run</h4><div class="card" style="padding:12px">
    <div class="mut" style="font-size:12.5px;margin-bottom:8px">Wrong page or topic? Stop it, or make it again on any page with the topic as written here.</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center"><select id="chTo">${S.channels.filter((x) => x.group === "Studio").map((x) => `<option value="${x.id}" ${x.id === cid ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div>
    <textarea id="chTopic" rows="3" style="width:100%;margin-top:8px;box-sizing:border-box">${esc(d.request || d.topic || d.title || "")}</textarea>
    <div class="mut" style="font-size:12px;margin-top:4px">Write what you want in your own words: the engine researches it and names the topic itself.${d.request ? " Topic it chose: " + esc(d.topic) : ""}</div>
    <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">${d.active || ["paused", "prepped", "made"].includes(d.status) ? `<button class="btn no" onclick="changeRun('${cid}','${job}','stop')">${d.active ? "Stop" : "Cancel"}</button>` : ""}<button class="btn ok" onclick="changeRun('${cid}','${job}','redo')">${d.active ? "Stop and make again" : "Make again"}</button></div></div>`}
   <h4>Timeline</h4><div class="wf">${wf}</div>
   ${(rv.problems || []).length || (rv.minor || []).length ? `<h4>Review</h4><ul style="padding-left:16px">${(rv.problems || []).map((p) => `<li class="dn">${esc(p)}</li>`).join("")}${(rv.minor || []).map((p) => `<li class="mut">${esc(p)}</li>`).join("")}</ul>` : ""}
   ${d.caption ? `<h4>Caption</h4><div style="white-space:pre-wrap">${esc(d.caption)}</div>` : ""}
   ${d.scenes.length ? `<h4>Script · ${d.scenes.length} scenes</h4><ol style="padding-left:18px">${d.scenes.map((s) => `<li style="margin-top:4px"><span class="faint mono">${esc(s.type)}</span> ${esc(s.vo)}</li>`).join("")}</ol>` : ""}
   <h4>Log</h4><div class="logs">${d.logs.map((l) => esc(l)).join("\n") || "No log lines for this run."}</div>
  </div>`;
}
async function openChannel(id) {
  const c = ch(id); drawerKey = "ch:" + id; $("#drawer").classList.add("on");
  const head = `<div class="ph">${dp(c, 34, ";margin-top:2px")}<div style="flex:1"><div style="font-weight:600;font-size:15px">${esc(c.name)}</div><div class="mut">${esc(c.note)}</div></div><button class="icon-btn" onclick="closeDrawer()">${ic("x")}</button></div>`;
  const links = [c.ig && `<a class="btn sm" target="_blank" href="https://instagram.com/${c.ig}">Instagram ${ic("ext")}</a>`, c.fb_url && `<a class="btn sm" target="_blank" href="${c.fb_url}">Facebook ${ic("ext")}</a>`, c.yt && `<a class="btn sm" target="_blank" href="https://youtube.com/${c.yt}">YouTube${c.yt_ok === false ? " (not linked)" : ""} ${ic("ext")}</a>`].filter(Boolean).join("");
  $("#panel").innerHTML = head + `<div class="pb"><div class="kv"><span>IG followers</span><span class="num">${nf(c.igF)}</span><span>FB followers</span><span class="num">${nf(c.fb)}</span><span>IG posts</span><span class="num">${nf(c.posts)}</span></div><div class="chips" style="margin-top:12px">${links}</div><h4>Latest posts</h4><div id="posts" class="mut">Loading…</div><h4>Last idea ranking</h4><div id="ideas" class="mut">Loading…</div></div>`;
  fetch(`/api/ideas?cid=${id}`).then((r) => r.json()).then((x) => { const el = $("#ideas"); if (!el) return; el.outerHTML = x && x.ideas ? `<div class="mut" style="font-size:12.5px;margin-bottom:6px">${esc(x.t)} · picked the top one of ${x.ideas.length}</div><div class="card tw"><table><thead><tr><th>Score</th><th>Idea</th><th class="hide-m">Demand</th></tr></thead><tbody>${x.ideas.map((i, k) => `<tr><td class="num" style="${k ? "" : "font-weight:600"}">${i.score.toFixed(1)}</td><td class="w">${k ? "" : `<span class="badge" style="--c:var(--green);margin-right:6px">Picked</span>`}${esc(i.topic)}</td><td class="hide-m mut num">${nf(i.median_views)} views</td></tr>`).join("")}</tbody></table></div>` : `<div class="mut">No ranking yet. The next video for this page will make one.</div>`; });
  const ps = await (await fetch(`/api/posts?cid=${id}`)).json();
  $("#posts").outerHTML = Array.isArray(ps) && ps.length ? `<div class="posts">${ps.map((p) => `<a class="post" target="_blank" href="${p.url}"><div class="im" style="background-image:url('${p.thumb || ""}')"></div><div class="m"><span>${nf(p.likes)} likes</span><span>${nf(p.comments)} comments</span><span class="faint" style="margin-left:auto">${p.t.slice(5, 10)}</span></div></a>`).join("")}</div>` : `<div class="mut">${ps && ps.error ? "Could not read posts: " + esc(ps.error) : "No posts yet."}</div>`;
}
function closeDrawer() { $("#drawer").classList.remove("on"); $("#panel").innerHTML = ""; drawerKey = null; }

/* ---------- command palette + Ask ---------- */
let palSel = 0;
function palItems(q) {
  const go = NAV.flatMap(([, it]) => it).map(([k, t]) => ({ t: "Go to " + t, s: "page", f: () => (location.hash = k) }));
  const runs = (S?.jobs || []).map((j) => ({ t: j.title, s: ch(j.cid).name + " · " + (ST[j.status] || [j.status])[0], f: () => openJob(j.cid, j.job) }));
  const chs = (S?.channels || []).map((c) => ({ t: c.name, s: "channel", f: () => openChannel(c.id) }));
  const all = [...go, ...chs, ...runs]; q = q.trim().toLowerCase();
  const m = q ? all.filter((x) => (x.t + " " + x.s).toLowerCase().includes(q)) : all.slice(0, 9);
  return [...(q ? [{ t: `Ask: “${q}”`, s: "AI answer from live data", ask: 1 }] : []), ...m.slice(0, 9)];
}
function openPalette() {
  $("#pal").classList.add("on");
  $("#palbox").innerHTML = `<div class="pal-in"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input id="pq" placeholder="Ask anything, or type a page, channel or video" autocomplete="off"><kbd>Esc</kbd></div><div class="pal-l" id="pl"></div><div id="pans"></div>`;
  const i = $("#pq"); palSel = 0; drawPal(""); i.focus();
  i.oninput = () => { palSel = 0; drawPal(i.value); };
  i.onkeydown = (e) => { const it = palItems(i.value); if (e.key === "ArrowDown") { palSel = Math.min(it.length - 1, palSel + 1); drawPal(i.value); e.preventDefault(); } else if (e.key === "ArrowUp") { palSel = Math.max(0, palSel - 1); drawPal(i.value); e.preventDefault(); } else if (e.key === "Enter") pick(it[palSel], i.value); };
}
function drawPal(q) { const it = palItems(q); $("#pl").innerHTML = it.map((x, k) => `<div class="it ${k === palSel ? "on" : ""}" data-k="${k}">${x.ask ? ic("spark") : ""}<span>${esc(x.t)}</span><small>${esc(x.s)}</small></div>`).join(""); document.querySelectorAll("#pl .it").forEach((el) => (el.onclick = () => pick(it[+el.dataset.k], q))); }
async function pick(x, q) {
  if (!x) return;
  if (x.ask) { $("#pans").innerHTML = `<div class="ans mut">Thinking…</div>`; try { const r = await post("/api/ask", { q }); $("#pans").innerHTML = `<div class="ans">${esc(r.answer)}</div>`; } catch (e) { $("#pans").innerHTML = `<div class="ans dn">${esc(e.message)}</div>`; } return; }
  closePalette(); x.f();
}
function closePalette() { $("#pal").classList.remove("on"); }
addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); } else if (e.key === "Escape") { closePalette(); closeDrawer(); } });

/* ---------- brain ---------- */
async function startBrain() {
  const cv = $("#brainc"); if (!cv) return;
  const data = await (await fetch("/api/brain")).json();
  const css = getComputedStyle(document.documentElement), col = (v) => css.getPropertyValue(v).trim();
  const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr; const x = cv.getContext("2d"); x.scale(dpr, dpr);
  const SC = { posted: col("--green"), approved: col("--teal"), held: col("--amber"), rejected: col("--red") };
  const by = {}, N = data.nodes.map((n, i) => (by[n.id] = { ...n, x: W / 2 + Math.cos(i * 2.4) * (40 + i * 2), y: H / 2 + Math.sin(i * 2.4) * (40 + i * 2), vx: 0, vy: 0,
    r: n.kind === "core" ? 11 : n.kind === "page" || n.kind === "hub" ? 9 : n.kind === "video" ? 4.5 : 3.5,
    c: n.kind === "core" ? col("--ink") : n.kind === "page" ? n.color : n.kind === "hub" || n.kind === "learned" ? col("--teal") : n.kind === "auto" ? col("--red") : n.kind === "video" ? SC[n.status] || col("--gray") : n.cid ? n.color : col("--blue") }));
  const L = data.links.map((l) => ({ s: by[l.s], t: by[l.t] })).filter((l) => l.s && l.t); const core = by.brain; core.fx = W / 2; core.fy = H / 2;
  const anchors = N.filter((n) => n.kind === "page" || n.kind === "hub"), R = Math.min(W, H) * 0.3;
  anchors.forEach((n, k) => { const a = -Math.PI / 2 + (k * 2 * Math.PI) / anchors.length; n.fx = W / 2 + R * Math.cos(a) * (W > H ? 1.35 : 1); n.fy = H / 2 + R * Math.sin(a); n.pin = [n.fx, n.fy]; n.x = n.fx; n.y = n.fy; });
  let drag = null, hov = null, a = 1; const tip = document.body.appendChild(Object.assign(document.createElement("div"), { className: "tip" }));
  (function tick() {
    if (!document.body.contains(cv)) { tip.remove(); return; }
    if (a > 0.01) {
      for (let i = 0; i < N.length; i++) for (let j = i + 1; j < N.length; j++) { const p = N[i], q = N[j]; let dx = q.x - p.x, dy = q.y - p.y, d2 = dx * dx + dy * dy + 0.01, d = Math.sqrt(d2), f = (600 * a) / d2; dx /= d; dy /= d; p.vx -= dx * f; p.vy -= dy * f; q.vx += dx * f; q.vy += dy * f; }
      for (const l of L) { const want = l.s.kind === "core" ? 120 : l.s.kind === "page" || l.s.kind === "hub" ? 58 : 48; const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = ((d - want) / d) * 0.05 * a; l.s.vx += dx * f; l.s.vy += dy * f; l.t.vx -= dx * f; l.t.vy -= dy * f; }
      for (const n of N) { if (n.fx != null) { n.x = n.fx; n.y = n.fy; n.vx = n.vy = 0; continue; } n.vx += (W / 2 - n.x) * 0.002 * a; n.vy += (H / 2 - n.y) * 0.002 * a; n.vx *= 0.8; n.vy *= 0.8; n.x = Math.max(10, Math.min(W - 10, n.x + n.vx)); n.y = Math.max(10, Math.min(H - 10, n.y + n.vy)); }
      a *= 0.99;
    }
    x.clearRect(0, 0, W, H); x.lineWidth = 1;
    for (const l of L) { x.strokeStyle = hov && (hov === l.s || hov === l.t) ? col("--mut") : col("--line"); x.beginPath(); x.moveTo(l.s.x, l.s.y); x.lineTo(l.t.x, l.t.y); x.stroke(); }
    for (const n of N) { x.beginPath(); x.arc(n.x, n.y, n.r, 0, 7); if (n.kind === "video") { x.fillStyle = col("--panel"); x.fill(); x.strokeStyle = n.c; x.lineWidth = 2; x.stroke(); x.lineWidth = 1; } else { x.fillStyle = n.c; x.fill(); }
      if (n.kind === "page" || n.kind === "core" || n.kind === "hub") { x.fillStyle = col("--tx"); x.font = "500 12px Geist"; x.textAlign = "center"; x.fillText(n.label, n.x, n.y - n.r - 6); } }
    requestAnimationFrame(tick);
  })();
  const pos = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }, find = (px, py) => N.find((n) => (n.x - px) ** 2 + (n.y - py) ** 2 < (n.r + 6) ** 2);
  cv.onpointerdown = (e) => { const [px, py] = pos(e); drag = find(px, py); if (drag) { drag.fx = px; drag.fy = py; a = Math.max(a, 0.4); cv.setPointerCapture(e.pointerId); } };
  cv.onpointermove = (e) => { const [px, py] = pos(e); if (drag) { drag.fx = px; drag.fy = py; a = Math.max(a, 0.3); } hov = find(px, py);
    if (hov) { tip.style.display = "block"; tip.style.left = Math.min(innerWidth - 330, e.clientX + 12) + "px"; tip.style.top = e.clientY + 12 + "px"; tip.innerHTML = `<div class="mut" style="font-size:11.5px">${{ core: "Shared brain", page: "Page", lesson: "Lesson", auto: "Mistake the reviewer caught", hub: "Learning", learned: "Learned from a repo or file", video: "Video · " + (hov.status || "") }[hov.kind]}</div>${esc(hov.label)}`; } else tip.style.display = "none"; };
  cv.onpointerup = () => { if (drag && drag !== core) { if (drag.pin) { drag.fx = drag.pin[0]; drag.fy = drag.pin[1]; } else drag.fx = drag.fy = null; } drag = null; }; cv.onpointerleave = () => { tip.style.display = "none"; hov = null; };
}

/* ---------- published: one feed of every post (20 Nov) ---------- */
let pubData = null, pubCh = "all", pubPl = "all", pubSig = "", pubAt = 0;
async function loadPublished(force) {
  if (!pubData || force || Date.now() - pubAt > 600000) {
    try { pubData = await (await fetch("/api/published")).json(); pubAt = Date.now(); } catch (e) { if (!pubData) pubData = { rows: [], error: e.message }; }
  }
  drawPublished();
}
setInterval(() => { if (page() === "published" && document.visibilityState === "visible") loadPublished(0); }, 60000);
function drawPublished() {
  const g = $("#pubGrid"); if (!g || !pubData) return;
  const sig = JSON.stringify([pubCh, pubPl, pubData.t, (pubData.rows || []).length]);
  if (sig === pubSig) return;                     // nothing new: leave the grid (and its loaded images) alone
  pubSig = sig;
  const rows = (pubData.rows || []).filter((r) => (pubCh === "all" || r.cid === pubCh) && (pubPl === "all" || r[pubPl]));
  const t = pubData.totals || {};
  $("#pubTot").innerHTML = `<div><div class="lbl">Posts</div><div class="val">${nf(t.posts)}</div><div class="dl">last 80</div></div>
    <div><div class="lbl">Views</div><div class="val">${nf(t.views)}</div><div class="dl">IG + FB + YouTube</div></div>
    <div><div class="lbl">Likes</div><div class="val">${nf(t.likes)}</div><div class="dl">IG + YouTube</div></div>
    <div><div class="lbl">Campaign clips</div><div class="val">${nf(t.campaign)}</div><div class="dl">${nf(t.submitted)} submitted for pay</div></div>
    <div><div class="lbl">Updated</div><div class="dl" style="margin-top:8px">${pubData.t ? ago(pubData.t) : "—"} · <a href="javascript:loadPublished(1)">refresh</a></div></div>`;
  $("#pubTabs").innerHTML = [["all", "All"], ["ig", "Instagram"], ["fb", "Facebook"], ["yt", "YouTube"]].map(([k, l]) => `<button class="${pubPl === k ? "on" : ""}" onclick="pubPl='${k}';drawPublished()">${l}</button>`).join("");
  const ids = [...new Set((pubData.rows || []).map((r) => r.cid))];
  $("#pubCh").innerHTML = `<option value="all">All pages</option>` + ids.map((i) => `<option value="${i}" ${pubCh === i ? "selected" : ""}>${esc(ch(i).name)}</option>`).join("");
  const pl = (r, k, label, url, nums) => r[k] ? `<a class="badge" style="--c:${url ? "var(--green)" : "var(--gray)"}" href="${esc(url || "#")}" target="_blank">${label}${nums ? " · " + nums : ""}</a>`
    : r.errors && r.errors[k] ? `<span class="badge" style="--c:var(--red)" title="${esc(r.errors[k])}">${label} failed</span>` : "";
  g.innerHTML = rows.map((r) => {
    const c = ch(r.cid);
    const camp = r.campaign ? (r.submitted ? `<span class="badge" style="--c:var(--green)">Submitted ${esc(r.submitted.slice(5))}</span>` : `<span class="badge" style="--c:var(--amber)">Submit ${r.submit_ok}/${r.submit_n}</span>`) : "";
    return `<div class="card pubcard">
      <div class="pubthumb" onclick="openJob('${r.cid}','${r.job}')">${r.cover ? `<img src="${r.cover}" loading="lazy" decoding="async" alt="" onload="this.classList.add('ld')">` : ""}</div>
      <div class="pubbody"><div style="display:flex;gap:8px;align-items:center">${dp(c, 20)}<span class="mut" style="font-size:12px">${esc(c.name)} · ${esc((r.at || "").slice(5))}</span></div>
      <div class="t" style="margin-top:6px;white-space:normal;line-height:1.3">${esc(r.title)}</div>
      <div class="chips" style="margin-top:8px">
        ${pl(r, "ig", "IG", r.ig_url, [r.ig_views != null ? nf(r.ig_views) + " views" : "", r.likes != null ? nf(r.likes) + " ♥" : ""].filter(Boolean).join(" "))}
        ${pl(r, "fb", "FB", r.fb_url, r.fb_views != null ? nf(r.fb_views) + " views" : "")}
        ${pl(r, "yt", "YT", r.yt_url, r.yt_views != null ? nf(r.yt_views) + " views" : "")}
        ${camp}</div></div></div>`;
  }).join("") || `<div class="card empty">${pubData.error ? "Could not load: " + esc(pubData.error) : "Nothing posted yet for this filter."}</div>`;
}
async function loadRadar() {
  const el = $("#radar"); if (!el) return;
  const days = await (await fetch("/api/radar")).json();
  if (!days.length) { el.innerHTML = `<div class="empty">The first scan runs at 06:30. Nothing yet.</div>`; return; }
  const act = { learn_repo: "Learner reads it", add_to_brain: "Added to the brain", build: "On the build list", owner_signup: "Needs a free sign-up (optional)", watch: "Watching" };
  el.innerHTML = days.map((d) => `<div class="row" style="background:var(--sub)"><b>${esc(d.day)}</b><span class="mut" style="font-size:12.5px">${d.scanned} items scanned · ${d.new} new · ${(d.picks || []).length} picked</span></div>` +
    ((d.picks || []).map((p) => `<div class="row" style="align-items:flex-start">
      <span class="badge" style="--c:${p.score >= 8 ? "var(--green)" : p.score >= 7 ? "var(--teal)" : "var(--gray)"};min-width:44px;justify-content:center">${p.score}/10</span>
      <div class="grow"><div class="t" style="white-space:normal"><a href="${esc(p.url)}" target="_blank">${esc(p.name)}</a> <span class="faint" style="font-weight:400">· ${esc(p.src)}</span></div>
      <div class="s" style="white-space:normal">${esc(p.what || "")}</div>
      <div style="font-size:12.5px;margin-top:3px;white-space:normal"><b>For us:</b> ${esc(p.why || "")}</div>
      <div class="s" style="white-space:normal"><b>Free:</b> ${esc(p.free || "")} · effort ${esc(p.effort || "")}${p.risk ? " · careful: " + esc(p.risk) : ""}</div></div>
      <span class="mut" style="font-size:12px;white-space:nowrap">${esc(p.done || act[p.action] || "")}</span></div>`).join("") || `<div class="row mut">Nothing worth adding that day.</div>`)).join("");
}
async function loadLearned() {
  const el = $("#learned"); if (!el) return;
  const d = await (await fetch("/api/learned")).json(), s = d.stats || {};
  el.innerHTML = `<div class="strip" style="margin:0;border:0;box-shadow:none"><div><div class="lbl">In the brain</div><div class="val">${s.active ?? 0}</div><div class="dl">${s.items ?? 0} stored · no size limit</div></div>
   <div><div class="lbl">To build</div><div class="val">${d.build_open}</div><div class="dl">${d.build_done} built</div></div>
   <div><div class="lbl">Retired</div><div class="val">${s.retired ?? 0}</div><div class="dl">kept losing in reviews</div></div>
   <div><div class="lbl">Sources read</div><div class="val">${d.learned.length}</div><div class="dl">repos and files</div></div>
   <div><div class="lbl">Areas</div><div class="dl" style="margin-top:8px">${Object.entries(s.areas || {}).map(([k, v]) => `${esc(k)} ${v}`).join(" · ") || "—"}</div></div></div>
   ${d.learned.map((x) => `<div class="row" style="align-items:flex-start"><i class="dot" style="--c:${x.verdict === "useful" ? "var(--green)" : x.verdict === "some" ? "var(--blue)" : "var(--gray)"};margin-top:6px"></i>
     <div class="grow"><div class="t" style="white-space:normal">${x.url.startsWith("http") ? `<a href="${esc(x.url)}" target="_blank">${esc(x.name)}</a>` : esc(x.name)} <span class="faint" style="font-weight:400">· ${esc(x.t)}</span></div>
     <div class="s" style="white-space:normal">${esc(x.summary || x.skip || "")}</div>
     ${x.items && x.items.length ? `<div class="chips" style="margin-top:6px">${x.items.map((i) => `<span class="badge" style="--c:${i.kind === "build" ? "var(--violet)" : "var(--teal)"}">${esc(i.title)}</span>`).join("")}</div>` : ""}</div>
     <span class="mut num" style="white-space:nowrap">+${x.knowledge}${x.build ? ` · ${x.build} build` : ""}</span></div>`).join("") || `<div class="empty">Nothing learned yet. Send a GitHub link or a PDF in Studio360.</div>`}`;
}
/* ---------- actions ---------- */
async function decide(cid, job, action) { try { await post("/api/decide", { cid, job, action }); toast(action === "approve" ? "Approved" : action === "remove" ? "Removed" : "Rejected"); if (drawerKey) closeDrawer(); load(); } catch (e) { toast("Failed: " + e.message); } }
function feedback(cid, job) {
  drawerKey = "fb"; $("#drawer").classList.add("on");
  $("#panel").innerHTML = `<div class="ph"><div style="flex:1;font-weight:600">Feedback</div><button class="icon-btn" onclick="closeDrawer()">${ic("x")}</button></div><div class="pb"><div class="mut">Saved as a lesson for this page; the video is marked for a fix.</div><textarea id="fb" rows="6" style="margin-top:10px" placeholder="What should change?"></textarea><div style="display:flex;gap:8px;margin-top:10px"><button class="btn pri" onclick="sendFb('${cid}','${job}')">Send</button><button class="btn" onclick="closeDrawer()">Cancel</button></div></div>`;
  setTimeout(() => $("#fb").focus(), 40);
}
async function sendFb(cid, job) { const note = $("#fb").value.trim(); if (!note) return; try { await post("/api/decide", { cid, job, action: "fix", note }); clearDraft("fb"); closeDrawer(); toast("Feedback saved"); load(); } catch (e) { toast("Failed: " + e.message); } }
async function changeRun(cid, job, action) {
  const to = ($("#chTo") || {}).value || cid, topic = (($("#chTopic") || {}).value || "").trim(), name = (ch(to) || {}).name || to;
  if (!confirm(action === "stop" ? "Stop this run? It will be marked cancelled." : `Make "${topic.slice(0, 80)}" on ${name}?` + (to !== cid ? " This run will be cancelled." : ""))) return;
  try { const r = await post("/api/change", { cid, job, action, to, topic }); toast(action === "stop" ? "Stopped" : "Started on " + name); clearDraft("chTopic", "chTo"); closeDrawer(); setTimeout(load, 3000); } catch (e) { toast("Failed: " + e.message); }
}
async function addSource() {
  try {
    const r = await post("/api/source", { campaign_url: $("#srcU").value.trim(), channels: $("#srcC").value.trim(), rules: $("#srcR").value,
      caption_add: $("#srcT").value.trim(), no_watermark: $("#srcW").checked });
    toast("Added " + r.key + ", clipping starts"); clearDraft("srcU", "srcC", "srcR", "srcT"); ["#srcU", "#srcC", "#srcR", "#srcT"].forEach((s) => ($(s).value = "")); setTimeout(load, 2000);
  } catch (e) { toast("Failed: " + e.message); }
}
async function makeNow() { try { await post("/api/make", { cid: $("#mkc").value, topic: $("#mkt").value.trim() }); toast("Started"); clearDraft("mkt"); $("#mkt").value = ""; setTimeout(load, 3000); } catch (e) { toast("Failed: " + e.message); } }
async function setS(b) { try { S.settings = await post("/api/settings", b); render(1); toast("Saved"); } catch (e) { toast("Failed: " + e.message); } }
async function resetFailed() { await post("/api/reset-failed", {}); toast("Cleared"); load(); }
async function doneTask(id) { await post("/api/task", { id, done: true }); toast("Marked done"); load(); }
async function testSrc(n) { toast("Testing…"); const r = await post("/api/test", { name: n }); toast((r.ok ? "Working: " : "Problem: ") + r.detail); loadSources(); }
async function loadBrief(force) {
  if (force) { briefCache = { headline: "", lines: [] }; render(1); }
  try { briefCache = await (await fetch("/api/brief" + (force ? "?force=1" : ""))).json(); } catch (e) { briefCache = { error: e.message }; }
  render(1);
  if (briefCache.t && Date.now() / 1000 - briefCache.t > 1800) setTimeout(() => loadBrief(0), 30000);      // the server is rewriting a stale brief: pick it up
}
async function loadSources() { try { srcCache = await (await fetch("/api/sources")).json(); } catch (e) {} if (page() === "sources") render(1); }
function toggleTheme() { const h = document.documentElement; h.dataset.theme = h.dataset.theme === "dark" ? "light" : "dark"; localStorage.theme = h.dataset.theme; document.querySelector('meta[name=theme-color]').content = h.dataset.theme === "dark" ? "#0a0a0a" : "#fafafa"; render(1); }

/* ---------- render loop ---------- */
const page = () => { const t = location.hash.slice(1); return V[t] ? t : "today"; };
function render(force) {
  if (!S) return;
  const p = page(), wait = (S.queue || S.jobs).filter((j) => ["waiting", "ready"].includes(j.status)).length, bad = S.issues.filter((i) => i.lvl === "bad").length, warn = S.issues.filter((i) => i.lvl === "warn").length;
  const cnt = { approvals: wait ? [wait, "v"] : null, server: bad ? [bad, "r"] : warn ? [warn, "a"] : null, runs: S.jobs.filter((j) => j.active).length ? [S.jobs.filter((j) => j.active).length, ""] : null };
  $("#nav").innerHTML = NAV.map(([g, it]) => (g ? `<div class="ng">${g}</div>` : `<div style="height:6px"></div>`) + it.map(([k, t]) => `<a href="#${k}" class="${k === p ? "on" : ""}">${ic(ICON[k])}${t}${cnt[k] ? `<span class="c ${cnt[k][1]}">${cnt[k][0]}</span>` : ""}</a>`).join("")).join("");
  $("#tabbar").innerHTML = [["today", "Today"], ["published", "Posted"], ["approvals", "Approve"], ["channels", "Channels"], ["server", "Server"], ["more", "More"]].map(([k, t]) => `<a href="${k === "more" ? "javascript:moreMenu()" : "#" + k}" class="${k === p ? "on" : ""}">${ic(ICON[k] || "more")}${t}${cnt[k] ? `<span class="c">${cnt[k][0]}</span>` : ""}</a>`).join("");
  const label = NAV.flatMap(([, it]) => it).find(([k]) => k === p)?.[1] || "Today";
  $("#crumb").innerHTML = `<span class="mut hide-m">Studio /</span>${esc(label)}`;
  if (p === "brain") { if (force || !$("#brainc")) { $("#view").innerHTML = V.brain(); prev = ""; startBrain(); } return; }
  // 20 Nov (owner: "posted tab refreshes every 3 sec, thumbnails reload"): the 4 s loop rebuilt the whole grid. The
  // Published page is drawn once; its numbers update in place every 10 min, and only when they changed
  if (p === "published") { if (!$("#pubGrid")) { $("#view").innerHTML = V.published(); prev = ""; pubSig = ""; loadPublished(0); } return; }
  const html = V[p]();
  if (force || html !== prev) { const a = document.activeElement, y = scrollY, keep = drafts($("#view")); $("#view").innerHTML = html; prev = html; restoreDrafts($("#view"), keep); scrollTo(0, y); if (a && a.id && $("#" + a.id)) $("#" + a.id).focus(); }
}
/* 19 Nov (owner: "I was writing a topic, it auto reloaded and my typed thing vanished"): the 4 s refresh rebuilt the view
   and every box came back empty. Typed text and chosen options survive every redraw (and a page reload, sessionStorage). */
const DRAFT = "studio-drafts";
function drafts(root) {
  const d = JSON.parse(sessionStorage.getItem(DRAFT) || "{}");
  (root || document).querySelectorAll("input[id],textarea[id],select[id]").forEach((el) => { if (el.type !== "checkbox" && el.type !== "radio") d[el.id] = el.value; });
  return d;
}
function restoreDrafts(root, d) {
  (root || document).querySelectorAll("input[id],textarea[id],select[id]").forEach((el) => {
    if (d[el.id] != null && d[el.id] !== "" && el.type !== "checkbox" && el.type !== "radio") el.value = d[el.id];
  });
}
function clearDraft(...ids) { const d = JSON.parse(sessionStorage.getItem(DRAFT) || "{}"); ids.forEach((i) => delete d[i]); sessionStorage.setItem(DRAFT, JSON.stringify(d)); }
document.addEventListener("input", (e) => { const el = e.target; if (el && el.id && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) { const d = JSON.parse(sessionStorage.getItem(DRAFT) || "{}"); d[el.id] = el.value; sessionStorage.setItem(DRAFT, JSON.stringify(d)); } });
document.addEventListener("change", (e) => { const el = e.target; if (el && el.id && el.tagName === "SELECT") { const d = JSON.parse(sessionStorage.getItem(DRAFT) || "{}"); d[el.id] = el.value; sessionStorage.setItem(DRAFT, JSON.stringify(d)); } });
function moreMenu() {
  drawerKey = "more"; $("#drawer").classList.add("on");
  $("#panel").innerHTML = `<div class="ph"><div style="flex:1;font-weight:600">More</div><button class="icon-btn" onclick="closeDrawer()">${ic("x")}</button></div><div>${[["runs", "Runs"], ["sources", "Connected apps"], ["activity", "Activity log"], ["brain", "Brain"], ["settings", "Settings"]].map(([k, t]) => `<a class="row click" href="#${k}" onclick="closeDrawer()">${ic(ICON[k])}<span class="grow">${t}</span></a>`).join("")}<a class="row click" href="javascript:closeDrawer();openPalette()">${ic("spark")}<span class="grow">Ask a question</span></a></div>`;
}
async function load() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" }); if (!r.ok) throw 0; S = await r.json(); fails = 0;
    $("#sync").innerHTML = `<i class="dot live"></i><span>Live · ${new Date(S.now * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>`;
    const ae = document.activeElement; if (ae && /^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName) && ($("#view").contains(ae) || $("#panel").contains(ae))) return; render();
  } catch (e) { if (++fails > 1) $("#sync").innerHTML = `<i class="dot" style="--c:var(--red)"></i><span>Offline · retrying</span>`; }
}
addEventListener("hashchange", () => { prev = ""; scrollTo(0, 0); closeDrawer(); render(1); if (page() === "sources") loadSources(); });
load().then(() => { loadBrief(0); loadSources(); }); setInterval(() => !document.hidden && loadBrief(0), 300000); setInterval(() => !document.hidden && load(), 4000); setInterval(() => !document.hidden && loadSources(), 60000);
