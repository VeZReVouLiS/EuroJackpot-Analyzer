/* The Python API (app/api.py) re-implemented in the browser: the same methods the UI calls through pywebview,
 * backed by IndexedDB and by the draws file that the project publishes on GitHub Pages (updated automatically).
 * Used by the web app (iPhone / any browser) and by the Android app. */
import * as core from "./core.js";
import { openStore } from "./store.js";
import { VERSION, REPO, PAGES } from "./version.js";

const DEFAULTS = { lang: "el", country: "", prices: {}, sync_token: "", sync_gist: "", theme: "dark", auto_update: true, check_app_updates: true,
  period: "all", columns: 5, algo: core.AUTO_TICKET };
const isNative = () => !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
const plugin = (name) => (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins[name]) || null;
const nowUtc = () => new Date().toISOString();                       // change times travel between devices: UTC with milliseconds
const newUid = (created, target) => `${created}|${target}|${Math.floor(Math.random() * 65536).toString(16).padStart(4, "0")}`;
const SYNC_FILE = "eurojackpot-tickets.json", SYNC_DESC = "EuroJackpot Analyzer tickets (synced)";
const nowIso = () => { const n = new Date(), p = (x) => String(x).padStart(2, "0"); return `${n.getFullYear()}-${p(n.getMonth() + 1)}-${p(n.getDate())}T${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`; };
const isNewer = (a, b) => { const x = String(a).replace(/^v/, "").split(".").map(Number), y = String(b).replace(/^v/, "").split(".").map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i++) { if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0); } return false; };

export async function createApi() {
  const store = await openStore();
  let draws = store.get("draws", []);
  let byDate = new Map(draws.map((d) => [d.date, d]));
  let seedInfo = null, latestApk = null;
  let appProgress = { running: false, done: 0, total: 0, error: null, restart: false };
  let progress = { running: false, done: 0, total: 0, error: null, errors: null, result: null };
  let catalogue = null;
  const locales = new Map();

  const settings = () => ({ ...DEFAULTS, ...(store.get("settings", {})) });
  const tickets = () => store.get("tickets", []);
  const saveTickets = (t) => store.set("tickets", t);

  /* ---- countries / price ---- */
  async function getCountries() {
    if (!catalogue) catalogue = await (await fetch("countries.json")).json();
    return catalogue;
  }
  const supported = (code) => (catalogue ? catalogue.countries.find((c) => c.code === code && c.supported) : null);
  const defaultPrice = (code) => { const c = supported(code); return c ? Number(c.price) : core.COLUMN_PRICE; };
  function effectivePrice(s) {
    const custom = (s.prices || {})[s.country], v = parseFloat(custom);
    return custom !== undefined && custom !== null && v > 0 ? Math.round(v * 100) / 100 : defaultPrice(s.country);
  }

  /* ---- draws data (a file published with the web app; the same file seeds a fresh install) ---- */
  async function fetchDataset() {
    const urls = [];
    const here = new URL("data/draws.json", location.href).href;
    if (isNative() || (!here.startsWith(PAGES) && !/^(localhost|127\.|\[::1\])/.test(location.hostname))) urls.push(PAGES + "data/draws.json");     // the freshest copy first (native app / other host)
    urls.push(here);
    const errors = {};
    for (const url of urls) {
      try {
        const r = await fetch(url, { cache: "no-cache" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const list = core.parseText(await r.text(), "draws.json");
        if (list.length) return { draws: list, source: url };
        throw new Error("no draws in the file");
      } catch (e) { errors[new URL(url).host || url] = String(e.message || e); }
    }
    const err = new Error(Object.entries(errors).map(([k, v]) => `${k}: ${v}`).join("; "));
    err.errors = errors;
    throw err;
  }
  function mergeDraws(list) {
    let added = 0;
    for (const r of list) {
      const e = byDate.get(r.date);
      if (!e) { added++; byDate.set(r.date, { date: r.date, main: r.main, euro: r.euro, source: r.source, details: r.details || null }); }
      else { e.main = r.main; e.euro = r.euro; e.source = r.source || e.source; e.details = r.details || e.details; }
    }
    draws = [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1));
    store.set("draws", draws);
    return added;
  }
  async function ensureData() {
    if (draws.length) return;
    try { const ds = await fetchDataset(); mergeDraws(ds.draws); seedInfo = { count: draws.length, last: draws[draws.length - 1].date }; store.set("seed_loaded", nowIso()); }
    catch (e) { /* offline and nothing bundled: the UI shows the empty state with manual import */ }
  }

  /* ---- tickets ---- */
  function evaluateTickets() {
    const all = tickets(); let evaluated = 0; const wins = []; let changed = false;
    for (const t of all) {
      const res = t.result;
      if (res && res.complete) continue;
      const draw = byDate.get(t.target_date);
      if (!draw) continue;
      if (res && !draw.details) continue;
      const nw = core.evaluateTicket(t.columns, draw);
      t.result = nw; changed = true;
      if (nw.winning_columns && !res) t.seen = false;
      if (!res) { evaluated++; if (nw.winning_columns && t.played) wins.push({ id: t.id, target_date: t.target_date, total_prize: nw.total_prize }); }
    }
    if (changed) saveTickets(all);
    return { evaluated, wins };
  }
  const sortedTickets = () => [...tickets()].sort((a, b) => (a.target_date < b.target_date ? 1 : a.target_date > b.target_date ? -1 : b.id - a.id));
  const r2 = (x) => Math.round((x + Number.EPSILON) * 100) / 100;

  function windowFor(period, last) {
    if (!period || period === "all" || !last) return [null, null];
    if (period.startsWith("custom:")) { const [, a, b] = period.split(":"); return [a || null, b || null]; }
    const years = { "1y": 1, "3y": 3, "5y": 5, "10y": 10 }[period];
    if (years) return [core.addDays(last, -365 * years), null];
    return [null, null];
  }

  function cleanColumns(columns) {
    const out = (columns || []).map((c) => {
      const main = core.sortNumbers(c.main.map(Number)), euro = core.sortNumbers(c.euro.map(Number));
      if (!core.validColumn(main, euro)) throw new Error("invalid column");
      return { main, euro, algo: "manual" };
    });
    if (out.length < 1 || out.length > core.MAX_COLUMNS) throw new Error(`columns must be 1..${core.MAX_COLUMNS}`);
    return out;
  }

  const api = {
    /* settings */
    async get_settings() { return settings(); },
    async set_setting(key, value) {
      const s = settings();
      if (key in DEFAULTS) { s[key] = value; await store.set("settings", s); }
      return s;
    },
    async get_locale(lang) {
      const load = async (n) => {
        if (!locales.has(n)) {
          let j = null;
          try { const r = await fetch(`locales/${n}.json`); if (r.ok) j = await r.json(); } catch (e) { /* offline and not cached */ }
          if (j) locales.set(n, j);
        }
        return locales.get(n) || null;
      };
      const name = /^[a-z]{2}$/.test(lang) ? lang : "en";
      return (await load(name)) || (await load("en")) || {};
    },
    async get_countries() { return getCountries(); },

    /* state */
    async get_state() {
      await getCountries();
      const s = settings();
      return { count: draws.length, last_draw: draws.length ? draws[draws.length - 1].date : null, last_update: store.get("last_update", null),
        seed: seedInfo, settings: s, price: effectivePrice(s), default_price: defaultPrice(s.country), max_columns: core.MAX_COLUMNS,
        algos: core.ALGOS, euro_max: core.currentEuroMax(), version: VERSION, repo_configured: true,
        unseen_wins: (await api.get_tickets()).unseen_wins, sync: !!s.sync_token, web: true, native: isNative() };
    },

    /* draw data updates */
    async start_update() {
      if (progress.running) return progress;
      progress = { running: true, done: 0, total: 1, error: null, errors: null, result: null };
      (async () => {
        try {
          const ds = await fetchDataset();
          const added = mergeDraws(ds.draws);
          store.set("last_update", nowIso());
          const res = { added, total: draws.length, last_draw: draws[draws.length - 1].date, source: "eurojackpot-analyzer", backfilled: 0, verified: null };
          res.tickets = evaluateTickets();
          progress.result = res;
        } catch (e) { progress.error = String(e.message || e); progress.errors = e.errors || null; }
        progress.running = false; progress.done = progress.total;
      })();
      return progress;
    },
    async get_progress() { return { ...progress }; },
    async diagnose() {
      const out = [];
      const checks = [["draws data (GitHub Pages)", () => fetch(PAGES + "data/draws.json", { cache: "no-cache", method: "HEAD" })],
        ["github.com (releases)", () => fetch(`https://api.github.com/repos/${REPO}/releases/latest`)]];
      for (const [name, fn] of checks) {
        const t = Date.now();
        try { const r = await fn(); out.push({ name, ok: r.ok || r.status === 404, message: r.ok ? "OK" : `HTTP ${r.status}`, ms: Date.now() - t }); }
        catch (e) { out.push({ name, ok: false, message: String(e.message || e), ms: Date.now() - t }); }
      }
      return out;
    },

    /* statistics */
    async get_stats(period = "all") {
      const last = draws.length ? draws[draws.length - 1].date : null;
      let [since, until] = windowFor(period, last);
      if (period && period.startsWith("last:")) { const n = +period.split(":")[1]; since = draws.length >= n ? draws[draws.length - n].date : null; }
      const s = core.computeStats(draws, since, until);
      s.recent = draws.slice(-10).reverse();
      return s;
    },
    async get_draws(limit = 100) { return draws.slice(-Math.floor(limit)).reverse(); },
    async get_draw(dateStr) {
      const d = byDate.get(dateStr);
      if (!d) return null;
      return { ...d, details: d.details || null, euro_max: core.euroMax(dateStr), greek_data: dateStr >= "2024-03-08" };
    },

    /* tickets */
    async generate(columns, algo, keep = [], period = "all", ticketId = null, targetDate = null) {
      const s = await api.get_stats(period);
      if (!s.n_draws) throw new Error("no data");
      const k = (keep || []).map((c) => (c ? c : null));
      const t = core.generateTicket(s, Number(columns), algo, undefined, k, effectivePrice(settings()));
      const all = tickets();
      const existing = ticketId ? all.find((x) => x.id === Number(ticketId)) : null;
      let tid, target, played = false;
      if (existing && !existing.played && !existing.result) {
        target = targetDate || existing.target_date;
        Object.assign(existing, { columns: t.columns, algo, price: t.total, target_date: target, updated_at: nowUtc() });
        tid = existing.id;
      } else {
        target = targetDate || core.nextDrawDates(new Date(), 1)[0];
        tid = store.get("ticket_seq", 1); await store.set("ticket_seq", tid + 1);
        const created = nowIso();
        all.push({ id: tid, uid: newUid(created, target), updated_at: nowUtc(), created_at: created, target_date: target, algo, columns: t.columns, price: t.total, played: false, result: null, seen: false });
      }
      await saveTickets(all);
      return { ...t, id: tid, target_date: target, played };
    },
    async save_manual_ticket(columns, targetDate = null) {
      const cols = cleanColumns(columns), price = effectivePrice(settings());
      const target = targetDate || core.nextDrawDates(new Date(), 1)[0];
      if (!core.parseDate(target)) throw new Error("invalid date");
      const all = tickets(), tid = store.get("ticket_seq", 1); await store.set("ticket_seq", tid + 1);
      const created = nowIso();
      const t = { id: tid, uid: newUid(created, target), updated_at: nowUtc(), created_at: created, target_date: target, algo: "manual", columns: cols, price: r2(price * cols.length), played: false, result: null, seen: false };
      all.push(t); await saveTickets(all);
      return t;
    },
    async analyze_columns(columns) {
      const cols = cleanColumns(columns), s = settings();
      return core.analyze(cols, draws, core.computeStats(draws), effectivePrice(s), s.country || "");
    },
    async get_next_draws(n = 4) { return core.nextDrawDates(new Date(), Number(n)); },
    async set_ticket_played(id, played) { const all = tickets(); const t = all.find((x) => x.id === Number(id)); if (t) { t.played = !!played; t.updated_at = nowUtc(); await saveTickets(all); } return t || null; },
    async set_ticket_target(id, target) {
      const all = tickets(); const t = all.find((x) => x.id === Number(id));
      if (t && !t.result) { if (!core.parseDate(target)) throw new Error("invalid date"); t.target_date = target; t.updated_at = nowUtc(); await saveTickets(all); }
      return t || null;
    },
    async delete_ticket(id) {
      const gone = tickets().find((x) => x.id === Number(id));
      if (gone) { const tombs = store.get("tombstones", {}); tombs[core.uidOf(gone)] = nowUtc(); await store.set("tombstones", tombs); }
      await saveTickets(tickets().filter((x) => x.id !== Number(id))); return true;
    },

    /* ticket sync between devices through a private gist of the user */
    async sync_status() { const s = settings(); return { connected: !!s.sync_token, gist: s.sync_gist || null, last: store.get("sync_last", null) }; },
    async sync_connect(token) {
      token = String(token || "").trim();
      if (!token) throw new Error("token is empty");
      await api.set_setting("sync_token", token); await api.set_setting("sync_gist", "");
      try { return await api.sync_now(); } catch (e) { await api.set_setting("sync_token", ""); throw e; }
    },
    async sync_disconnect() { await api.set_setting("sync_token", ""); await api.set_setting("sync_gist", ""); return api.sync_status(); },
    async sync_now() {
      const s = settings();
      if (!s.sync_token) throw new Error("not connected");
      let gistId = s.sync_gist || null, remote = null;
      const call = async (method, path, body) => {
        let r;
        try {
          r = await fetch("https://api.github.com" + path, { method, headers: { Authorization: `Bearer ${s.sync_token.trim()}`, Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", ...(body ? { "Content-Type": "application/json" } : {}) }, body: body ? JSON.stringify(body) : undefined });
        } catch (e) { throw new Error(`No connection to GitHub: ${e.message || e}`); }
        if (r.status === 401) throw new Error("The GitHub token is not valid (401).");
        if (r.status === 403) throw new Error("GitHub refused the request (403): the token needs the gist permission.");
        if (r.status === 404 && gistId) throw new Error("The sync gist was not found (404). Disconnect and connect again.");
        if (!r.ok) throw new Error(`GitHub error ${r.status}`);
        return r.json();
      };
      if (!gistId) {
        for (const g of (await call("GET", "/gists?per_page=100")) || []) if (g.files && g.files[SYNC_FILE]) { gistId = g.id; break; }
        if (!gistId) { const g = await call("POST", "/gists", { description: SYNC_DESC, public: false, files: { [SYNC_FILE]: { content: JSON.stringify(core.syncDoc([], {})) } } }); gistId = g.id; }
      }
      const g = await call("GET", `/gists/${gistId}`), f = g.files && g.files[SYNC_FILE];
      if (f) { if (f.truncated) throw new Error("The sync file is too large."); try { remote = f.content && f.content.trim() ? JSON.parse(f.content) : null; } catch { throw new Error("The sync file is damaged."); } }
      const all = tickets(), tombs0 = store.get("tombstones", {});
      const { tickets: merged, tombstones } = core.mergeTickets(all, remote, tombs0);
      let added = 0, updated = 0, seq = store.get("ticket_seq", 1);
      const byUid = new Map(all.map((t) => [core.uidOf(t), t])), next = [];
      for (const m of merged) {
        const cur = byUid.get(m.uid);
        if (!cur) { next.push({ id: seq++, ...m, result: null, seen: false }); added++; }
        else if (m.updated_at > (cur.updated_at || cur.created_at)) {
          const reset = JSON.stringify(cur.columns) !== JSON.stringify(m.columns) || cur.target_date !== m.target_date;
          next.push({ ...cur, ...m, id: cur.id, ...(reset ? { result: null, seen: false } : {}) }); updated++;
        } else next.push(cur);
      }
      const removed = all.filter((t) => !merged.some((m) => m.uid === core.uidOf(t))).length;
      await saveTickets(next); await store.set("ticket_seq", seq); await store.set("tombstones", tombstones);
      const doc = core.syncDoc(merged, tombstones);
      const pushed = !remote || JSON.stringify({ t: remote.tickets, d: remote.tombstones }) !== JSON.stringify({ t: doc.tickets, d: doc.tombstones });
      if (pushed) await call("PATCH", `/gists/${gistId}`, { files: { [SYNC_FILE]: { content: JSON.stringify(doc) } } });
      await api.set_setting("sync_gist", gistId); await store.set("sync_last", nowIso());
      evaluateTickets();
      return { added, updated, removed, pushed, tickets: merged.length, ...(await api.sync_status()) };
    },
    async evaluate_tickets() { return evaluateTickets(); },
    async get_tickets() {
      const list = sortedTickets(), played = list.filter((t) => t.played), done = played.filter((t) => t.result);
      const spent = r2(played.reduce((a, t) => a + t.price, 0)), won = r2(done.reduce((a, t) => a + t.result.total_prize, 0));
      return { tickets: list, totals: { tickets: list.length, played: played.length, evaluated: done.length,
          pending: played.filter((t) => !t.result).length, spent, won, net: r2(won - done.reduce((a, t) => a + t.price, 0)),
          best: Math.max(0, ...done.map((t) => t.result.total_prize)) },
        unseen_wins: list.filter((t) => t.played && t.result && t.result.winning_columns && !t.seen).length };
    },
    async mark_tickets_seen() { const all = tickets(); for (const t of all) if (t.result && !t.seen) t.seen = true; await saveTickets(all); return true; },

    /* import / export */
    async import_text(filename, text) {
      const before = draws.length;
      const list = core.parseText(text, filename);
      if (list.length) { mergeDraws(list); store.set("last_import", nowIso()); }
      const res = { found: list.length, added: draws.length - before, total: draws.length, last_draw: draws.length ? draws[draws.length - 1].date : null };
      const incoming = core.parseTickets(text), all = tickets(), have = new Set(all.map((t) => t.created_at + "|" + t.target_date));
      let n = 0, seq = store.get("ticket_seq", 1);
      for (const t of incoming) { if (have.has(t.created_at + "|" + t.target_date)) continue; all.push({ ...t, id: seq++, seen: false }); n++; }
      if (n) { await saveTickets(all); await store.set("ticket_seq", seq); }
      res.tickets = n;
      evaluateTickets();
      return res;
    },
    async export_text(fmt = "json") {
      const text = fmt === "csv" ? core.toCsv(draws) : core.toJson(draws, tickets(), VERSION);
      return { filename: core.defaultFilename(fmt === "csv" ? "csv" : "json"), text, count: draws.length };
    },
    /* save/share a text file: native share sheet (Android app), Web Share with a file (iPhone), else a normal download */
    async save_text(filename, text) {
      const mime = filename.endsWith(".csv") ? "text/csv" : "application/json";
      const fs = plugin("Filesystem"), share = plugin("Share");
      if (isNative() && fs && share) {
        const w = await fs.writeFile({ path: filename, data: text, directory: "CACHE", encoding: "utf8" });
        await share.share({ title: filename, url: w.uri, dialogTitle: filename });
        return true;
      }
      const file = new File([text], filename, { type: mime });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        try { await navigator.share({ files: [file], title: filename }); return true; } catch (e) { if (e && e.name === "AbortError") return true; }
      }
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], { type: mime + ";charset=utf-8" }));
      a.download = filename; document.body.appendChild(a); a.click(); a.remove();
      return true;
    },
    async import_file() { return null; },
    async export_file() { return null; },

    /* the application itself */
    async check_app_update() {
      const res = { current: VERSION, latest: null, newer: false, notes: "", url: null, installable: false, error: null, configured: true };
      if (isNative()) {                                  // Android app: new APK on GitHub (installed by the user)
        try {
          const r = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, { headers: { Accept: "application/vnd.github+json" } });
          if (r.status === 404) { res.error = "no releases yet"; return res; }
          if (!r.ok) { res.error = `HTTP ${r.status}`; return res; }
          const rel = await r.json();
          res.latest = String(rel.tag_name || "").replace(/^v/, ""); res.newer = isNewer(res.latest, VERSION); res.notes = rel.body || ""; res.url = rel.html_url;
          const asset = (n) => (rel.assets || []).find((a) => a.name === n);
          const apk = asset("EuroJackpotApp-android.apk"), sha = asset("EuroJackpotApp-android.apk.sha256");
          latestApk = apk && sha ? { apkUrl: apk.browser_download_url, shaUrl: sha.browser_download_url } : null;
          res.installable = !!(latestApk && plugin("ApkInstaller"));
        } catch (e) { res.error = String(e.message || e); }
        return res;
      }
      try {                                              // web app: the service worker updates it by itself
        if (navigator.serviceWorker) { const reg = await navigator.serviceWorker.getRegistration(); if (reg) reg.update(); }
        const v = await (await fetch("version.json", { cache: "no-store" })).json();
        res.latest = v.version; res.newer = false;
      } catch (e) { res.latest = VERSION; }
      return res;
    },
    /* Android: download the new APK inside the app and hand it to the system installer (the user confirms) */
    async start_app_update() {
      const inst = plugin("ApkInstaller");
      if (!isNative() || !inst || !latestApk) return { error: "not available" };
      if (appProgress.running) return appProgress;
      const can = await inst.canInstall();
      if (!can.allowed) { await inst.openSettings(); return { running: false, done: 0, total: 0, error: null, restart: false, needs_permission: true }; }
      appProgress = { running: true, done: 0, total: 0, error: null, restart: false, installing: false };
      const handle = await inst.addListener("progress", (p) => { appProgress.done = p.done; appProgress.total = p.total; });
      inst.downloadAndInstall(latestApk)
        .then(() => { appProgress.running = false; appProgress.installing = true; })
        .catch((e) => { appProgress.running = false; appProgress.error = String((e && e.message) || e); })
        .finally(() => handle.remove());
      return appProgress;
    },
    async get_app_update_progress() { return { ...appProgress }; },
    async open_url(url) {
      const b = plugin("Browser");
      if (isNative() && b) { await b.open({ url }); return true; }
      window.open(url, "_blank", "noopener");
      return true;
    },
    async toggle_fullscreen() {
      const el = document.documentElement;
      if (document.fullscreenElement) await document.exitFullscreen(); else if (el.requestFullscreen) await el.requestFullscreen();
    },
    async today() { return nowIso().slice(0, 10); },
  };

  await getCountries().catch(() => {});
  await ensureData();
  evaluateTickets();
  return api;
}
