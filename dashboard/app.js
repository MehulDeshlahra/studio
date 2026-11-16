/* Studio dashboard. Live data from /api/state every 4 s. Colour = meaning only. */
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const K = { green: "var(--green)", amber: "var(--amber)", red: "var(--red)", blue: "var(--blue)", violet: "var(--violet)", teal: "var(--teal)", gray: "var(--gray)" };
const ST = {
  building: ["Building", K.blue, 1], prepped: ["Prepped", K.blue], waiting: ["Needs approval", K.violet], ready: ["Ready, not sent", K.violet],
  approved: ["Approved", K.teal], posted: ["Posted", K.green], held: ["Held by review", K.amber], rejected: ["Rejected", K.red], paused: ["Stopped midway", K.gray], made: ["Made", K.gray],
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
  ["", [["today", "Today"], ["runs", "Runs"], ["approvals", "Approvals"]]],
  ["Channels", [["channels", "All channels"]]],
  ["System", [["server", "Server"], ["sources", "Connected apps"], ["activity", "Activity log"]]],
  ["Knowledge", [["brain", "Brain"]]],
  ["", [["settings", "Settings"]]],
];
const ICON = { today: "today", runs: "runs", approvals: "approve", channels: "channels", server: "server", sources: "sources", activity: "activity", brain: "brain", settings: "settings" };
let S = null, prev = "", runFilter = "all", runCh = "all", logQ = "", logLvl = "all", fails = 0, srcCache = null, briefCache = null, drawerKey = null;

/* ---------- format ---------- */
const nf = (x) => (x == null ? "—" : x >= 1e5 ? (x / 1e5).toFixed(1).replace(".0", "") + "L" : x >= 1e4 ? (x / 1000).toFixed(1).replace(".0", "") + "k" : Number(x).toLocaleString("en-IN"));
const now = () => (S ? S.now : Date.now() / 1000);
const ago = (t) => { if (!t) return "—"; const d = Math.max(0, now() - t); return d < 60 ? "just now" : d < 3600 ? `${(d / 60) | 0} min ago` : d < 86400 ? `${(d / 3600) | 0} h ago` : `${(d / 86400) | 0} d ago`; };
const dur = (s) => (s == null ? "—" : s < 60 ? `${s | 0}s` : s < 3600 ? `${(s / 60) | 0}m ${String(s % 60 | 0).padStart(2, "0")}s` : `${(s / 3600) | 0}h ${String(((s % 3600) / 60) | 0).padStart(2, "0")}m`);
const inT = (s) => (s == null ? "—" : s <= 0 ? "now" : s < 3600 ? `in ${Math.ceil(s / 60)} min` : `in ${(s / 3600) | 0} h ${((s % 3600) / 60) | 0} m`);
const ch = (id) => (S?.channels || []).find((c) => c.id === id) || { name: id, color: "#737373" };
const badge = (k) => { const [t, c, run] = ST[k] || [k, K.gray]; return `<span class="badge ${run ? "run" : ""}" style="--c:${c}"><i class="dot"></i>${t}</span>`; };
const lvlBadge = (l, t) => `<span class="badge" style="--c:${LV[l] || K.gray}"><i class="dot"></i>${esc(t)}</span>`;
const meter = (p, c) => `<div class="meter" style="--c:${c}"><i style="width:${Math.max(2, Math.min(100, p))}%"></i></div>`;
const thr = (v, w, b) => (v >= b ? K.red : v >= w ? K.amber : K.green);
const seg = (j) => `<div class="seg">${j.steps.map((s) => `<i class="${s.done ? "d" : s.active ? "a" : ""}" title="${esc(s.label)}"></i>`).join("")}</div>`;
const curStep = (j) => (j.steps.find((s) => s.active) || {}).label;
function toast(t) { const e = $("#toast"); e.textContent = t; e.classList.add("on"); clearTimeout(e._t); e._t = setTimeout(() => e.classList.remove("on"), 2200); }
async function post(u, b) { const r = await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }); const j = await r.json(); if (!r.ok) throw new Error(j.error || r.status); return j; }

function chart(hist, key, color, max = 100, unit = "%") {
  if (!hist || hist.length < 3) return `<div class="empty">Collecting…</div>`;
  const w = 600, h = 120, n = hist.length, y = (v) => h - 4 - (Math.min(v, max) / max) * (h - 12);
  const d = hist.map((p, i) => `${i ? "L" : "M"}${((i / (n - 1)) * w).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(" ");
  const last = hist[n - 1][key];
  return `<div style="display:flex;justify-content:space-between;align-items:baseline"><span class="lbl">${key === "cpu" ? "CPU" : key === "mem" ? "Memory" : "Load"}</span><span class="num" style="font-weight:600">${last}${unit}</span></div>
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
   <div class="top"><span class="sq" style="--c:${c.color}"></span><div class="grow" style="min-width:0;flex:1"><div class="t" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(j.title)}</div>
   <div class="s mut">${esc(c.name)} · ${j.lang === "en" ? "English" : "Hindi"}</div></div>${badge(j.status)}</div>
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
    const wait = S.jobs.filter((j) => ["waiting", "ready"].includes(j.status)).length, appr = S.jobs.filter((j) => j.status === "approved").length;
    const today = d.toISOString().slice(0, 10), made = S.activity.filter((a) => a.t.startsWith(today) && /rendered in/.test(a.msg)).length;
    const bad = S.issues.filter((i) => i.lvl === "bad").length, warn = S.issues.filter((i) => i.lvl === "warn").length;
    const s = S.server, b = briefCache;
    return `<div class="h1">${d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}</div>
    <div class="lead">${esc(S.doing)}.</div>
    <div class="card strip">
     <div><div class="lbl">Followers</div><div class="val">${nf(fol)}</div><div class="dl">6 channels · Instagram + Facebook</div></div>
     <div><div class="lbl"><i class="dot" style="--c:${K.violet}"></i>Needs approval</div><div class="val">${wait}</div><div class="dl">${appr} approved, waiting for a slot</div></div>
     <div><div class="lbl">Rendered today</div><div class="val">${made}</div><div class="dl">${S.budgets.map((x) => `${x.name.split(" ")[0]} ${x.used}/${x.cap}`).join(" · ")}</div></div>
     <div><div class="lbl"><i class="dot" style="--c:${act.length ? K.blue : K.gray}"></i>Building</div><div class="val">${act.length}</div><div class="dl">typical render ${dur(S.render_median)}</div></div>
     <div><div class="lbl"><i class="dot" style="--c:${bad ? K.red : warn ? K.amber : K.green}"></i>Health</div><div class="val">${bad ? bad + " <small>to fix</small>" : warn ? warn + " <small>to watch</small>" : "OK"}</div><div class="dl">CPU ${Math.round(s.cpu)}% · disk ${Math.round(s.disk_pct)}%</div></div>
    </div>
    <div class="cols" style="margin-top:16px">
     <div>
      <div class="card brief"><div class="hd">${ic("spark")}<span>Brief</span><span class="faint">${b && b.t ? "written " + ago(b.t) : ""}</span><button class="btn sm" style="margin-left:auto" onclick="loadBrief(1)">${ic("refresh")}Refresh</button></div>
       ${b && b.headline ? `<div class="hl">${esc(b.headline)}</div><ul>${(b.lines || []).map((l) => `<li>${esc(l)}</li>`).join("")}</ul>` : `<div class="mut" style="margin-top:8px">${b && b.error ? "Could not write the brief: " + esc(b.error) : "Writing the brief…"}</div>`}</div>
      <div class="sec"><h3>Needs you</h3><span class="mut">${S.needs.length}</span></div>
      <div class="card">${S.needs.map(needRow).join("") || `<div class="empty">Nothing needs you right now.</div>`}</div>
      <div class="sec"><h3>Building now</h3><a class="r mut" href="#runs">All runs →</a></div>
      <div class="card">${act.map(runRow).join("") || `<div class="empty">Idle. Next: ${esc(S.schedule[0]?.name || "—")} ${inT(S.schedule[0]?.in)}.</div>`}</div>
     </div>
     <div>
      <div class="sec" style="margin-top:0"><h3>Server</h3><a class="r mut" href="#server">Details →</a></div>
      <div class="card pad">${[["CPU", s.cpu, thr(s.cpu, 80, 95), `${Math.round(s.cpu)}%`], ["Memory", s.mem_pct, thr(s.mem_pct, 80, 92), `${s.mem_used_gb} / ${s.mem_total_gb} GB`], ["Disk", s.disk_pct, thr(s.disk_pct, 85, 93), `${s.disk_free_gb} GB free`], ["Load", (s.load[0] / (s.cores * 3)) * 100, thr(s.load[0] / s.cores, 2, 3.5), `${s.load[0]} on ${s.cores} cores`]]
        .map(([l, v, c, t]) => `<div style="margin-top:10px"><div style="display:flex;justify-content:space-between;font-size:12.5px"><span class="mut">${l}</span><span class="num">${t}</span></div><div style="margin-top:5px">${meter(v, c)}</div></div>`).join("").replace('margin-top:10px', 'margin-top:0')}</div>
      <div class="sec"><h3>Issues</h3><span class="mut">${S.issues.length}</span></div>
      <div class="card">${S.issues.slice(0, 5).map(issueRow).join("") || `<div class="empty">No issues.</div>`}${S.issues.length > 5 ? `<a class="row mut" href="#server">${S.issues.length - 5} more →</a>` : ""}</div>
      <div class="sec"><h3>Coming up</h3></div>
      <div class="card">${S.schedule.map((t) => `<div class="row"><i class="dot ${t.running ? "live" : ""}" style="--c:${t.running ? K.blue : K.gray}"></i><div class="grow"><div class="t">${esc(t.name)}</div><div class="s">${t.last ? "last ran " + ago(t.last) : "not run yet"}</div></div><span class="num mut">${t.running ? "running" : inT(t.in)}</span></div>`).join("")}</div>
     </div>
    </div>`;
  },
  runs() {
    const F = [["all", "All"], ["active", "Building"], ["need", "Needs you"], ["held", "Held"], ["approved", "Approved"], ["posted", "Posted"], ["rejected", "Rejected"]];
    const ok = (j) => runFilter === "all" || (runFilter === "active" ? j.active : runFilter === "need" ? ["waiting", "ready"].includes(j.status) : j.status === runFilter);
    const list = S.jobs.filter((j) => ok(j) && (runCh === "all" || j.cid === runCh));
    return `<div class="h1">Runs</div><div class="lead">Every video the engine has made or is making. Click a row for the full timeline, review and log.</div>
    <div class="tools"><div class="tabs">${F.map(([k, t]) => `<button class="${runFilter === k ? "on" : ""}" onclick="runFilter='${k}';render(1)">${t} <span class="faint">${S.jobs.filter((j) => k === "all" || (k === "active" ? j.active : k === "need" ? ["waiting", "ready"].includes(j.status) : j.status === k)).length}</span></button>`).join("")}</div>
     <select onchange="runCh=this.value;render(1)"><option value="all">All pages</option>${S.channels.filter((c) => c.group === "Studio").map((c) => `<option value="${c.id}" ${runCh === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div>
    <div class="card tw" style="margin-top:12px"><table><thead><tr><th>Status</th><th>Video</th><th class="hide-m">Page</th><th>Progress</th><th class="hide-m">Review</th><th class="hide-m">Updated</th></tr></thead><tbody>
    ${list.map((j) => { const c = ch(j.cid); return `<tr class="click" onclick="openJob('${j.cid}','${j.job}')"><td>${badge(j.status)}</td>
      <td><div class="tt">${esc(j.title)}</div><div class="mono faint">${esc(j.job)} · ${j.lang === "en" ? "EN" : "HI"}</div></td>
      <td class="hide-m"><span style="display:flex;gap:8px;align-items:center"><span class="sq" style="--c:${c.color}"></span>${esc(c.name)}</span></td>
      <td style="min-width:170px">${seg(j)}<div class="mono faint" style="margin-top:4px">${j.active ? esc(curStep(j) || "") + " · " : ""}${Math.round(j.pct * 100)}%</div></td>
      <td class="hide-m">${j.review.ok === true ? `<span class="up">Passed</span>${j.review.score ? ` · ${j.review.score}/10` : ""}` : j.review.ok === false ? `<span class="dn">${(j.review.problems || []).length} problems</span>` : `<span class="faint">—</span>`}</td>
      <td class="hide-m mut">${ago(j.updated)}</td></tr>`; }).join("") || `<tr><td colspan="6" class="empty">No runs here.</td></tr>`}</tbody></table></div>`;
  },
  approvals() {
    const w = S.jobs.filter((j) => ["waiting", "ready"].includes(j.status)), held = S.jobs.filter((j) => j.status === "held"), ap = S.jobs.filter((j) => j.status === "approved");
    const card = (j) => { const c = ch(j.cid), base = `/media/${j.cid}/${j.job}/`;
      return `<div class="card pad"><div class="media"><div class="cover" onclick="openJob('${j.cid}','${j.job}')">${j.files["cover.jpg"] ? `<img loading="lazy" src="${base}cover.jpg?v=${j.updated}">` : ""}<span class="pl">${ic("play")}${j.qc.dur ? Math.round(j.qc.dur) + "s" : "Play"}</span></div>
       <div style="min-width:0"><div style="display:flex;gap:8px;align-items:center"><span class="sq" style="--c:${c.color}"></span><span class="mut">${esc(c.name)} · ${j.lang === "en" ? "English" : "Hindi"}</span><span style="margin-left:auto">${badge(j.status)}</span></div>
       <div style="font-weight:600;font-size:14.5px;margin-top:6px">${esc(j.title)}</div>
       <div class="chips" style="margin-top:8px">${j.review.ok ? lvlBadge("ok", "Passed review") : ""}${j.review.score ? lvlBadge(j.review.score >= 8 ? "ok" : "warn", `Visual ${j.review.score}/10`) : ""}${j.qc.lufs ? lvlBadge("info", `${j.qc.lufs} LUFS`) : ""}</div>
       ${(j.review.problems || []).length ? `<ul class="mut" style="margin:8px 0 0 16px;font-size:12.5px">${j.review.problems.slice(0, 3).map((p) => `<li>${esc(String(p).slice(0, 160))}</li>`).join("")}</ul>` : ""}
       ${["waiting", "ready", "held"].includes(j.status) ? `<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><button class="btn ok" onclick="decide('${j.cid}','${j.job}','approve')">Approve</button><button class="btn no" onclick="decide('${j.cid}','${j.job}','reject')">Reject</button><button class="btn" onclick="feedback('${j.cid}','${j.job}')">Feedback</button></div>` : ""}
       </div></div></div>`; };
    return `<div class="h1">Approvals</div><div class="lead">Only videos that passed the server's review come here. Approving here or in Telegram does the same thing.${S.settings.auto_approve ? ` Auto-approve is on for scores of ${S.settings.min_score}/10 and up.` : ""}</div>
     <div class="sec"><i class="dot" style="--c:${K.violet}"></i><h3>Needs approval</h3><span class="mut">${w.length}</span></div><div class="g2">${w.map(card).join("") || `<div class="card empty">Nothing is waiting for you.</div>`}</div>
     ${held.length ? `<div class="sec"><i class="dot" style="--c:${K.amber}"></i><h3>Held by review</h3><span class="mut">${held.length} · not sent to Telegram</span></div><div class="g2">${held.map(card).join("")}</div>` : ""}
     ${ap.length ? `<div class="sec"><i class="dot" style="--c:${K.teal}"></i><h3>Approved, waiting for a slot</h3><span class="mut">${ap.length}</span></div><div class="g2">${ap.map(card).join("")}</div>` : ""}`;
  },
  channels() {
    const row = (c) => { const cnt = c.counts || {}, st = { live: ["Live", "ok"], warm: ["Warm-up", "warn"], off: ["Off", "info"], manual: ["Manual", "info"] }[c.status];
      return `<tr class="click" onclick="openChannel('${c.id}')"><td><span style="display:flex;gap:10px;align-items:center"><span class="sq" style="--c:${c.color};width:12px;height:12px"></span><span><div style="font-weight:500">${esc(c.name)}</div><div class="faint" style="font-size:12px">@${esc(c.ig)}</div></span></span></td>
      <td>${lvlBadge(st[1], st[0])}<div class="faint" style="font-size:12px;margin-top:3px">${esc(c.note)}</div></td><td class="num">${nf(c.igF)}</td><td class="num hide-m">${nf(c.fb)}</td><td class="num hide-m">${nf(c.posts)}</td>
      <td class="hide-m">${Object.entries(cnt).filter(([, v]) => v).map(([k, v]) => `<span class="mut" style="margin-right:10px">${v} ${(ST[k] || [k])[0].toLowerCase()}</span>`).join("") || `<span class="faint">—</span>`}</td><td class="hide-m">${spark(c.spark, c.color)}</td></tr>`; };
    const st = S.channels.filter((c) => c.group === "Studio"), bz = S.channels.filter((c) => c.group !== "Studio");
    const head = `<thead><tr><th>Channel</th><th>Status</th><th>IG followers</th><th class="hide-m">FB followers</th><th class="hide-m">IG posts</th><th class="hide-m">Videos</th><th class="hide-m">30 days</th></tr></thead>`;
    return `<div class="h1">Channels</div><div class="lead">${S.channels.length} channels. Follower numbers come from Meta every 30 minutes. Click one for its latest posts.</div>
     <div class="sec"><h3>Studio pages</h3><span class="mut">made by the engine</span></div><div class="card tw"><table>${head}<tbody>${st.map(row).join("")}</tbody></table></div>
     <div class="sec"><h3>Businesses</h3></div><div class="card tw"><table>${head}<tbody>${bz.map(row).join("")}</tbody></table></div>
     <div class="sec"><h3>Make a video now</h3></div><div class="card pad"><div class="tools" style="margin:0"><select id="mkc">${st.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select><input id="mkt" type="text" placeholder="Topic (optional)" style="flex:1;min-width:200px"><button class="btn pri" onclick="makeNow()">Start</button></div><div class="mut" style="margin-top:8px;font-size:12.5px">Runs in the background and counts toward today's budget. It appears under Runs within a few seconds.</div></div>`;
  },
  server() {
    const s = S.server;
    return `<div class="h1">Server</div><div class="lead">Oracle Ampere · ${s.cores} cores · ${s.mem_total_gb} GB · up ${Math.round(s.uptime_h / 24)} days. Sampled every 5 seconds.</div>
     <div class="g3" style="margin-top:16px"><div class="card pad">${chart(s.hist, "cpu", "var(--blue)")}</div><div class="card pad">${chart(s.hist, "mem", "var(--violet)")}</div>
      <div class="card pad"><div class="lbl">Disk</div><div class="val">${Math.round(s.disk_pct)}%<small>${s.disk_free_gb} GB free of ${s.disk_total_gb}</small></div><div style="margin-top:10px">${meter(s.disk_pct, thr(s.disk_pct, 85, 93))}</div>
       <div class="lbl" style="margin-top:16px">Load (1 / 5 / 15 min)</div><div class="val num" style="font-size:18px">${s.load.join(" · ")}</div><div class="dl">${s.load[1] > s.cores * 3 ? "Overloaded: more work than cores" : s.load[1] > s.cores ? "Busy" : "Comfortable"}</div></div></div>
     <div class="sec"><h3>Issues</h3><span class="mut">${S.issues.length}</span></div><div class="card">${S.issues.map(issueRow).join("") || `<div class="empty">No issues.</div>`}</div>
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
     <div class="card" style="margin-top:12px">${L.map((a) => `<div class="row" style="align-items:flex-start;padding:8px 16px"><span class="mono faint" style="width:44px;padding-top:1px">${a.t.slice(11, 16)}</span><i class="dot" style="--c:${LV[a.lvl]};margin-top:6px"></i>${a.cid ? `<span class="sq" style="--c:${ch(a.cid).color};margin-top:5px" title="${esc(ch(a.cid).name)}"></span>` : `<span style="width:9px"></span>`}<span class="grow" style="word-break:break-word">${esc(a.msg)}</span></div>`).join("") || `<div class="empty">No lines match.</div>`}</div>`;
  },
  brain() {
    return `<div class="h1">Brain</div><div class="lead">What the engine has learned. Every page reads the shared lessons and every other page's lessons before it writes a script. Drag nodes; hover for the text.</div>
     <div class="card" style="margin-top:16px;overflow:hidden"><canvas id="brainc"></canvas><div class="leg"><span><i class="dot" style="--c:var(--ink)"></i>Shared brain</span>${S.channels.slice(0, 3).map((c) => `<span><span class="sq" style="--c:${c.color}"></span>${esc(c.name)}</span>`).join("")}<span><i class="dot" style="--c:var(--blue)"></i>Shared lesson</span><span><i class="dot" style="--c:var(--red)"></i>Mistake the reviewer caught</span><span><i class="dot" style="--c:var(--green)"></i>Video</span></div></div>`;
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
  const wf = d.timeline.map((r) => `<div class="r ${r.start == null ? "p" : ""}"><span>${esc(r.label)}</span><div class="tr">${r.start != null ? `<div class="b" style="--c:${r.active ? "var(--blue)" : "var(--green)"};left:${((r.start - t0) / (t1 - t0)) * 100}%;width:${(Math.max(r.dur || 0, 1) / (t1 - t0)) * 100}%"></div>` : ""}</div><span class="num mut" style="text-align:right">${r.start != null ? dur(r.dur) : "—"}</span></div>`).join("");
  const rv = d.review_full || {};
  $("#panel").innerHTML = `<div class="ph"><span class="sq" style="--c:${c.color};margin-top:6px"></span><div style="flex:1;min-width:0"><div style="font-weight:600;font-size:15px">${esc(d.title)}</div><div class="mut">${esc(c.name)} · ${d.lang === "en" ? "English" : "Hindi"} · <span class="mono">${esc(job)}</span></div></div>${badge(d.status)}<button class="icon-btn" onclick="closeDrawer()">${ic("x")}</button></div>
  <div class="pb">
   <div class="media"><div class="cover">${have ? `<video src="${base + vid}" poster="${d.files["cover.jpg"] ? base + "cover.jpg" : ""}" controls playsinline preload="none"></video>` : d.files["cover.jpg"] ? `<img src="${base}cover.jpg">` : `<div class="empty">No video yet</div>`}</div>
    <div><div class="kv"><span>Progress</span><span class="num">${Math.round(d.pct * 100)}%${d.active ? " · " + esc(curStep(d) || "") : ""}</span><span>Length</span><span>${d.qc.dur ? Math.round(d.qc.dur) + " s" : "—"}</span><span>Loudness</span><span>${d.qc.lufs ?? "—"} LUFS</span><span>Review</span><span>${d.review.ok === true ? `<span class="up">Passed</span>` : d.review.ok === false ? `<span class="dn">Held</span>` : "—"}${d.review.score ? ` · visual ${d.review.score}/10` : ""}</span><span>Updated</span><span>${ago(d.updated)}</span></div>
    ${["waiting", "ready", "held"].includes(d.status) ? `<div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap"><button class="btn ok" onclick="decide('${cid}','${job}','approve')">Approve</button><button class="btn no" onclick="decide('${cid}','${job}','reject')">Reject</button><button class="btn" onclick="feedback('${cid}','${job}')">Feedback</button></div>` : ""}</div></div>
   <h4>Timeline</h4><div class="wf">${wf}</div>
   ${(rv.problems || []).length || (rv.minor || []).length ? `<h4>Review</h4><ul style="padding-left:16px">${(rv.problems || []).map((p) => `<li class="dn">${esc(p)}</li>`).join("")}${(rv.minor || []).map((p) => `<li class="mut">${esc(p)}</li>`).join("")}</ul>` : ""}
   ${d.caption ? `<h4>Caption</h4><div style="white-space:pre-wrap">${esc(d.caption)}</div>` : ""}
   ${d.scenes.length ? `<h4>Script · ${d.scenes.length} scenes</h4><ol style="padding-left:18px">${d.scenes.map((s) => `<li style="margin-top:4px"><span class="faint mono">${esc(s.type)}</span> ${esc(s.vo)}</li>`).join("")}</ol>` : ""}
   <h4>Log</h4><div class="logs">${d.logs.map((l) => esc(l)).join("\n") || "No log lines for this run."}</div>
  </div>`;
}
async function openChannel(id) {
  const c = ch(id); drawerKey = "ch:" + id; $("#drawer").classList.add("on");
  const head = `<div class="ph"><span class="sq" style="--c:${c.color};margin-top:6px;width:12px;height:12px"></span><div style="flex:1"><div style="font-weight:600;font-size:15px">${esc(c.name)}</div><div class="mut">${esc(c.note)}</div></div><button class="icon-btn" onclick="closeDrawer()">${ic("x")}</button></div>`;
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
    r: n.kind === "core" ? 11 : n.kind === "page" ? 9 : n.kind === "video" ? 4.5 : 3.5,
    c: n.kind === "core" ? col("--ink") : n.kind === "page" ? n.color : n.kind === "auto" ? col("--red") : n.kind === "video" ? SC[n.status] || col("--gray") : n.cid ? n.color : col("--blue") }));
  const L = data.links.map((l) => ({ s: by[l.s], t: by[l.t] })).filter((l) => l.s && l.t); const core = by.brain; core.fx = W / 2; core.fy = H / 2;
  let drag = null, hov = null, a = 1; const tip = document.body.appendChild(Object.assign(document.createElement("div"), { className: "tip" }));
  (function tick() {
    if (!document.body.contains(cv)) { tip.remove(); return; }
    if (a > 0.01) {
      for (let i = 0; i < N.length; i++) for (let j = i + 1; j < N.length; j++) { const p = N[i], q = N[j]; let dx = q.x - p.x, dy = q.y - p.y, d2 = dx * dx + dy * dy + 0.01, d = Math.sqrt(d2), f = (600 * a) / d2; dx /= d; dy /= d; p.vx -= dx * f; p.vy -= dy * f; q.vx += dx * f; q.vy += dy * f; }
      for (const l of L) { const want = l.s.kind === "core" ? (l.t.kind === "page" ? 140 : 90) : 48; const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = ((d - want) / d) * 0.05 * a; l.s.vx += dx * f; l.s.vy += dy * f; l.t.vx -= dx * f; l.t.vy -= dy * f; }
      for (const n of N) { if (n.fx != null) { n.x = n.fx; n.y = n.fy; n.vx = n.vy = 0; continue; } n.vx += (W / 2 - n.x) * 0.002 * a; n.vy += (H / 2 - n.y) * 0.002 * a; n.vx *= 0.8; n.vy *= 0.8; n.x = Math.max(10, Math.min(W - 10, n.x + n.vx)); n.y = Math.max(10, Math.min(H - 10, n.y + n.vy)); }
      a *= 0.99;
    }
    x.clearRect(0, 0, W, H); x.lineWidth = 1;
    for (const l of L) { x.strokeStyle = hov && (hov === l.s || hov === l.t) ? col("--mut") : col("--line"); x.beginPath(); x.moveTo(l.s.x, l.s.y); x.lineTo(l.t.x, l.t.y); x.stroke(); }
    for (const n of N) { x.beginPath(); x.arc(n.x, n.y, n.r, 0, 7); if (n.kind === "video") { x.fillStyle = col("--panel"); x.fill(); x.strokeStyle = n.c; x.lineWidth = 2; x.stroke(); x.lineWidth = 1; } else { x.fillStyle = n.c; x.fill(); }
      if (n.kind === "page" || n.kind === "core") { x.fillStyle = col("--tx"); x.font = "500 12px Geist"; x.textAlign = "center"; x.fillText(n.label, n.x, n.y - n.r - 6); } }
    requestAnimationFrame(tick);
  })();
  const pos = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }, find = (px, py) => N.find((n) => (n.x - px) ** 2 + (n.y - py) ** 2 < (n.r + 6) ** 2);
  cv.onpointerdown = (e) => { const [px, py] = pos(e); drag = find(px, py); if (drag) { drag.fx = px; drag.fy = py; a = Math.max(a, 0.4); cv.setPointerCapture(e.pointerId); } };
  cv.onpointermove = (e) => { const [px, py] = pos(e); if (drag) { drag.fx = px; drag.fy = py; a = Math.max(a, 0.3); } hov = find(px, py);
    if (hov) { tip.style.display = "block"; tip.style.left = Math.min(innerWidth - 330, e.clientX + 12) + "px"; tip.style.top = e.clientY + 12 + "px"; tip.innerHTML = `<div class="mut" style="font-size:11.5px">${{ core: "Shared brain", page: "Page", lesson: "Lesson", auto: "Mistake the reviewer caught", video: "Video · " + (hov.status || "") }[hov.kind]}</div>${esc(hov.label)}`; } else tip.style.display = "none"; };
  cv.onpointerup = () => { if (drag && drag !== core) drag.fx = drag.fy = null; drag = null; }; cv.onpointerleave = () => { tip.style.display = "none"; hov = null; };
}

/* ---------- actions ---------- */
async function decide(cid, job, action) { try { await post("/api/decide", { cid, job, action }); toast(action === "approve" ? "Approved" : "Rejected"); if (drawerKey) closeDrawer(); load(); } catch (e) { toast("Failed: " + e.message); } }
function feedback(cid, job) {
  drawerKey = "fb"; $("#drawer").classList.add("on");
  $("#panel").innerHTML = `<div class="ph"><div style="flex:1;font-weight:600">Feedback</div><button class="icon-btn" onclick="closeDrawer()">${ic("x")}</button></div><div class="pb"><div class="mut">Saved as a lesson for this page; the video is marked for a fix.</div><textarea id="fb" rows="6" style="margin-top:10px" placeholder="What should change?"></textarea><div style="display:flex;gap:8px;margin-top:10px"><button class="btn pri" onclick="sendFb('${cid}','${job}')">Send</button><button class="btn" onclick="closeDrawer()">Cancel</button></div></div>`;
  setTimeout(() => $("#fb").focus(), 40);
}
async function sendFb(cid, job) { const note = $("#fb").value.trim(); if (!note) return; try { await post("/api/decide", { cid, job, action: "fix", note }); closeDrawer(); toast("Feedback saved"); load(); } catch (e) { toast("Failed: " + e.message); } }
async function makeNow() { try { await post("/api/make", { cid: $("#mkc").value, topic: $("#mkt").value.trim() }); toast("Started"); setTimeout(load, 3000); } catch (e) { toast("Failed: " + e.message); } }
async function setS(b) { try { S.settings = await post("/api/settings", b); render(1); toast("Saved"); } catch (e) { toast("Failed: " + e.message); } }
async function resetFailed() { await post("/api/reset-failed", {}); toast("Cleared"); load(); }
async function doneTask(id) { await post("/api/task", { id, done: true }); toast("Marked done"); load(); }
async function testSrc(n) { toast("Testing…"); const r = await post("/api/test", { name: n }); toast((r.ok ? "Working: " : "Problem: ") + r.detail); loadSources(); }
async function loadBrief(force) { if (force) { briefCache = { headline: "", lines: [] }; render(1); } try { briefCache = await (await fetch("/api/brief" + (force ? "?force=1" : ""))).json(); } catch (e) { briefCache = { error: e.message }; } render(1); }
async function loadSources() { try { srcCache = await (await fetch("/api/sources")).json(); } catch (e) {} if (page() === "sources") render(1); }
function toggleTheme() { const h = document.documentElement; h.dataset.theme = h.dataset.theme === "dark" ? "light" : "dark"; localStorage.theme = h.dataset.theme; document.querySelector('meta[name=theme-color]').content = h.dataset.theme === "dark" ? "#0a0a0a" : "#fafafa"; render(1); }

/* ---------- render loop ---------- */
const page = () => { const t = location.hash.slice(1); return V[t] ? t : "today"; };
function render(force) {
  if (!S) return;
  const p = page(), wait = S.jobs.filter((j) => ["waiting", "ready"].includes(j.status)).length, bad = S.issues.filter((i) => i.lvl === "bad").length, warn = S.issues.filter((i) => i.lvl === "warn").length;
  const cnt = { approvals: wait ? [wait, "v"] : null, server: bad ? [bad, "r"] : warn ? [warn, "a"] : null, runs: S.jobs.filter((j) => j.active).length ? [S.jobs.filter((j) => j.active).length, ""] : null };
  $("#nav").innerHTML = NAV.map(([g, it]) => (g ? `<div class="ng">${g}</div>` : `<div style="height:6px"></div>`) + it.map(([k, t]) => `<a href="#${k}" class="${k === p ? "on" : ""}">${ic(ICON[k])}${t}${cnt[k] ? `<span class="c ${cnt[k][1]}">${cnt[k][0]}</span>` : ""}</a>`).join("")).join("");
  $("#tabbar").innerHTML = [["today", "Today"], ["runs", "Runs"], ["approvals", "Approve"], ["channels", "Channels"], ["server", "Server"], ["more", "More"]].map(([k, t]) => `<a href="${k === "more" ? "javascript:moreMenu()" : "#" + k}" class="${k === p ? "on" : ""}">${ic(ICON[k] || "more")}${t}${cnt[k] ? `<span class="c">${cnt[k][0]}</span>` : ""}</a>`).join("");
  const label = NAV.flatMap(([, it]) => it).find(([k]) => k === p)?.[1] || "Today";
  $("#crumb").innerHTML = `<span class="mut hide-m">Studio /</span>${esc(label)}`;
  if (p === "brain") { if (force || !$("#brainc")) { $("#view").innerHTML = V.brain(); prev = ""; startBrain(); } return; }
  const html = V[p]();
  if (force || html !== prev) { const a = document.activeElement, y = scrollY; $("#view").innerHTML = html; prev = html; scrollTo(0, y); if (a && a.id && $("#" + a.id)) $("#" + a.id).focus(); }
}
function moreMenu() {
  drawerKey = "more"; $("#drawer").classList.add("on");
  $("#panel").innerHTML = `<div class="ph"><div style="flex:1;font-weight:600">More</div><button class="icon-btn" onclick="closeDrawer()">${ic("x")}</button></div><div>${[["sources", "Connected apps"], ["activity", "Activity log"], ["brain", "Brain"], ["settings", "Settings"]].map(([k, t]) => `<a class="row click" href="#${k}" onclick="closeDrawer()">${ic(ICON[k])}<span class="grow">${t}</span></a>`).join("")}<a class="row click" href="javascript:closeDrawer();openPalette()">${ic("spark")}<span class="grow">Ask a question</span></a></div>`;
}
async function load() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" }); if (!r.ok) throw 0; S = await r.json(); fails = 0;
    $("#sync").innerHTML = `<i class="dot live"></i><span>Live · ${new Date(S.now * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>`;
    const ae = document.activeElement; if (ae && ae.tagName === "INPUT" && $("#view").contains(ae) && page() !== "activity") return; render();
  } catch (e) { if (++fails > 1) $("#sync").innerHTML = `<i class="dot" style="--c:var(--red)"></i><span>Offline · retrying</span>`; }
}
addEventListener("hashchange", () => { prev = ""; scrollTo(0, 0); closeDrawer(); render(1); if (page() === "sources") loadSources(); });
load().then(() => { loadBrief(0); loadSources(); }); setInterval(() => !document.hidden && load(), 4000); setInterval(() => !document.hidden && loadSources(), 60000);
