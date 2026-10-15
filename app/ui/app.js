"use strict";
/* EuroJackpot Analyzer UI. Talks to Python through window.pywebview.api (or /rpc in dev-server mode). */

const S = { t: {}, settings: {}, info: {}, stats: null, ticket: null, locks: {}, view: "stats", freqKind: "main", charts: [], polling: null,
  lastError: null, appUpdate: null };
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const ALGO_ORDER = ["auto_ticket", "auto_column", "random", "hot", "cold", "overdue", "weighted", "balanced", "smart"];

// Browser/fallback mode (no native window): the local server hands us a secret token in the URL (?t=...)
const TOKEN = new URLSearchParams(location.search).get("t") || "";
async function call(name, ...args) {
  if (window.EJ_WEBAPI) return window.EJ_WEBAPI[name](...args);       // web app (PWA) and Android app: the API runs in the page
  if (window.pywebview && window.pywebview.api) return window.pywebview.api[name](...args);
  const r = await fetch("/rpc", { method: "POST", headers: { "X-Token": TOKEN }, body: JSON.stringify({ name, args }) });
  const j = await r.json();
  if (j.error) throw new Error(j.error);
  return j.result;
}
function startHeartbeat() {       // lets the server know the window is open; it exits when the window is closed
  if (!TOKEN) return;
  const ping = () => fetch("/ping", { headers: { "X-Token": TOKEN } }).catch(() => {});
  ping(); setInterval(ping, 2500);
}
const ready = () => new Promise(res => {
  if (window.EJ_WEB) {                         // wait until the in-browser API (web/boot.js) is up
    const t0 = Date.now();
    const poll = () => (window.EJ_WEBAPI_PROMISE ? window.EJ_WEBAPI_PROMISE.then(() => res(), () => res()) : (Date.now() - t0 > 8000 ? res() : setTimeout(poll, 25)));
    return poll();
  }
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
const LOC = { el: "el-GR", en: "en-GB", de: "de-DE" };
const loc = () => LOC[S.settings.lang] || "en-GB";
const money = n => n.toLocaleString(loc(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const ball = (n, cls = "") => `<span class="ball ${cls}">${n}</span>`;
const balls = (d, cls = "") => `<div class="balls">${d.main.map(n => ball(n, cls)).join("")}<span class="sep"></span>${d.euro.map(n => ball(n, "euro " + cls)).join("")}</div>`;

function toast(msg) {
  const el = $("#toast"); el.textContent = msg; el.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.add("hidden"), 2200);
}
// msg: a string, or a function returning one (re-evaluated when the language changes, so it is always translated)
function setStatus(msg, cls = "") { S.status = { msg, cls }; renderStatus(); }
function renderStatus() {
  const s = $("#status"), st = S.status; if (!s || !st) return;
  s.textContent = typeof st.msg === "function" ? st.msg() : st.msg;
  s.className = "status " + st.cls;
}

/* ---------- i18n / theme ---------- */
async function loadLocale() {
  S.t = await call("get_locale", S.settings.lang);
  document.documentElement.lang = S.settings.lang;
  $$("[data-i18n]").forEach(el => el.textContent = tr(el.dataset.i18n));
  renderLangButton();
  document.title = tr("app.title");
  renderStatus();
}
function applyTheme() {
  document.documentElement.dataset.theme = S.settings.theme;
  $("#btn-theme").textContent = S.settings.theme === "dark" ? "🌙" : "☀️";
}
async function setSetting(k, v) { S.settings = await call("set_setting", k, v); }

/* ---------- countries, languages, flag dropdowns ---------- */
const flagImg = f => `<img class="flag-ico" src="flags/${f}.svg" alt="">`;
const country = () => (S.cat ? S.cat.countries.find(c => c.code === S.settings.country && c.supported) : null);
const cname = (c, lang) => c.name[lang] || c.name.en;
// Generic dropdown. items: [{value, flag, label, sub, disabled}]. `btnHtml(item)` renders the closed button.
function dropdown(host, items, value, onpick, { align = "left", btnHtml } = {}) {
  const cur = items.find(i => i.value === value) || items[0];
  host.classList.add("dd");
  host.innerHTML = `<button type="button" class="dd-btn">${btnHtml ? btnHtml(cur) : `${flagImg(cur.flag)}<span>${esc(cur.label)}</span><i class="caret">▾</i>`}</button>
    <div class="dd-menu ${align}">${items.map(i => `<button type="button" class="dd-item ${i.value === value ? "active" : ""} ${i.disabled ? "disabled" : ""}" data-v="${esc(i.value)}">${flagImg(i.flag)}<span>${esc(i.label)}</span>${i.sub ? `<em>${esc(i.sub)}</em>` : ""}</button>`).join("")}</div>`;
  const btn = $(".dd-btn", host), menu = $(".dd-menu", host);
  btn.onclick = e => { e.stopPropagation(); const open = menu.classList.contains("open"); closeDropdowns(); menu.classList.toggle("open", !open); };
  $$(".dd-item", host).forEach(b => b.onclick = e => { e.stopPropagation(); closeDropdowns(); if (!b.classList.contains("disabled")) onpick(b.dataset.v); });
}
const closeDropdowns = () => $$(".dd-menu.open").forEach(m => m.classList.remove("open"));
const langItems = () => Object.entries(S.cat.languages).map(([k, l]) => ({ value: k, flag: l.flag, label: l.name }));
const countryItems = () => S.cat.countries.map(c => ({ value: c.code, flag: c.flag, label: c.name.own, sub: c.supported ? "" : c.soon, disabled: !c.supported }));
async function changeLanguage(lang) {
  await setSetting("lang", lang); await loadLocale(); await refreshInfo(); renderAll();
}
function renderLangButton() {
  const host = $("#lang-dd"); if (!host || !S.cat) return;
  dropdown(host, langItems(), S.settings.lang, changeLanguage, { align: "right",
    btnHtml: i => `${flagImg(i.flag)}<span>${esc(S.cat.languages[i.value].code)}</span><i class="caret">▾</i>` });
}

/* ---------- splash: choose country, then language ---------- */
async function showSplash() {
  const t = await call("get_locale", "en");     // before a country is chosen nothing says which language to use
  const sp = $("#splash"); sp.classList.remove("hidden");
  const stepCountry = () => {
    sp.innerHTML = `<div class="splash-frame"><div class="splash-head"><h1>${t["splash.title"]}</h1><p>${t["splash.sub"]}</p></div>
      <div class="flags">${S.cat.countries.map(c => `<button class="flag-tile ${c.supported ? "" : "soon"}" data-c="${c.code}" aria-label="${esc(c.name.en)}">
        <img src="flags/${c.flag}.svg" alt=""><span class="flag-name">${esc(c.name.own)}</span>
        ${c.supported ? "" : `<span class="flag-soon">${esc(c.soon)}</span>`}</button>`).join("")}</div></div>`;
    (new URLSearchParams(location.hash.slice(1)).get("hover") || "").split(",").forEach(code => { const t = $(`.flag-tile[data-c="${code}"]`, sp); if (t) t.classList.add("hover"); });   // docs: show the hover state
    $$(".flag-tile", sp).forEach(b => b.onclick = () => { const c = S.cat.countries.find(x => x.code === b.dataset.c); if (c.supported) stepLang(c); });
  };
  const stepLang = c => {
    const opts = [...new Set([c.local_lang, "en"])];
    sp.innerHTML = `<div class="splash-frame"><div class="splash-head"><h1>${t["splash.lang_title"]}</h1><p>${t["splash.lang_sub"]}</p></div>
      <div class="lang-tiles">${opts.map(k => { const l = S.cat.languages[k]; return `<button class="lang-tile" data-l="${k}"><img src="flags/${l.flag}.svg" alt=""><b>${esc(l.name)}</b></button>`; }).join("")}</div>
      <div class="splash-foot"><button class="btn ghost" id="sp-back">${t["splash.back"]}</button></div></div>`;
    $("#sp-back", sp).onclick = stepCountry;
    $$(".lang-tile", sp).forEach(b => b.onclick = async () => {
      await setSetting("country", c.code); await setSetting("lang", b.dataset.l);
      sp.classList.add("hidden"); sp.innerHTML = "";
      await loadLocale(); await refreshInfo(); S.splashDone(); });
  };
  stepCountry();
  await new Promise(res => { S.splashDone = res; });
}

/* ---------- next draw box with countdown ---------- */
function tzOffset(ms, tz) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit" }).formatToParts(new Date(ms)).map(x => [x.type, x.value]));
  return Date.UTC(+p.year, p.month - 1, +p.day, +p.hour, +p.minute, +p.second) - ms;
}
function zonedInstant(y, m, d, hh, mm, tz) {
  const wall = Date.UTC(y, m - 1, d, hh, mm);
  let ms = wall - tzOffset(wall, tz);
  ms = wall - tzOffset(ms, tz);
  return ms;
}
function nextDraw(c) {           // Friday, plus Tuesday since 2022-03-29; draw time and zone are the country's
  const tz = c.tz || "Europe/Athens", [hh, mm] = (c.draw || "21:00").split(":").map(Number), now = Date.now();
  const base = new Date(); base.setUTCDate(base.getUTCDate() - 1);
  for (let i = 0; i < 14; i++) {
    const dt = new Date(base.getTime() + i * 864e5), y = dt.getUTCFullYear(), m = dt.getUTCMonth() + 1, d = dt.getUTCDate(), wd = dt.getUTCDay();
    if (!(wd === 5 || (wd === 2 && Date.UTC(y, m - 1, d) >= Date.UTC(2022, 2, 29)))) continue;
    const at = zonedInstant(y, m, d, hh, mm, tz);
    if (at > now) return { at, iso: `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`, time: c.draw || "21:00" };
  }
  return null;
}
function nextDrawBox() {
  const c = country(); if (!c) return "";
  const n = nextDraw(c); if (!n) return "";
  S.nextAt = n.at;
  const cell = u => `<div class="cd-cell"><b id="cd-${u}">00</b><span>${tr("next." + u)}</span></div>`;
  return `<div class="card next-box"><div class="next-title">⏱ ${tr("next.title")} <b>${fmtDate(n.iso)} - ${n.time}</b></div>
    <div class="countdown">${cell("d")}<i>:</i>${cell("h")}<i>:</i>${cell("m")}<i>:</i>${cell("s")}</div></div>`;
}
function tickCountdown() {
  if (!$("#cd-d")) { clearInterval(S.cd); S.cd = null; return; }
  const left = Math.max(0, Math.floor((S.nextAt - Date.now()) / 1000));
  const parts = { d: Math.floor(left / 86400), h: Math.floor(left % 86400 / 3600), m: Math.floor(left % 3600 / 60), s: left % 60 };
  for (const k in parts) $("#cd-" + k).textContent = String(parts[k]).padStart(2, "0");
  if (left === 0 && S.view === "history") renderHistory();       // draw time reached: pick the following draw
}
function startCountdown() { clearInterval(S.cd); tickCountdown(); S.cd = setInterval(tickCountdown, 1000); }

/* ---------- state / update ---------- */
async function refreshInfo() {
  S.info = await call("get_state");
  S.settings = S.info.settings;
  $("#last-update").textContent = fmtDT(S.info.last_update);
  $("#draw-count").textContent = `${S.info.count} ${tr("top.draws")}`;
  $("#app-version").textContent = "v" + S.info.version;
  const nb = $("#nav-badge"); nb.textContent = S.info.unseen_wins || ""; nb.classList.toggle("hidden", !S.info.unseen_wins);
  updateBadge();
}
function updateBadge() {
  const b = $("#app-badge"), u = S.appUpdate;
  const show = !!(u && u.newer);
  b.classList.toggle("hidden", !show);
  if (show) { b.textContent = "⬆ " + tr("side.newversion", { v: u.latest }); b.onclick = () => showView("settings"); }
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
  else setStatus(() => tr("update.running"));
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
    overlay(false);
    if (p.error) {          // never block the app: show the error and (if there is no data) the empty state
      S.lastError = p.error;
      setStatus(() => tr("update.error", { err: p.error }), "err");
      await refreshInfo(); await renderAll();
      return;
    }
    S.lastError = null;
    const r = p.result || {};
    const wins = (r.tickets && r.tickets.wins) || [];
    if (wins.length) {          // a played ticket won in a draw that was just downloaded
      const total = wins.reduce((a, w) => a + w.total_prize, 0);
      toast(tr("mt.win_toast", { amount: money(total), date: fmtDate(wins[0].target_date) }));
    }
    setStatus(() => (r.added ? tr("update.done", r) : tr("update.uptodate", r)) + (r.verified ? "  " + tr("update.verified") : ""), "ok");
    await refreshInfo(); await renderAll();
  });
}

/* ---------- navigation ---------- */
function showView(v) {
  S.view = v; closeDropdowns();
  $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === v));
  $$(".view").forEach(s => s.classList.toggle("active", s.id === "view-" + v));
  if (v === "stats") renderStats(); else if (v === "ticket") renderTicket(); else if (v === "mytickets") renderMyTickets();
  else if (v === "history") renderHistory(); else renderSettings();
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

/* ---------- empty state (no data: online download failed or not done yet) ---------- */
function renderEmpty(view) {
  killCharts();
  view.innerHTML = `<div class="card empty-state">
    <div style="font-size:3rem">📭</div><h2>${tr("empty.title")}</h2><p class="muted">${tr("empty.text")}</p>
    ${S.lastError ? `<div class="errbox"><b>${tr("empty.error")}:</b> ${esc(S.lastError)}</div>` : ""}
    <div class="actions"><button id="e-import" class="btn primary">${tr("empty.import")}</button>
      <button id="e-retry" class="btn">${tr("empty.retry")}</button>
      <button id="e-diag" class="btn">${tr("empty.diag")}</button></div>
    <div id="e-drop" class="drop" style="width:100%">${tr("empty.drop")}</div><div id="e-diag-out" class="diag" style="width:100%"></div></div>`;
  $("#e-retry", view).onclick = () => runUpdate({ firstRun: true });
  $("#e-import", view).onclick = () => pickAndImport();
  $("#e-diag", view).onclick = () => runDiagnostics($("#e-diag-out", view));
  wireDrop($("#e-drop", view));
}
const afterImport = async r => {
  if (!r) return;
  toast(r.found ? tr("settings.import.done", r) : tr("settings.import.none"));
  S.lastError = null; await refreshInfo(); await renderAll();
};
async function pickAndImport() {
  if (window.pywebview && window.pywebview.api) return afterImport(await call("import_file"));
  const i = document.createElement("input"); i.type = "file"; i.accept = ".csv,.json,.txt";
  i.onchange = () => readFile(i.files[0], afterImport); i.click();
}
function wireDrop(drop) {
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => readFile(e.dataTransfer.files[0], afterImport));
}
async function runDiagnostics(box) {
  box.innerHTML = `<span class="muted">${tr("app.checking")}</span>`;
  const rows = await call("diagnose");
  S.diagReport = rows.map(r => `${r.ok ? "OK " : "ERR"} ${r.name} (${r.ms} ms) ${r.ok ? "" : r.message}`).join("\n");
  box.innerHTML = rows.map(r => `<div><span class="${r.ok ? "ok" : "bad"}">${r.ok ? "✔" : "✘"}</span> <b>${esc(r.name)}</b> <span class="muted">${r.ms} ms</span>${r.ok ? "" : `<div class="muted small">${esc(r.message)}</div>`}</div>`).join("")
    + `<div><button class="btn" id="diag-copy">${tr("settings.diag.copy")}</button></div>`;
  $("#diag-copy", box).onclick = async () => { try { await navigator.clipboard.writeText(`EuroJackpot Analyzer v${S.info.version}\n${S.diagReport}`); toast(tr("ticket.copied")); } catch { toast(S.diagReport); } };
}

/* ---------- draw details (winners / prizes) ---------- */
const nf = n => (n ?? 0).toLocaleString(loc());
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];
const matchText = tier => { const [m, e] = tier.split("+").map(Number);
  return [tr(m === 1 ? "detail.m1" : "detail.mN", { m }), e ? tr(e === 1 ? "detail.e1" : "detail.eN", { e }) : ""].filter(Boolean).join(" + "); };
function whereHtml(cls) {
  const lang = S.settings.lang, byA3 = Object.fromEntries(S.cat.countries.map(c => [c.alpha3, c]));
  const blocks = cls.map((c, i) => c.where && c.where.length ? { c, i } : null).filter(Boolean).map(({ c, i }) => {
    const items = [...c.where].sort((a, b) => b.winners - a.winners).map(w => {
      const cc = byA3[w.alpha3];
      const st = w.region && S.cat.german_states[w.region];
      const label = w.region ? (st ? st[lang] || st.en : w.region) : (cc ? cname(cc, lang) : w.code || w.alpha3);
      return `<span class="where-chip">${cc ? flagImg(cc.flag) : ""}${esc(label)} <b>${nf(w.winners)}×</b></span>`;
    }).join("");
    return `<div class="where-row"><div class="where-cls"><b>${ROMAN[i]}</b> <span class="muted small">${esc(matchText(c.tier))}</span></div><div class="where-chips">${items}</div></div>`;
  });
  return blocks.length ? `<h3 style="margin:1.2rem 0 .6rem">${tr("detail.where")}</h3>${blocks.join("")}<div class="note">${tr("detail.where_hint")}</div>` : "";
}
async function openDraw(dateStr) {
  const d = await call("get_draw", dateStr);
  if (!d) return;
  const det = d.details, cls = det ? det.classes : [], c = country(), official = c && c.layout === "official";
  const hasGr = cls.some(x => x.winners_gr != null);
  const kpi = (l, v) => v != null ? `<div class="kpi"><span class="muted small">${l}</span><b>${v}</b></div>` : "";
  let table = "";
  if (det && official) {         // as on the official eurojackpot.com page: class, match, winners, prize
    const rows = cls.filter(x => !x.greek_only).map((x, i) => `<tr><td><b>${ROMAN[i]}</b></td><td>${esc(matchText(x.tier))}</td>
      <td class="num">${x.winners ? nf(x.winners) + " ×" : `<span class="muted">${tr("detail.no_winner")}</span>`}</td>
      <td class="num">${x.prize > 0 ? money(x.prize) : `<span class="muted">—</span>`}</td></tr>`).join("");
    table = `<table><thead><tr><th>${tr("detail.class")}</th><th>${tr("detail.match")}</th><th class="num">${tr("detail.winners")}</th><th class="num">${tr("detail.prize")}</th></tr></thead><tbody>${rows}</tbody></table>`;
  } else if (det) {              // Greek (Allwyn) layout: all countries / Greece / others
    const rows = cls.map(x => {
      const other = (x.winners_gr != null && !x.greek_only) ? x.winners - x.winners_gr : null;
      const prize = x.prize > 0 ? money(x.prize) : `<span class="muted">${x.winners ? "—" : tr("detail.no_winner")}</span>`;
      return `<tr class="${x.winners_gr > 0 ? "gr-win" : ""}"><td><b>${esc(x.tier.replace("+", " + "))}</b>${x.greek_only ? `<span class="tag-gr">${tr("detail.greek_only")}</span>` : ""}</td>
        <td class="num">${x.greek_only ? "—" : nf(x.winners)}</td>
        <td class="num">${x.winners_gr != null ? nf(x.winners_gr) : "—"}</td>
        <td class="num">${other != null ? nf(other) : "—"}</td><td class="num">${prize}</td></tr>`;
    }).join("");
    table = `<table><thead><tr><th>${tr("detail.tier")}</th><th class="num">${tr("detail.winners_all")}</th><th class="num">${tr("detail.winners_gr")}</th><th class="num">${tr("detail.winners_other")}</th><th class="num">${tr("detail.prize")}</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  $("#detail-body").innerHTML = `
    <div class="dtl-head"><div><h2>${tr("detail.title")} · ${fmtDate(d.date)}${det && det.draw_no ? ` <span class="muted small">(${tr("detail.no", { n: det.draw_no })})</span>` : ""}</h2>
      ${balls(d, "lg")}</div></div>
    ${det ? `<div class="kpis">${kpi(tr("detail.columns_all"), det.columns_all ? nf(det.columns_all) : null)}${official ? "" : kpi(tr("detail.columns_gr"), det.columns_gr ? nf(det.columns_gr) : null)}${kpi(tr("detail.stake"), det.stake_all ? money(det.stake_all) : null)}</div>
    ${table}${whereHtml(cls)}
    ${official ? "" : `<div class="note">${tr("detail.no_country")}${hasGr ? "" : " " + tr("detail.no_greek", { d: "08/03/2024" })}</div>`}`
      : `<div class="empty">${tr("detail.no_details")}</div>`}`;
  $("#detail").classList.remove("hidden");
}
const closeDetail = () => $("#detail").classList.add("hidden");

async function renderStats() {
  const view = $("#view-stats");
  if (!S.info.count) { renderEmpty(view); return; }
  const period = S.settings.period || "all";
  const st = S.stats = await call("get_stats", period);
  const last = st.last_draw;
  view.innerHTML = `
    <div class="hero card" id="hero" style="cursor:pointer" title="${tr("detail.title")}">
      <div><div class="date">${tr("stats.lastdraw")} · ${fmtDate(last.date)} · 🔍</div>${balls(last, "lg")}</div>
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
  $("#hero", view).onclick = () => openDraw(last.date);
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
  if (!S.info.count) { renderEmpty(view); return; }
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
    const cur = S.ticket && !S.ticket.played ? S.ticket : null;       // an unplayed ticket is replaced, not duplicated
    S.ticket = await call("generate", S.settings.columns, S.settings.algo, keep || [], S.settings.period || "all",
      cur ? cur.id : null, cur ? cur.target_date : null);
    if (!keep) S.locks = {};
    S.nextDraws = await call("get_next_draws", 4);
    drawTicket();
  } catch (e) { toast(e.message || String(e)); }
}
const fmtDay = iso => { const d = new Date(iso + "T12:00:00"); return d.toLocaleDateString(loc(), { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" }); };
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
      <button id="copy" class="btn">📋 ${tr("ticket.copy")}</button></div>
    <div class="saved card">
      <div><b>💾 ${tr("tk.saved")}</b> · ${tr("tk.for_draw")}:
        <select id="tk-target">${[...new Set([tk.target_date, ...(S.nextDraws || [])])].sort().map(d => `<option value="${d}" ${d === tk.target_date ? "selected" : ""}>${fmtDay(d)}</option>`).join("")}</select></div>
      <button id="tk-played" class="btn ${tk.played ? "primary" : ""}">${tk.played ? "✅ " + tr("tk.played_on") : "☐ " + tr("tk.played")}</button>
      <div class="muted small" style="flex-basis:100%">${tr("tk.played.hint")}</div></div>`;
  $("#tk-target").onchange = async e => { const t = await call("set_ticket_target", tk.id, e.target.value); S.ticket = { ...S.ticket, target_date: t.target_date }; };
  $("#tk-played").onclick = async () => { const t = await call("set_ticket_played", tk.id, !tk.played); S.ticket = { ...S.ticket, played: t.played }; drawTicket(); };
  $$("[data-lock]", out).forEach(b => b.onclick = () => { const i = +b.dataset.lock; S.locks[i] = !S.locks[i]; drawTicket(); });
  $$("[data-regen]", out).forEach(b => b.onclick = () => { const i = +b.dataset.regen;
    generate(tk.columns.map((c, j) => j === i ? null : c)); });
  $("#copy").onclick = async () => {
    const text = tk.columns.map((c, i) => `${tr("ticket.column")} ${i + 1}: ${c.main.join(" ")} + ${c.euro.join(" ")}`).join("\n") + `\n${tr("ticket.total")}: ${money(tk.total)}`;
    try { await navigator.clipboard.writeText(text); toast(tr("ticket.copied")); } catch { toast(text); }
  };
}

/* ---------- my tickets: history + cross-check with the draws ---------- */
const TK_FILTERS = [["all", "mt.filter.all"], ["played", "mt.filter.played"], ["pending", "mt.filter.pending"], ["winners", "mt.filter.winners"]];
function ticketBalls(c, res, draw) {
  const hitM = new Set(res ? res.main_hit : []), hitE = new Set(res ? res.euro_hit : []);
  const cls = (hit) => res ? (hit ? "hit" : "miss") : "";
  return `<div class="balls">${c.main.map(n => ball(n, "sm " + cls(hitM.has(n)))).join("")}<span class="sep"></span>${c.euro.map(n => ball(n, "euro sm " + cls(hitE.has(n)))).join("")}</div>`;
}
async function renderMyTickets() {
  killCharts();
  const view = $("#view-mytickets");
  const data = await call("get_tickets");
  const f = S.tkFilter || "all";
  const list = data.tickets.filter(t => f === "all" || (f === "played" && t.played) || (f === "pending" && !t.result)
    || (f === "winners" && t.result && t.result.winning_columns));
  const T = data.totals;
  const kpi = (l, v, cls = "") => `<div class="kpi"><span class="muted small">${l}</span><b class="${cls}">${v}</b></div>`;
  view.innerHTML = `<h1>${tr("mt.title")}</h1>
    <div class="kpis">${kpi(tr("mt.spent"), money(T.spent))}${kpi(tr("mt.won"), money(T.won), T.won ? "pos" : "")}
      ${kpi(tr("mt.net"), (T.net > 0 ? "+" : "") + money(T.net), T.net > 0 ? "pos" : T.net < 0 ? "neg" : "")}${kpi(tr("mt.best"), money(T.best))}
      ${kpi(tr("mt.tickets"), tr("mt.count", T))}</div>
    <div class="toolbar"><div class="chips">${TK_FILTERS.map(([k, l]) => `<button class="chip ${k === f ? "active" : ""}" data-f="${k}">${tr(l)}</button>`).join("")}</div></div>
    ${list.length ? list.map(t => ticketCard(t)).join("") : `<div class="card empty">${tr("mt.empty")}</div>`}`;
  $$("[data-f]", view).forEach(b => b.onclick = () => { S.tkFilter = b.dataset.f; renderMyTickets(); });
  $$("[data-played]", view).forEach(b => b.onclick = async () => { await call("set_ticket_played", +b.dataset.played, b.dataset.val !== "1"); renderMyTickets(); });
  $$("[data-del]", view).forEach(b => b.onclick = async () => { if (confirm(tr("mt.delete_confirm"))) { await call("delete_ticket", +b.dataset.del); if (S.ticket && S.ticket.id === +b.dataset.del) S.ticket = null; renderMyTickets(); } });
  $$("[data-draw]", view).forEach(b => b.onclick = () => openDraw(b.dataset.draw));
  if (data.unseen_wins) { await call("mark_tickets_seen"); await refreshInfo(); }
}
function ticketCard(t) {
  const r = t.result;
  const status = !r ? `<span class="status-chip">⏳ ${tr("mt.pending")}</span>`
    : r.winning_columns ? `<span class="status-chip win">🎉 ${r.complete ? tr("mt.win", { amount: money(r.total_prize) }) : tr("mt.win_unknown")}</span>`
    : `<span class="status-chip">${tr("mt.nowin")}</span>`;
  const cols = t.columns.map((c, i) => {
    const rc = r ? r.columns[i] : null;
    const prize = !rc ? "" : rc.wins ? `<span class="prize win">${rc.known ? money(rc.prize) : "?"}</span>` : `<span class="prize">—</span>`;
    return `<div class="col-row ${rc && rc.wins ? "winner" : ""}"><span class="col-no">${tr("ticket.column")} ${i + 1}</span>${ticketBalls(c, rc)}
      ${rc ? `<span class="col-tag">${rc.tier.replace("+", " + ")}</span>` : `<span class="col-tag">${tr("algo.short." + c.algo)}</span>`}<span class="col-price">${prize}</span></div>`;
  }).join("");
  return `<div class="card tk ${r && r.winning_columns && t.played ? "tk-win" : ""}">
    <div class="tk-head"><div><b ${r ? `class="linkish" data-draw="${t.target_date}"` : ""}>${fmtDay(t.target_date)}</b> ${status}
      ${t.played ? "" : `<span class="status-chip dim">${tr("mt.suggestion")}</span>`}
      <div class="muted small">${tr("mt.created")} ${fmtDT(t.created_at)} · ${algoLabel(t.algo)} · ${tr("mt.cost")} ${money(t.price)}</div></div>
      <div class="tk-actions"><button class="btn ghost" data-played="${t.id}" data-val="${t.played ? 1 : 0}">${t.played ? "✅ " + tr("tk.played") : "☐ " + tr("tk.played")}</button>
        <button class="btn ghost" data-del="${t.id}" title="${tr("mt.delete")}">🗑</button></div></div>
    ${r ? `<div class="muted small" style="margin:.5rem 0 .3rem">${tr("mt.winning_numbers")} ${fmtDate(r.draw_date)}:</div>${balls(r.draw, "sm")}` : ""}
    ${r && !r.complete ? `<div class="note">${tr("mt.update_hint")}</div>` : ""}
    <div class="cols" style="margin-top:.6rem">${cols}</div></div>`;
}

/* ---------- history ---------- */
async function renderHistory() {
  killCharts();
  const view = $("#view-history");
  if (!S.info.count) { renderEmpty(view); return; }
  const rows = await call("get_draws", 100);
  view.innerHTML = `${nextDrawBox()}<h1>${tr("history.title")}</h1><div class="muted small" style="margin:-.6rem 0 .8rem">🔍 ${tr("detail.title")}…</div><div class="card"><table>
    <thead><tr><th>${tr("history.date")}</th><th>${tr("history.numbers")}</th><th>${tr("history.source")}</th></tr></thead>
    <tbody>${rows.map(d => `<tr class="click" data-draw="${d.date}"><td class="strong">${fmtDate(d.date)}</td><td>${balls(d, "sm")}</td><td class="muted small">${esc(d.source)}</td></tr>`).join("")}</tbody></table></div>`;
  $$("[data-draw]", view).forEach(r => r.onclick = () => openDraw(r.dataset.draw));
  if ($("#cd-d")) startCountdown();
}

/* ---------- settings ---------- */
function renderSettings() {
  killCharts();
  const s = S.settings;
  const view = $("#view-settings");
  view.innerHTML = `<h1>${tr("settings.title")}</h1>
    <div class="sect">${tr("settings.section.look")}</div>
    <div class="card">
      <div class="row"><span class="strong">${tr("settings.country")}</span><div id="dd-country"></div></div>
      <div class="row"><span class="strong">${tr("settings.language")}</span><div id="dd-lang"></div></div>
      <div class="row"><span class="strong">${tr("settings.theme")}</span><div class="chips">
        <button class="chip ${s.theme === "dark" ? "active" : ""}" data-theme="dark">🌙 ${tr("settings.dark")}</button><button class="chip ${s.theme === "light" ? "active" : ""}" data-theme="light">☀️ ${tr("settings.light")}</button></div></div>
    </div>

    <div class="sect">🎰 ${tr("settings.section.draws")}</div>
    <div class="card">
      ${country() ? `<div class="row"><div><div class="strong">${tr("settings.price")}</div><div class="muted small">${tr("settings.price.hint", { price: money(S.info.default_price) })}<br>${tr("price.note." + s.country)}</div></div>
        <div class="price-edit"><input id="price-in" type="number" min="0.1" step="0.1" value="${S.info.price.toFixed(2)}"><span>€</span><button id="price-reset" class="btn ghost">${tr("settings.price.reset")}</button></div></div>` : ""}
      <div class="row"><div><div class="strong">${tr("settings.auto_update")}</div><div class="muted small">${tr("settings.auto_update.hint")}</div></div>
        <button id="sw-auto" class="switch ${s.auto_update ? "on" : ""}" aria-label="auto update"></button></div>
      <div class="row"><div><div class="strong">${tr("settings.data")}</div><div class="muted small">${S.info.count} ${tr("top.draws")} · ${fmtDate(S.info.last_draw)}<br>${tr("settings.sources")}</div></div>
        <button id="upd" class="btn primary">🔄 ${tr("settings.update_now")}</button></div>
      <div class="row" style="display:block"><div class="strong">${tr("settings.export")}</div><div class="muted small">${tr("settings.export.hint")}</div>
        <div class="btn-row"><button class="btn" data-export="json">💾 ${tr("settings.export.json")}</button><button class="btn" data-export="csv">📄 ${tr("settings.export.csv")}</button></div></div>
      <div class="row" style="display:block"><div class="strong">${tr("settings.import")}</div><div class="muted small">${tr("settings.import.hint")}</div>
        <div id="drop" class="drop"><button id="pick" class="btn">${tr("settings.import.choose")}</button></div></div>
      <div class="row" style="display:block"><div class="strong">${tr("settings.diag")}</div><div class="muted small">${tr("settings.diag.hint")}</div>
        <div class="btn-row"><button id="diag" class="btn">🩺 ${tr("settings.diag.run")}</button></div><div id="diag-out" class="diag"></div></div>
    </div>

    <div class="sect">⬆️ ${tr("settings.section.app")}</div>
    <div class="card">
      <div class="row"><div><div class="strong">${tr("app.version")}: v${S.info.version}</div><div class="muted small">${tr("app.distinction")}</div></div>
        <button id="app-check" class="btn primary">${tr("app.check")}</button></div>
      <div class="row"><div class="strong">${tr("app.auto_check")}</div>
        <button id="sw-appcheck" class="switch ${s.check_app_updates ? "on" : ""}" aria-label="app update check"></button></div>
      <div id="app-upd-out"></div>
    </div>`;
  dropdown($("#dd-country"), countryItems(), s.country, async code => { await setSetting("country", code); await refreshInfo(); renderSettings(); }, { align: "right" });
  dropdown($("#dd-lang"), langItems(), s.lang, async code => { await setSetting("lang", code); await loadLocale(); await refreshInfo(); renderSettings(); }, { align: "right" });
  const pr = $("#price-in");
  if (pr) {
    pr.onchange = async () => { const v = parseFloat(String(pr.value).replace(",", ".")); const prices = { ...(S.settings.prices || {}) };
      if (v > 0) prices[S.settings.country] = Math.round(v * 100) / 100; else delete prices[S.settings.country];
      await setSetting("prices", prices); await refreshInfo(); renderSettings(); };
    $("#price-reset").onclick = async () => { const prices = { ...(S.settings.prices || {}) }; delete prices[S.settings.country]; await setSetting("prices", prices); await refreshInfo(); renderSettings(); };
  }
  $$("[data-theme]", view).forEach(b => b.onclick = async () => { await setSetting("theme", b.dataset.theme); applyTheme(); renderSettings(); });
  $("#sw-auto").onclick = async e => { await setSetting("auto_update", !S.settings.auto_update); e.currentTarget.classList.toggle("on", S.settings.auto_update); };
  $("#sw-appcheck").onclick = async e => { await setSetting("check_app_updates", !S.settings.check_app_updates); e.currentTarget.classList.toggle("on", S.settings.check_app_updates); };
  $("#upd").onclick = () => runUpdate();
  $$("[data-export]", view).forEach(b => b.onclick = () => exportData(b.dataset.export));
  $("#pick").onclick = () => pickAndImport();
  wireDrop($("#drop"));
  $("#diag").onclick = () => runDiagnostics($("#diag-out"));
  $("#app-check").onclick = () => doAppCheck();
  renderAppUpdate();
}
async function exportData(fmt) {
  try {
    if (window.EJ_WEBAPI) {                    // web app / Android: share sheet ("Save to Files") or a download
      const r = await call("export_text", fmt);
      await window.EJ_WEBAPI.save_text(r.filename, r.text);
      toast(tr("settings.export.done", r));
    } else if (window.pywebview && window.pywebview.api) {
      const r = await call("export_file", fmt);
      if (r) toast(tr("settings.export.done", r));
    } else {                         // browser / dev mode: normal download
      const r = await call("export_text", fmt);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([r.text], { type: "text/plain;charset=utf-8" }));
      a.download = r.filename; a.click();
      toast(tr("settings.export.done", r));
    }
  } catch (e) { toast(e.message || String(e)); }
}
function readFile(file, cb) {
  if (!file) return;
  const fr = new FileReader();
  fr.onload = async () => cb(await call("import_text", file.name, fr.result));
  fr.readAsText(file);
}

/* ---------- application updates (GitHub releases) – separate from draw updates ---------- */
async function doAppCheck() {
  const out = $("#app-upd-out"); if (out) out.innerHTML = `<div class="muted" style="padding:.8rem 0">${tr("app.checking")}</div>`;
  S.appUpdate = await call("check_app_update");
  updateBadge(); renderAppUpdate();
}
function renderAppUpdate() {
  const out = $("#app-upd-out"); if (!out) return;
  const r = S.appUpdate;
  if (!S.info.repo_configured) { out.innerHTML = `<div class="note">${tr("app.not_configured")}</div>`; return; }
  if (!r) { out.innerHTML = ""; return; }
  if (r.error) { out.innerHTML = `<div class="note">${r.error === "no releases yet" ? tr("app.no_releases") : tr("app.check_error", { err: esc(r.error) })}</div>`; return; }
  if (!r.newer) { out.innerHTML = `<div class="note" style="color:var(--good)">✔ ${tr("app.uptodate", { v: r.current })}</div>`; return; }
  out.innerHTML = `<div style="padding-top:.8rem"><div class="strong" style="color:var(--good)">⬆ ${tr("app.available", { v: r.latest, cur: r.current })}</div>
    ${r.notes ? `<div class="muted small" style="margin-top:.5rem">${tr("app.notes")}:</div><div class="notes">${esc(r.notes)}</div>` : ""}
    <div class="btn-row">${r.installable ? `<button id="app-install" class="btn primary">${tr("app.install")}</button>` : `<span class="note">${tr("app.manual_install")}</span>`}
      ${r.url ? `<button id="app-page" class="btn">${tr("app.open_page")}</button>` : ""}</div>
    <div id="app-prog" class="note"></div></div>`;
  const page = $("#app-page"); if (page) page.onclick = () => (window.pywebview || window.EJ_WEBAPI) ? call("open_url", r.url) : window.open(r.url, "_blank");
  const inst = $("#app-install"); if (inst) inst.onclick = () => installApp(inst);
}
async function installApp(btn) {
  btn.disabled = true;
  const box = $("#app-prog");
  const st = await call("start_app_update");
  if (st.error) { box.textContent = tr("app.check_error", { err: st.error }); btn.disabled = false; return; }
  const iv = setInterval(async () => {
    const p = await call("get_app_update_progress");
    const pct = p.total ? Math.round(100 * p.done / p.total) : 0;
    box.textContent = p.restart ? tr("app.restarting") : tr("app.installing", { pct });
    if (p.error) { clearInterval(iv); box.textContent = tr("app.check_error", { err: p.error }); btn.disabled = false; }
    else if (!p.running && !p.restart) clearInterval(iv);
  }, 400);
}

/* ---------- iPhone: how to install the web app ---------- */
function installTip() {
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = window.navigator.standalone || (window.matchMedia && matchMedia("(display-mode: standalone)").matches);
  let dismissed = false; try { dismissed = localStorage.getItem("ej_install_tip") === "1"; } catch (e) { /* private mode */ }
  if (!window.EJ_WEB || window.Capacitor || !ios || standalone || dismissed || !S.t["web.install_ios"] || new URLSearchParams(location.hash.slice(1)).get("static")) return;
  const el = document.createElement("div"); el.className = "install-tip";
  el.innerHTML = `<span>${esc(tr("web.install_ios"))}</span><button class="btn ghost" aria-label="close">✕</button>`;
  $("button", el).onclick = () => { try { localStorage.setItem("ej_install_tip", "1"); } catch (e) { /* ignore */ } el.remove(); };
  document.body.appendChild(el);
}

/* ---------- boot ---------- */
async function boot() {
  await ready();
  if (!(window.pywebview && window.pywebview.api)) startHeartbeat();
  await refreshInfo();
  S.cat = await call("get_countries");
  applyTheme();
  const hp0 = new URLSearchParams(location.hash.slice(1));      // dev/docs helper: #country=DE&lang=de&splash=1
  if (hp0.get("safe")) { document.documentElement.style.setProperty("--safe-top", hp0.get("safe") + "px"); document.documentElement.style.setProperty("--safe-bottom", "20px"); }   // docs: notch / status bar
  if (hp0.get("country") && hp0.get("country") !== S.settings.country) await setSetting("country", hp0.get("country"));
  if (hp0.get("lang") && hp0.get("lang") !== S.settings.lang) await setSetting("lang", hp0.get("lang"));
  if (hp0.get("splash")) await setSetting("country", "");
  await loadLocale();
  await refreshInfo();
  if (!S.settings.country) await showSplash();
  $$(".nav-btn").forEach(b => b.onclick = () => showView(b.dataset.view));
  $("#btn-theme").onclick = async () => { await setSetting("theme", S.settings.theme === "dark" ? "light" : "dark"); applyTheme(); renderAll(); };
  document.addEventListener("click", closeDropdowns);
  $("#btn-full").onclick = () => { if (window.pywebview) call("toggle_fullscreen"); else if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); };
  if (window.EJ_WEB && !document.fullscreenEnabled) $("#btn-full").classList.add("hidden");
  installTip();
  $("#btn-update").onclick = () => runUpdate();
  $("#ov-btn").onclick = () => runUpdate({ firstRun: true });
  $("#detail-close").onclick = closeDetail;
  $("#detail").addEventListener("click", e => { if (e.target.id === "detail") closeDetail(); });
  window.addEventListener("keydown", e => { if (e.key === "F11") { e.preventDefault(); $("#btn-full").click(); } if (e.key === "Escape") closeDetail(); });
  window.addEventListener("resize", () => S.charts.forEach(c => c.resize()));
  if (S.settings.check_app_updates && S.info.repo_configured) {     // quiet background check, shows a badge only
    call("check_app_update").then(r => { S.appUpdate = r; updateBadge(); }).catch(() => {});
  }
  if (S.info.seed && S.info.count) setStatus(() => tr("update.seed", S.info.seed));
  const hp = new URLSearchParams(location.hash.slice(1));      // dev/docs helper: #view=ticket&lang=en&theme=light&draw=2026-10-13&gen=12
  if (hp.get("theme") && hp.get("theme") !== S.settings.theme) { await setSetting("theme", hp.get("theme")); applyTheme(); }
  if (hp.get("static")) document.body.classList.add("no-anim");   // screenshots: no fade-in captured half-way
  if (hp.get("demo_update")) {          // docs: show the update screen; real release data, install button forced on
    S.appUpdate = await call("check_app_update"); S.appUpdate.installable = true; updateBadge();
  }
  if (hp.get("view")) S.view = hp.get("view");
  if (!S.info.count) { await runUpdate({ firstRun: true }); }
  else {
    if (hp.get("demo")) {              // docs: three demo tickets (two checked against past draws, one waiting)
      const mk = async (n, target) => { const t = await call("generate", n, "auto_column", [], "all", null, target); await call("set_ticket_played", t.id, true); };
      await mk(5, "2026-10-13"); await mk(3, "2026-10-09"); await mk(4, (await call("get_next_draws", 1))[0]);
      await call("evaluate_tickets"); await refreshInfo();
    }
    await renderAll();
    if (hp.get("gen")) { await setSetting("columns", +hp.get("gen")); await setSetting("algo", "auto_column"); await renderTicket(); await generate(); }
    if (hp.get("draw")) await openDraw(hp.get("draw"));
    if (hp.get("menu")) { const b = $("#" + hp.get("menu") + " .dd-btn"); if (b) b.click(); }       // docs: show an open dropdown
    if (S.settings.auto_update && !hp.toString()) runUpdate();
  }
}
boot().catch(e => { console.error(e); setStatus(String(e), "err"); });
