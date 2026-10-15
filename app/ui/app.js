"use strict";
/* EuroJackpot Analyzer UI. Talks to Python through window.pywebview.api (or /rpc in dev-server mode). */

const S = { t: {}, settings: {}, info: {}, stats: null, ticket: null, locks: {}, view: "stats", freqKind: "main", charts: [], polling: null };
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const ALGO_ORDER = ["auto_ticket", "auto_column", "random", "hot", "cold", "overdue", "weighted", "balanced", "smart"];

async function call(name, ...args) {
  if (window.pywebview && window.pywebview.api) return window.pywebview.api[name](...args);
  const r = await fetch("/rpc", { method: "POST", body: JSON.stringify({ name, args }) });
  const j = await r.json();
  if (j.error) throw new Error(j.error);
  return j.result;
}
const ready = () => new Promise(res => {
  if (window.pywebview && window.pywebview.api) return res();
  let done = false;
  const fin = () => { if (!done) { done = true; res(); } };
  window.addEventListener("pywebviewready", fin);
  setTimeout(fin, 1500); // plain-browser / dev-server mode
});

const tr = (k, vars = {}) => (S.t[k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? "");
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtDate = iso => { if (!iso) return "—"; const [y, m, d] = iso.slice(0, 10).split("-"); return `${d}/${m}/${y}`; };
const fmtDT = iso => iso ? `${fmtDate(iso)} ${iso.slice(11, 16)}` : tr("top.never");
const money = n => n.toLocaleString(S.settings.lang === "el" ? "el-GR" : "en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const ball = (n, cls = "") => `<span class="ball ${cls}">${n}</span>`;
const balls = (d, cls = "") => `<div class="balls">${d.main.map(n => ball(n, cls)).join("")}<span class="sep"></span>${d.euro.map(n => ball(n, "euro " + cls)).join("")}</div>`;

function toast(msg) {
  const el = $("#toast"); el.textContent = msg; el.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.add("hidden"), 2200);
}
function setStatus(msg, cls = "") { const s = $("#status"); s.textContent = msg; s.className = "status " + cls; }

/* ---------- i18n / theme ---------- */
async function loadLocale() {
  S.t = await call("get_locale", S.settings.lang);
  document.documentElement.lang = S.settings.lang;
  $$("[data-i18n]").forEach(el => el.textContent = tr(el.dataset.i18n));
  $("#btn-lang").textContent = S.settings.lang.toUpperCase();
  document.title = tr("app.title");
}
function applyTheme() {
  document.documentElement.dataset.theme = S.settings.theme;
  $("#btn-theme").textContent = S.settings.theme === "dark" ? "🌙" : "☀️";
}
async function setSetting(k, v) { S.settings = await call("set_setting", k, v); }

/* ---------- state / update ---------- */
async function refreshInfo() {
  S.info = await call("get_state");
  S.settings = S.info.settings;
  $("#last-update").textContent = fmtDT(S.info.last_update);
  $("#draw-count").textContent = `${S.info.count} ${tr("top.draws")}`;
}
function overlay(show, { title = "", text = "", pct = 0, btn = "" } = {}) {
  $("#overlay").classList.toggle("hidden", !show);
  if (!show) return;
  $("#ov-title").textContent = title; $("#ov-text").textContent = text;
  $("#ov-bar").style.width = pct + "%"; $("#ov-pct").textContent = Math.round(pct) + "%";
  const b = $("#ov-btn"); b.textContent = btn; b.classList.toggle("hidden", !btn);
}
async function runUpdate({ firstRun = false } = {}) {
  if (S.polling) return;
  $("#btn-update").disabled = true;
  if (firstRun) overlay(true, { title: tr("first.title"), text: tr("first.text") });
  else setStatus(tr("update.running"));
  await call("start_update");
  await new Promise(resolve => {
    S.polling = setInterval(async () => {
      const p = await call("get_progress");
      const pct = p.total ? (100 * p.done / p.total) : 0;
      if (firstRun) overlay(true, { title: tr("first.title"), text: tr("first.text"), pct });
      if (!p.running) {
        clearInterval(S.polling); S.polling = null; resolve(p);
      }
    }, 400);
  }).then(async p => {
    $("#btn-update").disabled = false;
    if (p.error) {
      setStatus(tr("update.error", { err: p.error }), "err");
      if (firstRun) overlay(true, { title: tr("first.title"), text: tr("update.error", { err: p.error }), btn: tr("first.retry") });
      return;
    }
    overlay(false);
    const r = p.result || {};
    setStatus((r.added ? tr("update.done", r) : tr("update.uptodate", r)) + (r.verified ? "  " + tr("update.verified") : ""), "ok");
    await refreshInfo(); await renderAll();
  });
}

/* ---------- navigation ---------- */
function showView(v) {
  S.view = v;
  $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === v));
  $$(".view").forEach(s => s.classList.toggle("active", s.id === "view-" + v));
  if (v === "stats") renderStats(); else if (v === "ticket") renderTicket(); else if (v === "history") renderHistory(); else renderSettings();
}
async function renderAll() { showView(S.view); }

/* ---------- statistics ---------- */
const PERIODS = [["all", "period.all"], ["10y", "period.10y"], ["5y", "period.5y"], ["3y", "period.3y"], ["1y", "period.1y"], ["last:100", "period.last100"], ["last:50", "period.last50"]];
function killCharts() { S.charts.forEach(c => c.destroy()); S.charts = []; }
function chart(id, cfg) {
  const el = document.getElementById(id); if (!el) return;
  const c = new Chart(el, cfg); S.charts.push(c); return c;
}
const chartBase = () => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { labels: { color: cssVar("--text"), font: { size: 13 } } } },
});
const axis = () => ({ ticks: { color: cssVar("--muted") }, grid: { color: "rgba(148,163,196,.15)" } });

async function renderStats() {
  const view = $("#view-stats");
  if (!S.info.count) { view.innerHTML = ""; return; }
  const period = S.settings.period || "all";
  const st = S.stats = await call("get_stats", period);
  const last = st.last_draw;
  view.innerHTML = `
    <div class="hero card">
      <div><div class="date">${tr("stats.lastdraw")} · ${fmtDate(last.date)}</div>${balls(last, "lg")}</div>
      <div class="muted">${tr("stats.analysed", { n: st.n_draws })}<br>${fmtDate(st.first_date)} → ${fmtDate(st.last_date)}</div>
    </div>
    <div class="toolbar"><span class="strong">${tr("stats.period")}:</span>
      <div class="chips">${PERIODS.map(([k, l]) => `<button class="chip ${k === period ? "active" : ""}" data-period="${k}">${tr(l)}</button>`).join("")}</div></div>
    <div class="card" style="margin-bottom:1.1rem">
      <div class="toolbar" style="margin-bottom:.6rem"><h3 style="margin:0">${tr("stats.freq")}</h3>
        <div class="chips"><button class="chip ${S.freqKind === "main" ? "active" : ""}" data-kind="main">${tr("stats.main")}</button>
        <button class="chip ${S.freqKind === "euro" ? "active" : ""}" data-kind="euro">${tr("stats.euro")}</button></div></div>
      <div class="chart-box"><canvas id="ch-freq"></canvas></div>
      ${S.freqKind === "euro" ? `<div class="muted small" style="margin-top:.5rem">${tr("stats.euro.note")}</div>` : ""}
    </div>
    <div class="grid g3" style="margin-bottom:1.1rem">
      ${rankCard("stats.hot", "hot", st)}${rankCard("stats.cold", "cold", st)}${rankCard("stats.overdue", "overdue", st)}
    </div>
    <div class="card" style="margin-bottom:1.1rem"><h3>${tr("stats.heatmap")}</h3><div class="muted small" style="margin-bottom:.7rem">${tr("stats.heatmap.hint")}</div>
      <div class="heat">${heatCells(st)}</div></div>
    <div class="grid g2" style="margin-bottom:1.1rem">
      <div class="card"><h3>${tr("stats.oddeven")}</h3><div class="chart-box sm"><canvas id="ch-odd"></canvas></div></div>
      <div class="card"><h3>${tr("stats.lowhigh")}</h3><div class="chart-box sm"><canvas id="ch-low"></canvas></div></div>
    </div>
    <div class="grid g2">
      <div class="card"><h3>${tr("stats.sums")} <span class="muted small">· ${tr("stats.avg_sum")}: ${st.sum_avg ?? "—"}</span></h3><div class="chart-box sm"><canvas id="ch-sum"></canvas></div></div>
      <div class="card"><h3>${tr("stats.pairs")}</h3><div class="pairs">${st.top_pairs.map(p =>
        `<div class="pair">${p.pair.map(n => ball(n, "sm")).join("")}<span class="cnt">${p.count}×</span></div>`).join("")}</div></div>
    </div>`;
  $$("[data-period]", view).forEach(b => b.onclick = async () => { await setSetting("period", b.dataset.period); renderStats(); });
  $$("[data-kind]", view).forEach(b => b.onclick = () => { S.freqKind = b.dataset.kind; renderStats(); });
  drawCharts(st);
}
function rankCard(titleKey, key, st) {
  const mainList = st.ranking.main[key].slice(0, 7);
  const euroList = st.ranking.euro[key].slice(0, 3);
  const mm = Object.fromEntries(st.main.map(x => [x.n, x])), em = Object.fromEntries(st.euro.map(x => [x.n, x]));
  const meta = (x) => key === "overdue" ? `${x.gap} ${tr("stats.gap")}` : `${x.count} ${tr("stats.times")} · ${x.pct}%`;
  return `<div class="card"><h3>${tr(titleKey)}</h3><div class="rank">
    ${mainList.map(n => `<div class="rank-row">${ball(n)}<span class="meta">${meta(mm[n])}</span></div>`).join("")}
    <div class="rank-row" style="margin-top:.3rem">${euroList.map(n => ball(n, "euro")).join("")}<span class="meta">${tr("stats.euro")}</span></div>
  </div></div>`;
}
function heatCells(st) {
  const maxGap = Math.max(...st.main.map(x => x.gap || 0), 1);
  return st.main.map(x => {
    const t = (x.gap || 0) / maxGap;
    const rgb = t > .35 ? cssVar("--heat-hot") : cssVar("--heat-cold");
    const alpha = (.18 + Math.min(1, t) * .72).toFixed(2);
    const tip = `${x.n}: ${x.gap} ${tr("stats.gap")} · ${tr("stats.max_gap")} ${x.max_gap} · ${tr("stats.last_seen")} ${fmtDate(x.last_seen)}`;
    return `<div class="cell" title="${esc(tip)}" style="background:rgba(${rgb},${alpha})"><b>${x.n}</b><i>${x.gap}</i></div>`;
  }).join("");
}
function drawCharts(st) {
  const txt = cssVar("--text"), acc = cssVar("--accent"), c2 = cssVar("--accent2"), gold = cssVar("--gold2");
  const block = (S.freqKind === "main" ? st.main : st.euro.filter(e => e.active || e.count));
  const avg = block.reduce((a, b) => a + b.pct, 0) / block.length;
  chart("ch-freq", { type: "bar", data: { labels: block.map(x => x.n), datasets: [{
      label: tr("stats.times"), data: block.map(x => x.count),
      backgroundColor: block.map(x => x.pct >= avg ? (S.freqKind === "main" ? acc : gold) : c2 + "aa"), borderRadius: 6 }] },
    options: { ...chartBase(), plugins: { legend: { display: false },
      tooltip: { callbacks: { afterLabel: i => { const x = block[i.dataIndex]; return `${x.pct}% · ${tr("stats.gap")}: ${x.gap}` + (x.avg_gap ? " · " + tr("stats.avg_gap", { n: x.avg_gap }) : ""); } } } },
      scales: { x: axis(), y: axis() } } });
  const pie = (id, labels, data, colors) => chart(id, { type: "doughnut", data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
    options: { ...chartBase(), cutout: "58%", plugins: { legend: { position: "right", labels: { color: txt, font: { size: 14 } } } } } });
  const palette = [acc, c2, "#f472b6", "#34d399", gold, "#fb7185"];
  pie("ch-odd", st.odd_even.map(x => tr("stats.lbl.oddeven", { a: x.odd, b: x.even })), st.odd_even.map(x => x.count), palette);
  pie("ch-low", st.low_high.map(x => tr("stats.lbl.lowhigh", { a: x.low, b: x.high })), st.low_high.map(x => x.count), palette);
  const sh = st.sum_hist.filter(x => x.from >= 40 && x.from <= 220);
  chart("ch-sum", { type: "bar", data: { labels: sh.map(x => `${x.from}–${x.from + 9}`), datasets: [{ data: sh.map(x => x.count), backgroundColor: c2, borderRadius: 6 }] },
    options: { ...chartBase(), plugins: { legend: { display: false } }, scales: { x: axis(), y: axis() } } });
}

/* ---------- ticket generator ---------- */
function algoLabel(a) { return tr("algo." + a); }
async function renderTicket() {
  killCharts();
  const view = $("#view-ticket"), cfg = S.settings, tk = S.ticket;
  view.innerHTML = `
    <h1>${tr("ticket.title")}</h1>
    <div class="card">
      <div class="toolbar"><span class="strong">${tr("ticket.columns")}:</span>
        <div class="stepper"><button id="c-minus">−</button><output id="c-val">${cfg.columns}</output><button id="c-plus">+</button></div>
        <span class="muted">× ${money(S.info.price)} ${tr("ticket.per_column")}</span></div>
      <div class="strong" style="margin-bottom:.5rem">${tr("ticket.algo")}:</div>
      <div class="algos">${ALGO_ORDER.map(a => `<button class="algo ${a === cfg.algo ? "active" : ""}" data-algo="${a}">${algoLabel(a)}</button>`).join("")}</div>
      <div style="margin-top:1.2rem"><button id="gen" class="btn primary big-btn">🎲 ${tr("ticket.generate")}</button></div>
    </div>
    <div id="ticket-out"></div>
    <div class="disclaimer">${tr("ticket.disclaimer")}</div>`;
  const setCols = async v => { v = Math.max(1, Math.min(S.info.max_columns, v)); await setSetting("columns", v); $("#c-val").textContent = v; };
  $("#c-minus").onclick = () => setCols(S.settings.columns - 1);
  $("#c-plus").onclick = () => setCols(S.settings.columns + 1);
  $$(".algo", view).forEach(b => b.onclick = async () => { await setSetting("algo", b.dataset.algo); $$(".algo", view).forEach(x => x.classList.toggle("active", x === b)); });
  $("#gen").onclick = () => generate();
  drawTicket();
}
async function generate(keep) {
  try {
    S.ticket = await call("generate", S.settings.columns, S.settings.algo, keep || [], S.settings.period || "all");
    if (!keep) S.locks = {};
    drawTicket();
  } catch (e) { toast(e.message || String(e)); }
}
function drawTicket() {
  const out = $("#ticket-out"); if (!out) return;
  const tk = S.ticket;
  if (!tk) { out.innerHTML = `<div class="empty">${tr("ticket.empty")}</div>`; return; }
  out.innerHTML = `<div class="cols">${tk.columns.map((c, i) => `
    <div class="col-row ${S.locks[i] ? "locked" : ""}">
      <span class="col-no">${tr("ticket.column")} ${i + 1}</span>${balls(c)}
      <span class="col-tag">${tr("algo.short." + c.algo)}</span>
      <button class="icon-btn" data-lock="${i}" title="${S.locks[i] ? tr("ticket.unlock") : tr("ticket.lock")}">${S.locks[i] ? "🔒" : "🔓"}</button>
      <button class="icon-btn" data-regen="${i}" title="${tr("ticket.regen")}">🔄</button>
      <span class="col-price">${money(tk.price_per_column)}</span></div>`).join("")}</div>
    <div class="total"><div><div class="muted">${tr("ticket.total")}</div><div>${tk.columns.length} × ${money(tk.price_per_column)}</div></div>
      <div class="sum">${money(tk.total)}</div>
      <button id="copy" class="btn">📋 ${tr("ticket.copy")}</button></div>`;
  $$("[data-lock]", out).forEach(b => b.onclick = () => { const i = +b.dataset.lock; S.locks[i] = !S.locks[i]; drawTicket(); });
  $$("[data-regen]", out).forEach(b => b.onclick = () => { const i = +b.dataset.regen;
    generate(tk.columns.map((c, j) => j === i ? null : c)); });
  $("#copy").onclick = async () => {
    const text = tk.columns.map((c, i) => `${tr("ticket.column")} ${i + 1}: ${c.main.join(" ")} + ${c.euro.join(" ")}`).join("\n") + `\n${tr("ticket.total")}: ${money(tk.total)}`;
    try { await navigator.clipboard.writeText(text); toast(tr("ticket.copied")); } catch { toast(text); }
  };
}

/* ---------- history ---------- */
async function renderHistory() {
  killCharts();
  const rows = await call("get_draws", 100);
  $("#view-history").innerHTML = `<h1>${tr("history.title")}</h1><div class="card"><table>
    <thead><tr><th>${tr("history.date")}</th><th>${tr("history.numbers")}</th><th>${tr("history.source")}</th></tr></thead>
    <tbody>${rows.map(d => `<tr><td class="strong">${fmtDate(d.date)}</td><td>${balls(d, "sm")}</td><td class="muted small">${esc(d.source)}</td></tr>`).join("")}</tbody></table></div>`;
}

/* ---------- settings ---------- */
function renderSettings() {
  killCharts();
  const s = S.settings;
  const view = $("#view-settings");
  view.innerHTML = `<h1>${tr("settings.title")}</h1><div class="card">
    <div class="row"><span class="strong">${tr("settings.language")}</span><div class="chips">
      <button class="chip ${s.lang === "el" ? "active" : ""}" data-lang="el">Ελληνικά</button><button class="chip ${s.lang === "en" ? "active" : ""}" data-lang="en">English</button></div></div>
    <div class="row"><span class="strong">${tr("settings.theme")}</span><div class="chips">
      <button class="chip ${s.theme === "dark" ? "active" : ""}" data-theme="dark">🌙 ${tr("settings.dark")}</button><button class="chip ${s.theme === "light" ? "active" : ""}" data-theme="light">☀️ ${tr("settings.light")}</button></div></div>
    <div class="row"><div><div class="strong">${tr("settings.auto_update")}</div><div class="muted small">${tr("settings.auto_update.hint")}</div></div>
      <button id="sw-auto" class="switch ${s.auto_update ? "on" : ""}" aria-label="auto update"></button></div>
    <div class="row"><div><div class="strong">${tr("settings.data")}</div><div class="muted small">${S.info.count} ${tr("top.draws")} · ${fmtDate(S.info.last_draw)}<br>${tr("settings.sources")}</div></div>
      <button id="upd" class="btn primary">${tr("settings.update_now")}</button></div></div>
    <div class="card" style="margin-top:1.1rem"><h3>${tr("settings.import")}</h3><div class="muted small">${tr("settings.import.hint")}</div>
      <div id="drop" class="drop"><button id="pick" class="btn">${tr("settings.import.choose")}</button></div></div>`;
  $$("[data-lang]", view).forEach(b => b.onclick = async () => { await setSetting("lang", b.dataset.lang); await loadLocale(); await refreshInfo(); renderSettings(); });
  $$("[data-theme]", view).forEach(b => b.onclick = async () => { await setSetting("theme", b.dataset.theme); applyTheme(); renderSettings(); });
  $("#sw-auto").onclick = async e => { await setSetting("auto_update", !S.settings.auto_update); e.currentTarget.classList.toggle("on", S.settings.auto_update); };
  $("#upd").onclick = () => runUpdate();
  const report = r => { if (!r) return; toast(r.found ? tr("settings.import.done", r) : tr("settings.import.none")); refreshInfo(); };
  $("#pick").onclick = async () => {
    if (window.pywebview && window.pywebview.api) report(await call("import_file"));
    else { const i = document.createElement("input"); i.type = "file"; i.accept = ".csv,.json,.txt"; i.onchange = () => readFile(i.files[0], report); i.click(); }
  };
  const drop = $("#drop");
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => readFile(e.dataTransfer.files[0], report));
}
function readFile(file, cb) {
  if (!file) return;
  const fr = new FileReader();
  fr.onload = async () => cb(await call("import_text", file.name, fr.result));
  fr.readAsText(file);
}

/* ---------- boot ---------- */
async function boot() {
  await ready();
  await refreshInfo();
  applyTheme();
  await loadLocale();
  await refreshInfo();
  $$(".nav-btn").forEach(b => b.onclick = () => showView(b.dataset.view));
  $("#btn-theme").onclick = async () => { await setSetting("theme", S.settings.theme === "dark" ? "light" : "dark"); applyTheme(); renderAll(); };
  $("#btn-lang").onclick = async () => { await setSetting("lang", S.settings.lang === "el" ? "en" : "el"); await loadLocale(); await refreshInfo(); renderAll(); };
  $("#btn-full").onclick = () => { if (window.pywebview) call("toggle_fullscreen"); else if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); };
  $("#btn-update").onclick = () => runUpdate();
  $("#ov-btn").onclick = () => runUpdate({ firstRun: true });
  window.addEventListener("keydown", e => { if (e.key === "F11") { e.preventDefault(); $("#btn-full").click(); } });
  window.addEventListener("resize", () => S.charts.forEach(c => c.resize()));
  if (!S.info.count) { await runUpdate({ firstRun: true }); }
  else { await renderAll(); if (S.settings.auto_update) runUpdate(); }
}
boot().catch(e => { console.error(e); setStatus(String(e), "err"); });
