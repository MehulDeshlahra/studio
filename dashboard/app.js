/* Studio Control: live dashboard for the Studio engine + all channels. Data: /api/state every 4 s. */
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const C = { run: "#3b82f6", ok: "#22c55e", warn: "#f59e0b", bad: "#ef4444", wait: "#a855f7", post: "#14b8a6", info: "#64748b" };
const STATUS = {
  building: ["Building", C.run, "run"], waiting: ["Waiting for you", C.wait], ready: ["Ready · not sent", C.wait], approved: ["Approved · queued", C.post],
  posted: ["Posted", C.ok], held: ["Held by reviewer", C.warn], rejected: ["Rejected", C.bad], prepped: ["Prepped · waiting to render", C.run], paused: ["Paused midway", C.info], made: ["Made", C.info],
};
const I = {
  live: '<path d="M3 12h4l3-8 4 16 3-8h4"/>', pipe: '<rect x="3" y="4" width="18" height="4" rx="2"/><rect x="3" y="10" width="12" height="4" rx="2"/><rect x="3" y="16" width="7" height="4" rx="2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>', grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  brain: '<circle cx="12" cy="12" r="2.5"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 7l3 3.5M17 7l-3 3.5M7 17l3-3.5M17 17l-3-3.5"/>',
  alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>', cog: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
  ig: '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1"/>',
  fb: '<path d="M15 3h-3a4 4 0 0 0-4 4v3H5v4h3v7h4v-7h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>', yt: '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3z"/>',
  ok: '<path d="M20 6 9 17l-5-5"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
};
const ic = (n, sw = 1.9) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${I[n]}</svg>`;
const TABS = [["live", "Live", "live"], ["pipeline", "Pipeline", "pipe"], ["approvals", "Approvals", "check"], ["channels", "Channels", "grid"],
  ["brain", "Brain", "brain"], ["issues", "Issues", "alert"], ["settings", "Settings", "cog"]];
let S = null, lastHtml = "", feedFilter = "all", failCount = 0;

/* ---------- helpers ---------- */
const nfmt = (x) => (x >= 1e5 ? (x / 1e5).toFixed(1).replace(".0", "") + "L" : x >= 1000 ? (x / 1000).toFixed(1).replace(".0", "") + "k" : String(x ?? 0));
const ago = (t) => { const d = Math.max(0, (S ? S.now : Date.now() / 1000) - t); return d < 60 ? `${d | 0}s ago` : d < 3600 ? `${(d / 60) | 0}m ago` : d < 86400 ? `${(d / 3600) | 0}h ago` : `${(d / 86400) | 0}d ago`; };
const dur = (s) => (s == null ? "—" : s < 60 ? `${s | 0}s` : s < 3600 ? `${(s / 60) | 0}m ${s % 60 | 0}s` : `${(s / 3600) | 0}h ${((s % 3600) / 60) | 0}m`);
const cd = (s) => (s == null ? "—" : s < 0 ? "now" : s < 3600 ? `${(s / 60) | 0}:${String(s % 60 | 0).padStart(2, "0")}` : `${(s / 3600) | 0}h ${((s % 3600) / 60) | 0}m`);
const chOf = (id) => (S?.channels || []).find((c) => c.id === id) || { name: id, color: "#64748b" };
const pill = (st) => { const [t, c, k] = STATUS[st] || [st, C.info]; return `<span class="pill ${k || ""}" style="--c:${c}"><i></i>${t}</span>`; };
const lvlC = { bad: C.bad, warn: C.warn, info: C.run, ok: C.ok, run: C.run };
function toast(t) { const e = $("#toast"); e.textContent = t; e.classList.add("on"); clearTimeout(e._t); e._t = setTimeout(() => e.classList.remove("on"), 2600); }
async function post(url, body) { const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); const j = await r.json(); if (!r.ok) throw new Error(j.error || r.status); return j; }

function ring(pct, color, label) {
  const r = 26, c = 2 * Math.PI * r, p = Math.max(0, Math.min(100, pct));
  return `<svg class="ring" viewBox="0 0 64 64"><circle class="bgc" cx="32" cy="32" r="${r}"/><circle cx="32" cy="32" r="${r}" stroke="${color}" stroke-linecap="round" stroke-dasharray="${(c * p) / 100} ${c}" transform="rotate(-90 32 32)"/><text x="32" y="37" text-anchor="middle">${label}</text></svg>`;
}
const lvl = (v, w, b) => (v >= b ? C.bad : v >= w ? C.warn : C.ok);
function spark(vals, color, h = 36) {
  const v = vals.filter((x) => x != null); if (v.length < 2) return `<div class="s">History starts building today</div>`;
  const mn = Math.min(...v), mx = Math.max(...v), w = 200, pts = v.map((x, i) => [(i / (v.length - 1)) * w, h - 4 - ((x - mn) / (mx - mn || 1)) * (h - 8)]);
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${d} L${w} ${h} L0 ${h}Z" fill="${color}22"/><path d="${d}" fill="none" stroke="${color}" stroke-width="2"/></svg>`;
}
function chart(hist) {
  if (!hist || hist.length < 2) return `<div class="empty">Collecting data…</div>`;
  const w = 600, h = 150, n = hist.length;
  const line = (k, mx) => hist.map((p, i) => (i ? "L" : "M") + ((i / (n - 1)) * w).toFixed(1) + " " + (h - 6 - (Math.min(p[k], mx) / mx) * (h - 14)).toFixed(1)).join(" ");
  const cpu = line("cpu", 100), mem = line("mem", 100);
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
   ${[25, 50, 75].map((y) => `<line x1="0" x2="${w}" y1="${h - 6 - (y / 100) * (h - 14)}" y2="${h - 6 - (y / 100) * (h - 14)}" stroke="var(--line)" stroke-dasharray="3 5"/>`).join("")}
   <path d="${cpu} L${w} ${h} L0 ${h}Z" fill="${C.run}26"/><path d="${cpu}" fill="none" stroke="${C.run}" stroke-width="2"/>
   <path d="${mem}" fill="none" stroke="${C.wait}" stroke-width="2"/></svg>
   <div class="lg"><span><i style="background:${C.run}"></i>CPU</span><span><i style="background:${C.wait}"></i>Memory</span><span class="right">last ${Math.round((hist[n - 1].t - hist[0].t) / 60)} min</span></div>`;
}

/* ---------- pieces ---------- */
function steps(j, mini) {
  const bars = j.steps.map((s) => `<div class="st ${s.done ? "d" : s.active ? "a" : ""}" style="${s.active && s.sub != null ? `--w:${Math.round(s.sub * 100)}%` : ""}" title="${esc(s.label)}"></div>`).join("");
  const lbl = mini ? "" : `<div class="stl">${j.steps.map((s) => `<span class="${s.done ? "d" : s.active ? "a" : ""}">${esc(s.label)}</span>`).join("")}</div>`;
  return `<div class="steps">${bars}</div>${lbl}`;
}
function jobCard(j) {
  const ch = chOf(j.cid), cur = j.steps.find((s) => s.active);
  const el = j.started ? S.now - j.started : null;
  return `<div class="job ${j.active ? "active" : ""}">
   <div class="hd"><span class="chd" style="background:${ch.color}"></span><div style="min-width:0;flex:1"><div class="tt">${esc(j.title)}</div>
   <div class="meta">${esc(ch.name)} · ${j.lang === "en" ? "English" : "Hindi"} · <span class="mono">${esc(j.job)}</span></div></div>${pill(j.status)}</div>
   ${steps(j)}
   <div class="bar"><i style="width:${Math.round(j.pct * 100)}%"></i></div>
   <div class="pct"><span>${cur ? `Now: <b>${esc(cur.label)}</b>${cur.key === "render" && j.eta != null ? ` · about ${dur(j.eta)} left` : ""}` : "Done"}</span><span><b>${Math.round(j.pct * 100)}%</b>${el ? ` · running ${dur(el)}` : ""}</span></div>
  </div>`;
}
function miniJob(j) {
  const ch = chOf(j.cid);
  return `<div class="mini"><span class="chd" style="background:${ch.color}"></span><div style="min-width:0"><div class="tt">${esc(j.title)}</div>
   <div class="meta s" style="margin:0">${esc(ch.name)} · ${j.lang === "en" ? "EN" : "HI"} · ${ago(j.updated)}</div>${steps(j, true)}</div>${pill(j.status)}</div>`;
}
function issueCard(x) {
  const c = lvlC[x.lvl] || C.info, sym = { bad: "!", warn: "!", info: "i" }[x.lvl] || "i";
  return `<div class="iss" style="--c:${c}"><div class="ic">${sym}</div><div style="min-width:0;flex:1"><b>${esc(x.title)}</b>${x.detail ? `<p>${esc(x.detail)}</p>` : ""}${x.fix ? `<p class="fix">→ ${esc(x.fix)}</p>` : ""}
   ${x.action === "reset-failed" ? `<div class="btns" style="margin-top:8px"><button class="b" onclick="act('reset')">Clear failed jobs</button></div>` : ""}</div></div>`;
}
function feed(list, n = 80) {
  const f = feedFilter === "all" ? list : list.filter((a) => (feedFilter === "problems" ? a.lvl === "bad" || a.lvl === "warn" : a.cid === feedFilter));
  const chips = [["all", "All"], ["problems", "Problems"], ...S.channels.slice(0, 3).map((c) => [c.id, c.name])]
    .map(([k, t]) => `<button class="chipb ${feedFilter === k ? "on" : ""}" onclick="feedFilter='${k}';render(true)">${esc(t)}</button>`).join("");
  return `<div class="filters">${chips}</div><div class="feed">${f.slice(0, n).map((a) => {
    const ch = a.cid ? chOf(a.cid) : null;
    return `<div class="ev" style="--c:${lvlC[a.lvl] || C.info}"><span class="t">${a.t.slice(11, 16)}</span><span class="l"></span><span class="m">${ch ? `<span class="tag" style="background:${ch.color}">${esc(ch.name)}</span>` : ""}${esc(a.msg)}</span></div>`;
  }).join("") || `<div class="empty">Nothing here</div>`}</div>`;
}
function chCard(c) {
  const cnt = c.counts || {}, links = [
    c.ig && `<a class="lk" target="_blank" href="https://instagram.com/${c.ig}">${ic("ig")}@${esc(c.ig)}</a>`,
    c.fb_url && `<a class="lk" target="_blank" href="${c.fb_url}">${ic("fb")}Facebook</a>`,
    c.yt && `<a class="lk ${c.yt_ok === false ? "no" : ""}" target="_blank" href="https://youtube.com/${c.yt}" title="${c.yt_ok === false ? "Uploader not connected yet" : ""}">${ic("yt")}YouTube${c.yt_ok === false ? " · not linked" : ""}</a>`].filter(Boolean).join("");
  const stC = { live: C.ok, warm: C.warn, off: C.info, manual: C.info }[c.status];
  const pipe = Object.entries(cnt).filter(([, v]) => v).map(([k, v]) => { const [t, col] = STATUS[k] || [k === "queued" ? "Queued" : k, k === "queued" ? C.post : C.info]; return `<span class="pill" style="--c:${col}">${v} ${esc(t)}</span>`; }).join("");
  return `<div class="card chc" style="--cc:${c.color}"><div class="band"></div><div class="in">
   <div class="hd"><div class="av">${esc(c.name.split(" ").map((w) => w[0]).join("").slice(0, 2))}</div><div style="min-width:0"><div class="nm">${esc(c.name)}</div><div class="nt">${esc(c.note)}</div></div>
   <span class="pill right" style="--c:${stC}"><i></i>${{ live: "Live", warm: "Warm-up", off: "Off", manual: "Manual" }[c.status]}</span></div>
   <div class="nums"><div><b>${nfmt(c.igF)}</b><span>IG followers</span></div><div><b>${nfmt(c.fb)}</b><span>FB followers</span></div><div><b>${nfmt(c.posts)}</b><span>IG posts</span></div></div>
   ${spark(c.spark || [], c.color)}
   ${pipe ? `<div class="pipe">${pipe}</div>` : ""}
   <div class="links">${links}</div></div></div>`;
}
function approvalCard(j) {
  const ch = chOf(j.cid), base = `/media/${j.cid}/${j.job}/`, vid = j.files["preview.mp4"] ? "preview.mp4" : j.final;
  const probs = (j.review.problems || []).map((p) => `<span class="bad">✗ ${esc(String(p).slice(0, 90))}</span>`).join("");
  const minor = (j.review.minor || []).map((p) => `<span>• ${esc(String(p).slice(0, 90))}</span>`).join("");
  return `<div class="card"><div class="ap">
   <div class="cover" onclick="openVideo('${base + vid}','${esc(j.title).replace(/'/g, "")}')">${j.files["cover.jpg"] ? `<img loading="lazy" src="${base}cover.jpg?v=${j.updated}">` : ""}<div class="play">▶</div></div>
   <div style="min-width:0"><div class="hd" style="display:flex;gap:8px;align-items:center"><span class="chd" style="background:${ch.color}"></span><span class="s" style="margin:0">${esc(ch.name)} · ${j.lang === "en" ? "English" : "Hindi"} · ${j.qc.dur ? Math.round(j.qc.dur) + " s" : ""}</span><span class="right">${pill(j.status)}</span></div>
   <div style="font-weight:700;font-size:15.5px;margin-top:6px">${esc(j.title)}</div>
   <div class="chips">${j.review.score ? `<span class="okc">visual ${j.review.score}/10</span>` : ""}${j.qc.lufs ? `<span>${j.qc.lufs} LUFS</span>` : ""}${j.review.ok ? `<span class="okc">✓ passed review</span>` : ""}${probs}${minor}</div>
   ${j.caption ? `<div class="caption">${esc(j.caption)}</div>` : ""}
   ${["waiting", "ready", "held"].includes(j.status) ? `<div class="btns"><button class="b ok" onclick="decide('${j.cid}','${j.job}','approve')">✓ Approve</button><button class="b no" onclick="decide('${j.cid}','${j.job}','reject')">✗ Reject</button><button class="b" onclick="feedback('${j.cid}','${j.job}')">✎ Feedback</button></div>` : ""}
   </div></div></div>`;
}

/* ---------- views ---------- */
const V = {
  live() {
    const s = S.server, act = S.jobs.filter((j) => j.active), recent = S.jobs.filter((j) => !j.active).slice(0, 6);
    const waiting = S.jobs.filter((j) => j.status === "waiting" || j.status === "ready").length;
    const fol = S.channels.reduce((a, c) => a + c.igF + c.fb, 0);
    const today = S.activity.filter((a) => a.t.slice(0, 10) === new Date(S.now * 1000).toISOString().slice(0, 10));
    const madeToday = today.filter((a) => /rendered in/.test(a.msg)).length;
    return `
    <div class="grid g4">
     <div class="card gauge">${ring(s.cpu, lvl(s.cpu, 75, 92), Math.round(s.cpu) + "%")}<div><div class="k">CPU</div><div class="s">${s.cores} cores · load ${s.load[0]}</div><div class="s">${S.running.length} processes</div></div></div>
     <div class="card gauge">${ring(s.mem_pct, lvl(s.mem_pct, 80, 92), Math.round(s.mem_pct) + "%")}<div><div class="k">Memory</div><div class="s">${s.mem_used_gb} / ${s.mem_total_gb} GB</div></div></div>
     <div class="card gauge">${ring(s.disk_pct, lvl(s.disk_pct, 85, 93), Math.round(s.disk_pct) + "%")}<div><div class="k">Disk</div><div class="s">${s.disk_free_gb} GB free</div></div></div>
     <div class="card"><div class="k">Today</div><div class="v">${madeToday} <span style="font-size:14px;color:var(--mut);font-weight:600">renders</span></div>
      ${S.budgets.map((b) => `<div class="s" style="display:flex;justify-content:space-between;margin-top:6px"><span>${esc(b.name)}</span><span class="mono">${b.used}/${b.cap}</span></div><div class="bar" style="height:6px;margin-top:4px"><i style="width:${Math.min(100, (b.used / b.cap) * 100)}%;background:${lvl((b.used / b.cap) * 100, 75, 95)}"></i></div>`).join("")}</div>
    </div>
    <div class="split">
     <div>
      <div class="card"><h2>${ic("pipe")} Working on now <small>${act.length ? `${act.length} active` : "idle"}</small></h2>
       ${act.length ? act.map(jobCard).join("") : `<div class="empty"><div class="e">☕</div>Nothing building right now. Next: ${esc(S.schedule[0]?.name || "—")} in ${cd(S.schedule[0]?.in)}</div>`}
       ${S.running.filter((r) => !["Making video", "Scheduler", "Render (Chrome)"].includes(r.kind)).map((r) => `<div class="mini"><span class="chd" style="background:${C.run}"></span><div><div class="tt">${esc(r.kind)}</div><div class="s" style="margin:0">${esc(r.job.cid || "")} ${esc(r.job.job || "")} · ${dur(r.age)}</div></div><span class="pill run" style="--c:${C.run}"><i></i>Running</span></div>`).join("")}
      </div>
      <div class="card mt"><h2>${ic("live")} Server load <small>live</small></h2>${chart(s.hist)}</div>
      <div class="card mt"><h2>Recent videos <small><a href="#pipeline" style="color:var(--run)">see all →</a></small></h2>${recent.map(miniJob).join("") || `<div class="empty">No videos yet</div>`}</div>
     </div>
     <div>
      <div class="card"><h2>${ic("alert")} Issues <small>${S.issues.length ? S.issues.length + " open" : "none"}</small></h2>
       ${S.issues.length ? S.issues.slice(0, 5).map(issueCard).join("") + (S.issues.length > 5 ? `<a href="#issues" class="s" style="display:block;margin-top:10px;color:var(--run)">+${S.issues.length - 5} more →</a>` : "") : `<div class="empty"><div class="e" style="color:var(--ok)">✓</div>Everything looks healthy</div>`}</div>
      <div class="card mt"><h2>${ic("clock")} Coming up</h2>${S.schedule.map((t) => `<div class="tm"><span class="chd" style="background:${t.running ? C.run : C.info}"></span><div class="nm">${esc(t.name)}<small>${t.running ? "running now" : t.last ? "last " + ago(t.last) : "not run yet"}</small></div><span class="cd" style="color:${t.running ? C.run : "var(--tx)"}">${t.running ? "●" : cd(t.in)}</span></div>`).join("")}</div>
      <div class="card mt"><h2>Snapshot</h2>
       <div class="row"><span>Followers, 6 channels</span><b>${nfmt(fol)}</b></div>
       <div class="row"><span>Waiting for your OK</span><a href="#approvals"><b style="color:${C.wait}">${waiting}</b></a></div>
       <div class="row"><span>Approved, queued to post</span><b style="color:${C.post}">${S.jobs.filter((j) => j.status === "approved").length}</b></div>
       <div class="row"><span>Typical render</span><b>${dur(S.render_median)}</b></div>
       <div class="row"><span>Meta login</span><b style="color:${(S.token_days ?? 99) < 21 ? C.warn : C.ok}">${S.token_days ?? "—"} days</b></div>
      </div>
     </div>
    </div>
    <div class="card mt"><h2>Activity <small>engine log, newest first</small></h2>${feed(S.activity, 60)}</div>`;
  },
  pipeline() {
    const groups = [["building", "Building now"], ["waiting", "Waiting for you"], ["ready", "Ready, not sent"], ["held", "Held by reviewer"], ["prepped", "Prepped, waiting to render"], ["approved", "Approved, queued"], ["posted", "Posted"], ["paused", "Paused midway"], ["rejected", "Rejected"], ["made", "Other"]];
    const counts = groups.map(([k, t]) => [k, t, S.jobs.filter((j) => j.status === k)]).filter((g) => g[2].length);
    return `<h1>Pipeline</h1><p class="lead">Every video and the step it is on. Green = done, blue = working on it.</p>
     <div class="pipe mt">${counts.map(([k, t, l]) => `<span class="pill" style="--c:${(STATUS[k] || [])[1]}">${l.length} ${esc(t)}</span>`).join("")}</div>
     ${counts.map(([k, t, l]) => `<div class="card mt"><h2><span class="chd" style="background:${(STATUS[k] || [])[1]}"></span>${esc(t)} <small>${l.length}</small></h2>${l.map(jobCard).join("")}</div>`).join("")}`;
  },
  approvals() {
    const list = S.jobs.filter((j) => ["waiting", "ready"].includes(j.status)), held = S.jobs.filter((j) => j.status === "held"), appr = S.jobs.filter((j) => j.status === "approved");
    return `<h1>Approvals</h1><p class="lead">Videos that passed the server's review. Approve here or in Telegram, both work the same.${S.settings.auto_approve ? ` <b style="color:${C.ok}">Auto-approve is ON (score ≥ ${S.settings.min_score}).</b>` : ""}</p>
     <div class="grid g2 mt">${list.map(approvalCard).join("") || `<div class="card empty"><div class="e">🎉</div>Nothing waiting for you</div>`}</div>
     ${held.length ? `<h2 class="mt" style="margin-top:26px"><span class="chd" style="background:${C.warn}"></span>Held by the reviewer (${held.length})</h2><p class="lead">Not sent to you because the reviewer found a problem. You can still approve one if you think it's fine.</p><div class="grid g2 mt">${held.map(approvalCard).join("")}</div>` : ""}
     ${appr.length ? `<h2 style="margin-top:26px"><span class="chd" style="background:${C.post}"></span>Approved, waiting for their slot (${appr.length})</h2><div class="grid g2 mt">${appr.map(approvalCard).join("")}</div>` : ""}`;
  },
  channels() {
    const st = S.channels.filter((c) => c.group === "Studio"), bz = S.channels.filter((c) => c.group !== "Studio");
    const tot = S.channels.reduce((a, c) => a + c.igF + c.fb, 0);
    return `<h1>Channels</h1><p class="lead">${S.channels.length} channels · ${nfmt(tot)} followers. Numbers from Meta, refreshed every 30 minutes.</p>
     <h2 style="margin-top:20px">Studio pages</h2><div class="grid g3 mt">${st.map(chCard).join("")}</div>
     <h2 style="margin-top:26px">Businesses</h2><div class="grid g3 mt">${bz.map(chCard).join("")}</div>
     <div class="card mt"><h2>Make a video now</h2><div class="grid g3"><select id="mkc">${st.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select><input id="mkt" type="text" placeholder="Topic (optional, the engine picks one if empty)"><button class="b pri" onclick="makeNow()">Start building</button></div><div class="s">Runs in the background; it shows up in Pipeline in a few seconds.</div></div>`;
  },
  issues() {
    const g = { bad: S.issues.filter((x) => x.lvl === "bad"), warn: S.issues.filter((x) => x.lvl === "warn"), info: S.issues.filter((x) => x.lvl === "info") };
    return `<h1>Issues</h1><p class="lead">Checked every few seconds: failed jobs, reviewer holds, disk, memory, image bridges, login expiry, errors in the log.</p>
     <div class="grid g3 mt">${[["bad", "Needs fixing"], ["warn", "Watch"], ["info", "To set up"]].map(([k, t]) => `<div class="card" style="border-top:4px solid ${lvlC[k] || C.info}"><div class="k">${t}</div><div class="v" style="color:${lvlC[k] || C.info}">${g[k].length}</div></div>`).join("")}</div>
     <div class="card mt">${S.issues.map(issueCard).join("") || `<div class="empty"><div class="e" style="color:var(--ok)">✓</div>No issues</div>`}</div>
     <div class="card mt"><h2>Problems in the log</h2>${(feedFilter = "problems", feed(S.activity, 120))}</div>`;
  },
  brain() {
    return `<h1>Brain</h1><p class="lead">What the engine has learned. Every page reads the shared brain and every other page's lessons before it writes a script. Drag to explore, hover for the lesson.</p>
     <div class="card mt" style="padding:10px"><canvas id="brainc"></canvas>
      <div class="legend"><span><i style="background:#fff"></i>Shared brain</span>${S.channels.slice(0, 3).map((c) => `<span><i style="background:${c.color}"></i>${esc(c.name)}</span>`).join("")}<span><i style="background:${C.run}"></i>Shared lesson</span><span><i style="background:${C.bad}"></i>Mistake learned (auto)</span><span><i style="border:2px solid ${C.ok};background:transparent"></i>Video</span></div></div>`;
  },
  settings() {
    const st = S.settings;
    return `<h1>Settings</h1>
     <div class="card mt">
      <div class="row"><div><b>Auto-approve top videos</b><div class="s">Videos that pass every review check and score at least the number below go straight to the posting queue. You still get them in Telegram, marked "auto".</div></div><div class="sw ${st.auto_approve ? "on" : ""}" onclick="setS({auto_approve:${!st.auto_approve}})"></div></div>
      <div class="row"><div><b>Minimum visual score</b><div class="s">Only used when auto-approve is on.</div></div><select style="width:90px" onchange="setS({min_score:+this.value})">${[8, 9, 10].map((n) => `<option ${st.min_score == n ? "selected" : ""}>${n}</option>`).join("")}</select></div>
      <div class="row"><div><b>Theme</b><div class="s">Dark or light, saved on this device.</div></div><button class="b" onclick="toggleTheme()">◐ Switch</button></div>
      <div class="row"><div><b>Install on phone</b><div class="s">Browser menu → "Add to Home screen". It opens full screen like an app.</div></div></div>
     </div>
     <div class="card mt"><h2>Running processes</h2>${S.running.map((r) => `<div class="row"><div style="min-width:0"><b>${esc(r.kind)}</b><div class="mono s" style="word-break:break-all">${esc(r.cmd)}</div></div><span class="mono">${dur(r.age)}</span></div>`).join("") || `<div class="empty">None</div>`}</div>`;
  },
};

/* ---------- brain graph (small force layout on canvas) ---------- */
let G = null;
async function startBrain() {
  const cv = $("#brainc"); if (!cv) return;
  const data = await (await fetch("/api/brain")).json();
  const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr;
  const ctx = cv.getContext("2d"); ctx.scale(dpr, dpr);
  const byId = {}, stC = { posted: C.ok, approved: C.post, held: C.warn, rejected: C.bad, made: C.info };
  const nodes = data.nodes.map((n, i) => (byId[n.id] = { ...n, x: W / 2 + Math.cos(i) * (60 + i), y: H / 2 + Math.sin(i) * (60 + i), vx: 0, vy: 0,
    r: n.kind === "core" ? 20 : n.kind === "page" ? 15 : n.kind === "video" ? 6 : 4.5,
    col: n.kind === "core" ? "#ffffff" : n.kind === "page" ? n.color : n.kind === "auto" ? C.bad : n.kind === "video" ? (stC[n.status] || C.info) : n.cid ? n.color : C.run }));
  const links = data.links.map((l) => ({ s: byId[l.s], t: byId[l.t] })).filter((l) => l.s && l.t);
  const core = byId.brain; core.fx = W / 2; core.fy = H / 2;
  let drag = null, hover = null, alpha = 1;
  const tip = document.body.appendChild(Object.assign(document.createElement("div"), { className: "tip" }));
  function tick() {
    if (!document.body.contains(cv)) { tip.remove(); return; }
    if (alpha > 0.02) {
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j]; let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy + 0.01; const f = (900 * alpha) / d2; const d = Math.sqrt(d2);
        dx /= d; dy /= d; a.vx -= dx * f; a.vy -= dy * f; b.vx += dx * f; b.vy += dy * f;
      }
      for (const l of links) {
        const want = l.s.kind === "core" ? (l.t.kind === "page" ? 150 : 95) : 55;
        const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = ((d - want) / d) * 0.06 * alpha;
        l.s.vx += dx * f; l.s.vy += dy * f; l.t.vx -= dx * f; l.t.vy -= dy * f;
      }
      for (const n of nodes) {
        n.vx += (W / 2 - n.x) * 0.002 * alpha; n.vy += (H / 2 - n.y) * 0.002 * alpha;
        if (n.fx != null) { n.x = n.fx; n.y = n.fy; n.vx = n.vy = 0; continue; }
        n.vx *= 0.82; n.vy *= 0.82; n.x = Math.max(12, Math.min(W - 12, n.x + n.vx)); n.y = Math.max(12, Math.min(H - 12, n.y + n.vy));
      }
      alpha *= 0.992;
    }
    ctx.clearRect(0, 0, W, H);
    for (const l of links) { ctx.strokeStyle = (l.t.col || "#888") + (hover && (hover === l.s || hover === l.t) ? "cc" : "33"); ctx.lineWidth = l.s.kind === "core" ? 1.6 : 1; ctx.beginPath(); ctx.moveTo(l.s.x, l.s.y); ctx.lineTo(l.t.x, l.t.y); ctx.stroke(); }
    const t = performance.now() / 1000;
    for (const n of nodes) {
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r + (n.kind === "core" ? Math.sin(t * 2) * 1.5 : 0), 0, 7);
      if (n.kind === "video") { ctx.strokeStyle = n.col; ctx.lineWidth = 2.2; ctx.stroke(); } else { ctx.shadowColor = n.col; ctx.shadowBlur = n.kind === "lesson" || n.kind === "auto" ? 6 : 18; ctx.fillStyle = n.col; ctx.fill(); ctx.shadowBlur = 0; }
      if (n.kind === "page" || n.kind === "core") { ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--tx"); ctx.font = "700 12px Inter"; ctx.textAlign = "center"; ctx.fillText(n.label, n.x, n.y + n.r + 15); }
    }
    requestAnimationFrame(tick);
  }
  const pos = (e) => { const r = cv.getBoundingClientRect(), p = e.touches ? e.touches[0] : e; return [p.clientX - r.left, p.clientY - r.top, p.clientX, p.clientY]; };
  const find = (x, y) => nodes.find((n) => (n.x - x) ** 2 + (n.y - y) ** 2 < (n.r + 6) ** 2);
  cv.onpointerdown = (e) => { const [x, y] = pos(e); drag = find(x, y); if (drag) { drag.fx = x; drag.fy = y; alpha = Math.max(alpha, 0.5); cv.setPointerCapture(e.pointerId); } };
  cv.onpointermove = (e) => {
    const [x, y, cx, cy] = pos(e); if (drag) { drag.fx = x; drag.fy = y; alpha = Math.max(alpha, 0.3); }
    hover = find(x, y); if (hover) { tip.style.display = "block"; tip.style.left = Math.min(innerWidth - 330, cx + 14) + "px"; tip.style.top = cy + 14 + "px"; tip.innerHTML = `<b>${esc({ core: "Shared brain", page: "Page", lesson: "Lesson", auto: "Mistake learned", video: "Video · " + (hover.status || "") }[hover.kind])}</b><br>${esc(hover.label)}`; } else tip.style.display = "none";
  };
  cv.onpointerup = () => { if (drag && drag !== core) { drag.fx = drag.fy = null; } drag = null; };
  cv.onpointerleave = () => { tip.style.display = "none"; hover = null; };
  tick();
}

/* ---------- actions ---------- */
async function decide(cid, job, action) { try { await post("/api/decide", { cid, job, action }); toast(action === "approve" ? "Approved ✓" : "Rejected"); load(); } catch (e) { toast("Failed: " + e.message); } }
function feedback(cid, job) {
  $("#sheet").innerHTML = `<h2>Feedback for ${esc(job)}</h2><p class="lead">Saved as a lesson for this page and the video is marked for a fix.</p><textarea id="fb" rows="5" class="mt" placeholder="What should change?"></textarea><div class="btns"><button class="b pri" onclick="sendFb('${cid}','${job}')">Send</button><button class="b" onclick="closeModal()">Cancel</button></div>`;
  $("#modal").classList.add("on"); setTimeout(() => $("#fb").focus(), 50);
}
async function sendFb(cid, job) { const note = $("#fb").value.trim(); if (!note) return; try { await post("/api/decide", { cid, job, action: "fix", note }); closeModal(); toast("Feedback saved"); load(); } catch (e) { toast("Failed: " + e.message); } }
function openVideo(src, title) { $("#sheet").innerHTML = `<h2 style="margin-bottom:10px">${esc(title)}</h2><video src="${src}" controls autoplay playsinline></video><div class="btns"><button class="b" onclick="closeModal()">Close</button></div>`; $("#modal").classList.add("on"); }
function closeModal() { $("#modal").classList.remove("on"); $("#sheet").innerHTML = ""; }
async function makeNow() { try { const r = await post("/api/make", { cid: $("#mkc").value, topic: $("#mkt").value.trim() }); toast("Started ✓"); setTimeout(load, 3000); } catch (e) { toast("Failed: " + e.message); } }
async function setS(b) { try { S.settings = await post("/api/settings", b); render(true); toast("Saved"); } catch (e) { toast("Failed: " + e.message); } }
async function act(k) { if (k === "reset") { await post("/api/reset-failed", {}); toast("Cleared"); load(); } }
function toggleTheme() { const h = document.documentElement; h.dataset.theme = h.dataset.theme === "dark" ? "light" : "dark"; localStorage.theme = h.dataset.theme; render(true); }

/* ---------- render ---------- */
function tab() { const t = location.hash.slice(1); return TABS.some((x) => x[0] === t) ? t : "live"; }
function render(force) {
  if (!S) return;
  const t = tab(), waiting = S.jobs.filter((j) => j.status === "waiting" || j.status === "ready").length;
  const bad = S.issues.filter((x) => x.lvl === "bad").length, warn = S.issues.filter((x) => x.lvl === "warn").length;
  const badge = { approvals: [waiting, C.wait], issues: [bad + warn, bad ? C.bad : C.warn] };
  const navHtml = TABS.map(([id, l, i]) => `<a href="#${id}" class="${id === t ? "on" : ""}">${ic(i)}${l}${badge[id] && badge[id][0] ? `<span class="cnt" style="background:${badge[id][1]}">${badge[id][0]}</span>` : ""}</a>`).join("");
  $("#nav").innerHTML = navHtml;
  $("#tabbar").innerHTML = TABS.filter((x) => x[0] !== "settings").map(([id, l, i]) => `<a href="#${id}" class="${id === t ? "on" : ""}">${ic(i)}${l}${badge[id] && badge[id][0] ? `<span class="cnt" style="background:${badge[id][1]}">${badge[id][0]}</span>` : ""}</a>`).join("");
  const c = bad ? C.bad : warn ? C.warn : C.ok, act = S.jobs.some((j) => j.active);
  $("#banner").style.setProperty("--c", act && !bad ? C.run : c);
  $("#banner").innerHTML = `<div class="ico">${act ? ic("live") : bad || warn ? ic("alert") : ic("ok")}</div><div style="min-width:0"><div class="big">${esc(S.doing)}</div>
   <div class="sub">${bad ? `${bad} problem${bad > 1 ? "s" : ""} need fixing` : warn ? `${warn} thing${warn > 1 ? "s" : ""} to watch` : "All systems healthy"} · ${waiting} waiting for you</div></div>
   <div class="right">Server up ${Math.round(S.server.uptime_h / 24)} d<br>updated ${new Date(S.now * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</div>`;
  if (t === "brain") { if (force || !$("#brainc")) { $("#view").innerHTML = V.brain(); lastHtml = ""; startBrain(); } return; }
  if ($("#modal").classList.contains("on") && !force) return;
  const keepFilter = feedFilter; const html = V[t](); if (t === "issues") feedFilter = keepFilter;
  if (force || html !== lastHtml) { const y = scrollY; $("#view").innerHTML = html; lastHtml = html; scrollTo(0, y); }
}
async function load() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" }); if (!r.ok) throw 0; S = await r.json(); failCount = 0;
    $("#liveTx").textContent = "Live · updates every 4 s"; document.querySelector(".pulse").classList.remove("off"); render();
  } catch (e) { if (++failCount > 1) { $("#liveTx").textContent = "Offline · retrying"; document.querySelector(".pulse").classList.add("off"); } }
}
if (localStorage.theme) document.documentElement.dataset.theme = localStorage.theme;
addEventListener("hashchange", () => { lastHtml = ""; scrollTo(0, 0); render(true); });
load(); setInterval(() => { if (!document.hidden) load(); }, 4000);
