/* EuroJackpot Analyzer - core logic in JavaScript (port of app/rules.py, stats.py, generators.py, evaluation.py,
 * sources/importer.py and exporter.py). Pure functions, no DOM: runs in the browser (PWA / Android app) and in Node
 * (tests). Parity with the Python version is checked by web/tests (golden file made by tools/make_golden.py). */

/* ---------------------------------------------------------------- rules */
export const FIRST_DRAW = "2012-03-23";
export const MAIN_MAX = 50, MAIN_COUNT = 5, EURO_COUNT = 2, COLUMN_PRICE = 2.5, MAX_COLUMNS = 12;
const EURO_RULES = [["2012-03-23", 8], ["2014-10-10", 10], ["2022-03-25", 12]];
export const TUESDAY_FROM = "2022-03-29";
export const euroMax = (d) => { let r = EURO_RULES[0][1]; for (const [s, m] of EURO_RULES) if (d >= s) r = m; return r; };
export const currentEuroMax = () => EURO_RULES[EURO_RULES.length - 1][1];

const pad = (n) => String(n).padStart(2, "0");
export const isoOf = (y, m, d) => `${y}-${pad(m)}-${pad(d)}`;
export const addDays = (iso, n) => { const t = new Date(iso + "T12:00:00Z"); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); };
export const weekday = (iso) => (new Date(iso + "T12:00:00Z").getUTCDay() + 6) % 7;   // Monday = 0 like Python
export const DRAW_TIME_LOCAL = [21, 15];

/** The next n draw dates (Friday, plus Tuesday since 2022-03-29). `now` = a local Date. */
export function nextDrawDates(now, n = 3) {
  let d = isoOf(now.getFullYear(), now.getMonth() + 1, now.getDate());
  if (now.getHours() * 60 + now.getMinutes() >= DRAW_TIME_LOCAL[0] * 60 + DRAW_TIME_LOCAL[1]) d = addDays(d, 1);
  const out = [];
  while (out.length < n) {
    const wd = weekday(d);
    if (wd === 4 || (wd === 1 && d >= TUESDAY_FROM)) out.push(d);
    d = addDays(d, 1);
  }
  return out;
}

/* ---------------------------------------------------------------- statistics */
const MAIN_RANGE = Array.from({ length: MAIN_MAX }, (_, i) => i + 1);
const EURO_RANGE = Array.from({ length: 12 }, (_, i) => i + 1);
// like Python's round(): exact ties go to the even neighbour (6.25 -> 6.2), everything else to the nearest
const round = (x, p) => { const f = 10 ** p, y = x * f, fl = Math.floor(y); return (y - fl === 0.5 ? (fl % 2 === 0 ? fl : fl + 1) : Math.round(y)) / f; };

function numberStats(all, win, key, rng, eligible, activeFn) {
  const counts = new Map(), eligWin = new Map();
  for (const d of win) {
    for (const n of rng) if (eligible(n, d.date)) eligWin.set(n, (eligWin.get(n) || 0) + 1);
    for (const n of d[key]) counts.set(n, (counts.get(n) || 0) + 1);
  }
  const lastIdx = new Map(), maxGap = new Map(), prevIdx = new Map(), lastSeen = new Map(), firstElig = new Map();
  all.forEach((d, i) => {
    for (const n of rng) if (!firstElig.has(n) && eligible(n, d.date)) { firstElig.set(n, i); prevIdx.set(n, i - 1); }
    for (const n of d[key]) {
      const gap = i - (prevIdx.has(n) ? prevIdx.get(n) : i - 1) - 1;
      maxGap.set(n, Math.max(maxGap.get(n) || 0, gap));
      prevIdx.set(n, i); lastIdx.set(n, i); lastSeen.set(n, d.date);
    }
  });
  const total = all.length, out = [];
  for (const n of rng) {
    const inPlay = firstElig.has(n);
    let cur = null;
    if (inPlay) {
      cur = lastIdx.has(n) ? total - 1 - lastIdx.get(n) : total - firstElig.get(n);
      maxGap.set(n, Math.max(maxGap.get(n) || 0, cur));
    }
    const e = eligWin.get(n) || 0, c = counts.get(n) || 0;
    out.push({ n, count: c, eligible: e, pct: e ? round(100 * c / e, 2) : 0.0, gap: cur,
      max_gap: maxGap.has(n) ? maxGap.get(n) : null, avg_gap: c ? round(e / c, 1) : null,
      last_seen: lastSeen.has(n) ? lastSeen.get(n) : null, active: activeFn(n) });
  }
  return out;
}

function top(items, field, reverse, k = 10, onlyActive = false) {
  const pool = items.filter((i) => i[field] !== null && (i.active !== false || !onlyActive));
  pool.sort((a, b) => (reverse ? (b[field] - a[field]) || (b.n - a.n) : (a[field] - b[field]) || (a.n - b.n)));
  return pool.slice(0, k).map((i) => i.n);
}
const ranked = (block, onlyActive) => ({ hot: top(block, "pct", true, 10, onlyActive), cold: top(block, "pct", false, 10, onlyActive),
  overdue: top(block, "gap", true, 10, onlyActive) });

/** draws: [{date, main, euro}] ; since/until: 'YYYY-MM-DD' window for counts (gaps use the whole history up to until). */
export function computeStats(draws, since = null, until = null) {
  draws = [...draws].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  const win = draws.filter((d) => (!since || d.date >= since) && (!until || d.date <= until));
  const hist = draws.filter((d) => !until || d.date <= until);
  const main = numberStats(hist, win, "main", MAIN_RANGE, () => true, (n) => n <= 12);
  const euro = numberStats(hist, win, "euro", EURO_RANGE, (n, d) => n <= euroMax(d), (n) => n <= currentEuroMax());
  const cnt = (f) => { const m = new Map(); for (const d of win) { const k = f(d); m.set(k, (m.get(k) || 0) + 1); } return m; };
  const oddDist = cnt((d) => d.main.reduce((a, n) => a + (n % 2), 0));
  const lowDist = cnt((d) => d.main.reduce((a, n) => a + (n <= 25 ? 1 : 0), 0));
  const sums = cnt((d) => Math.floor(d.main.reduce((a, n) => a + n, 0) / 10) * 10);
  const pairs = new Map();
  for (const d of win) {
    const m = [...d.main].sort((a, b) => a - b);
    for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) { const k = m[i] + "," + m[j]; pairs.set(k, (pairs.get(k) || 0) + 1); }
  }
  const sumValues = win.map((d) => d.main.reduce((a, n) => a + n, 0));
  const six = [0, 1, 2, 3, 4, 5];
  return {
    n_draws: win.length, n_total: hist.length, first_date: win.length ? win[0].date : null,
    last_date: win.length ? win[win.length - 1].date : null, last_draw: hist.length ? hist[hist.length - 1] : null,
    main, euro, ranking: { main: ranked(main, false), euro: ranked(euro, true) },
    odd_even: six.map((k) => ({ odd: k, even: 5 - k, count: oddDist.get(k) || 0 })),
    low_high: six.map((k) => ({ low: k, high: 5 - k, count: lowDist.get(k) || 0 })),
    sum_hist: Array.from({ length: 24 }, (_, i) => ({ from: 10 + i * 10, count: sums.get(10 + i * 10) || 0 })),
    sum_avg: sumValues.length ? round(sumValues.reduce((a, b) => a + b, 0) / sumValues.length, 1) : null,
    top_pairs: [...pairs.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, c]) => ({ pair: k.split(",").map(Number), count: c })),
  };
}

/* ---------------------------------------------------------------- generators */
export const ALGOS = ["random", "hot", "cold", "overdue", "weighted", "balanced", "smart"];
export const AUTO_COLUMN = "auto_column", AUTO_TICKET = "auto_ticket";

/** Default random source: crypto.getRandomValues (browser and Node 19+). A seeded one can be passed in tests. */
export function systemRng() {
  const buf = new Uint32Array(2);
  const random = () => { crypto.getRandomValues(buf); return (buf[0] * 2 ** 21 + (buf[1] >>> 11)) / 2 ** 53; };
  return makeRng(random);
}
export function makeRng(random) {
  return {
    random,
    uniform: (a, b) => a + (b - a) * random(),
    choice: (arr) => arr[Math.floor(random() * arr.length)],
    sample: (arr, k) => { const a = [...arr]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a.slice(0, k); },
  };
}
export function seededRng(seed) {                       // mulberry32, for tests
  let s = seed >>> 0;
  return makeRng(() => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; });
}

function weights(block, field, power, invert = false, onlyActive = true) {
  const vals = new Map();
  for (const b of block) if (b.gap !== null || !onlyActive) vals.set(b.n, b[field] || 0);
  if (!vals.size) return new Map();
  const hi = Math.max(...vals.values()) || 1, out = new Map();
  for (const [n, v] of vals) { let x = hi ? v / hi : 0; if (invert) x = 1 - x; out.set(n, (x + 0.05) ** power); }
  return out;
}
function pick(rng, w, k) {
  const pool = new Map(w), chosen = [];
  for (let i = 0; i < k; i++) {
    let total = 0; for (const v of pool.values()) total += v;
    const r = rng.uniform(0, total); let acc = 0, p = pool.keys().next().value;
    for (const [n, v] of pool) { acc += v; if (r <= acc) { p = n; break; } }
    chosen.push(p); pool.delete(p);
  }
  return chosen.sort((a, b) => a - b);
}
const uniform = (nums, rng, k) => rng.sample(nums, k).sort((a, b) => a - b);
const without = (m, taken) => new Map([...m].filter(([n]) => !taken.includes(n)));

function euroNumbers(stats, rng, algo) {
  const block = stats.euro.filter((e) => e.active), nums = block.map((e) => e.n);
  let w;
  if (algo === "random" || algo === "smart") return uniform(nums, rng, EURO_COUNT);
  if (algo === "hot" || algo === "weighted") w = weights(block, "pct", algo === "hot" ? 3 : 1);
  else if (algo === "cold") w = weights(block, "pct", 3, true);
  else if (algo === "overdue") w = weights(block, "gap", 3);
  else { const a = pick(rng, weights(block, "pct", 2), 1); return [...a, ...pick(rng, without(weights(block, "gap", 2), a), 1)].sort((x, y) => x - y); }
  return pick(rng, w, EURO_COUNT);
}

function mainNumbers(stats, rng, algo) {
  const block = stats.main, nums = MAIN_RANGE;
  if (algo === "random") return uniform(nums, rng, MAIN_COUNT);
  if (algo === "hot") return pick(rng, weights(block, "pct", 4), 5);
  if (algo === "weighted") return pick(rng, weights(block, "pct", 1), 5);
  if (algo === "cold") return pick(rng, weights(block, "pct", 4, true), 5);
  if (algo === "overdue") return pick(rng, weights(block, "gap", 3), 5);
  if (algo === "balanced") {
    const hot = pick(rng, weights(block, "pct", 3), 2);
    const over = pick(rng, without(weights(block, "gap", 3), hot), 1);
    const taken = [...hot, ...over], rest = nums.filter((n) => !taken.includes(n));
    return [...hot, ...over, ...rng.sample(rest, 2)].sort((a, b) => a - b);
  }
  for (let i = 0; i < 5000; i++) {                       // smart: typical shape
    const c = rng.sample(nums, 5).sort((a, b) => a - b);
    const odd = c.reduce((a, n) => a + (n % 2), 0), low = c.reduce((a, n) => a + (n <= 25 ? 1 : 0), 0);
    let consec = 0; for (let j = 1; j < c.length; j++) if (c[j] === c[j - 1] + 1) consec++;
    const sum = c.reduce((a, n) => a + n, 0);
    if (odd >= 2 && odd <= 3 && low >= 2 && low <= 3 && sum >= 90 && sum <= 160 && consec <= 1) return c;
  }
  return uniform(nums, rng, 5);
}

export function generateColumn(stats, algo, rng = systemRng()) {
  if (!ALGOS.includes(algo)) throw new Error(`unknown algorithm: ${algo}`);
  return { main: mainNumbers(stats, rng, algo), euro: euroNumbers(stats, rng, algo), algo };
}

export function generateTicket(stats, columns, algo = AUTO_TICKET, rng = systemRng(), keep = null, price = null) {
  if (!(columns >= 1 && columns <= MAX_COLUMNS)) throw new Error(`columns must be 1..${MAX_COLUMNS}`);
  const ticketAlgo = algo === AUTO_TICKET ? rng.choice(ALGOS) : algo;
  const slots = (keep || []).slice(0, columns).map((c) => c || null);
  while (slots.length < columns) slots.push(null);
  const keyOf = (c) => c.main.join(",") + "|" + c.euro.join(",");
  const seen = new Set(slots.filter(Boolean).map(keyOf));
  slots.forEach((slot, i) => {
    if (slot) return;
    let col;
    for (let t = 0; t < 50; t++) {
      const a = algo === AUTO_COLUMN ? rng.choice(ALGOS) : ticketAlgo;
      col = generateColumn(stats, a, rng);
      if (!seen.has(keyOf(col))) { seen.add(keyOf(col)); break; }
    }
    slots[i] = col;
  });
  const p = price === null || price === undefined ? COLUMN_PRICE : Number(price);
  return { columns: slots, algo, resolved_algo: algo !== AUTO_COLUMN ? ticketAlgo : null, price_per_column: p, total: round(columns * p, 2) };
}

/* ---------------------------------------------------------------- evaluation */
const PRIZE_TIERS = new Set(["5+2", "5+1", "5+0", "4+2", "4+1", "4+0", "3+2", "3+1", "3+0", "2+2", "2+1", "1+2"]);
const inter = (a, b) => [...new Set(a.filter((x) => b.includes(x)))].sort((x, y) => x - y);

export function evaluateColumn(col, draw) {
  const mainHit = inter(col.main, draw.main), euroHit = inter(col.euro, draw.euro), tier = `${mainHit.length}+${euroHit.length}`;
  let prize = 0, known = true, wins = false;
  const details = draw.details;
  if (details) {
    const c = ((details.classes) || []).find((x) => x.tier === tier);
    if (c && (c.prize || 0) > 0) { prize = Number(c.prize); wins = true; }
  } else { known = false; wins = PRIZE_TIERS.has(tier); }
  return { main_hit: mainHit, euro_hit: euroHit, tier, prize: round(prize, 2), wins, known };
}
export function evaluateTicket(columns, draw) {
  const cols = columns.map((c) => evaluateColumn(c, draw));
  return { draw_date: draw.date, draw: { main: draw.main, euro: draw.euro }, columns: cols,
    total_prize: round(cols.reduce((a, c) => a + c.prize, 0), 2), winning_columns: cols.filter((c) => c.wins).length,
    complete: cols.every((c) => c.known) };
}

/* ---------------------------------------------------------------- import */
function validDate(y, m, d) { const t = new Date(Date.UTC(y, m - 1, d)); return t.getUTCFullYear() === y && t.getUTCMonth() === m - 1 && t.getUTCDate() === d; }
export function parseDate(value) {
  if (value === null || value === undefined) return null;
  let s = String(value).trim();
  if (!s) return null;
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) s = s.slice(0, 10);
  const m = s.match(/\d{1,4}[./-]\d{1,2}[./-]\d{1,4}|\d{8}/);
  if (m) s = m[0];
  let y, mo, d;
  if (/^\d{8}$/.test(s)) { y = +s.slice(0, 4); mo = +s.slice(4, 6); d = +s.slice(6, 8); }
  else {
    const p = s.split(/[./-]/);
    if (p.length !== 3 || p.some((x) => !/^\d+$/.test(x))) return null;
    if (p[0].length === 4) { y = +p[0]; mo = +p[1]; d = +p[2]; }
    else if (p[2].length === 4) { d = +p[0]; mo = +p[1]; y = +p[2]; }
    else if (p[2].length === 2) { d = +p[0]; mo = +p[1]; const yy = +p[2]; y = yy >= 69 ? 1900 + yy : 2000 + yy; }
    else return null;
  }
  return validDate(y, mo, d) ? isoOf(y, mo, d) : null;
}
const ints = (v) => {
  if (v === null || v === undefined) return [];
  if (Array.isArray(v)) return v.flatMap(ints);
  return (String(v).match(/\d+/g) || []).map(Number);
};
export function validColumn(main, euro) {
  return main.length === 5 && new Set(main).size === 5 && main.every((n) => n >= 1 && n <= 50)
    && euro.length === 2 && new Set(euro).size === 2 && euro.every((n) => n >= 1 && n <= 12);
}
const sortNum = (a) => [...a].sort((x, y) => x - y);
const looksDate = (c) => parseDate(c) && /[./-]|\d{8}/.test(c);

function record(rec) {
  let d = null, main = [], euro = [], details = null, source = "import";
  if (rec && !Array.isArray(rec) && typeof rec === "object") {
    const flat = [];
    details = rec.details && typeof rec.details === "object" ? rec.details : null;
    if (typeof rec.source === "string" && rec.source) source = rec.source;
    for (const [k, v] of Object.entries(rec)) {
      const kl = String(k).toLowerCase();
      if (kl === "details" || kl === "source") continue;
      if (d === null && (kl.includes("date") || kl.includes("ημερ") || kl === "draw" || kl === "day")) { d = parseDate(v); if (d) continue; }
      if (/euro|bonus|star|extra|\be\d|^e\d/.test(kl)) euro.push(...ints(v));
      else if (/main|number|num|winning|^n\d|^b\d|ball/.test(kl)) main.push(...ints(v));
      else if (typeof v !== "string" || /^[\d\s,;|-]+$/.test(v)) flat.push(...ints(v));
    }
    if (!main.length && !euro.length) { if (flat.length === 7) { main = flat.slice(0, 5); euro = flat.slice(5); } }
    else if (main.length && !euro.length && main.length === 7) { euro = main.slice(5); main = main.slice(0, 5); }
    if (d === null) for (const v of Object.values(rec)) { d = parseDate(v); if (d) break; }
  } else if (Array.isArray(rec)) {
    const cells = rec.map((c) => String(c).trim());
    const idx = cells.findIndex((c) => looksDate(c));
    if (idx < 0) return null;
    d = parseDate(cells[idx]);
    const nums = [];
    cells.forEach((c, i) => {
      if (i === idx) return;
      if (/^\d{1,2}$/.test(c)) nums.push(+c);
      else if (/^[\d\s,;|-]+$/.test(c) && /\d\D+\d/.test(c)) nums.push(...ints(c));
    });
    if (nums.length >= 7) { main = nums.slice(0, 5); euro = nums.slice(5, 7); }
  }
  if (!d) return null;
  if (main.length && euro.length && validColumn(sortNum(main), sortNum(euro))) return { date: d, main: sortNum(main), euro: sortNum(euro), source, details };
  return null;
}

function parseCsv(text, delim) {
  const rows = []; let row = [], cur = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += c; }
    else if (c === '"') q = true;
    else if (c === delim) { row.push(cur); cur = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cur); rows.push(row); row = []; cur = ""; }
    else cur += c;
  }
  if (cur !== "" || row.length) { row.push(cur); rows.push(row); }
  return rows.filter((r) => r.some((c) => c !== ""));
}
function sniff(text) {
  const head = text.slice(0, 4096).split(/\r?\n/).slice(0, 8);
  let best = ",", bestScore = -1;
  for (const d of [",", ";", "\t", "|"]) {
    const counts = head.map((l) => l.split(d).length - 1);
    const score = counts.length && counts.every((c) => c === counts[0]) ? counts[0] : Math.min(...counts) / 2;
    if (score > bestScore) { bestScore = score; best = d; }
  }
  return best;
}

/** Draws from a CSV / JSON text (JSON may be an export of this app). Returns [{date, main, euro, source, details}] sorted. */
export function parseText(text, filename = "") {
  text = text.replace(/^﻿/, "").trim();
  let records = [];
  if (text[0] === "[" || text[0] === "{" || filename.toLowerCase().endsWith(".json")) {
    let data = JSON.parse(text);
    if (data && !Array.isArray(data) && typeof data === "object") {
      const key = ["draws", "results", "data", "items", "rows"].find((k) => Array.isArray(data[k]));
      data = key ? data[key] : (Object.values(data).every((v) => v && typeof v === "object" && !Array.isArray(v)) ? Object.values(data) : [data]);
    }
    records = data;
  } else {
    const rows = parseCsv(text, sniff(text));
    if (rows.length && !rows[0].some((c) => looksDate(c))) {
      const header = rows[0];
      records = rows.slice(1).map((r) => Object.fromEntries(header.map((h, i) => [h, r[i]]).filter(([, v]) => v !== undefined)));
    } else records = rows;
  }
  const out = new Map();
  for (const rec of records) {
    if (Array.isArray(rec) && rec.length && typeof rec[0] === "object" && rec[0] !== null) continue;
    const r = record(rec);
    if (r) out.set(r.date, r);
  }
  return [...out.values()].sort((a, b) => (a.date < b.date ? -1 : 1));
}

export function parseTickets(text) {
  text = text.replace(/^﻿/, "").trim();
  if (text[0] !== "{") return [];
  let doc; try { doc = JSON.parse(text); } catch { return []; }
  const out = [];
  for (const t of (doc && Array.isArray(doc.tickets) ? doc.tickets : [])) {
    try {
      const cols = t.columns.map((c) => ({ main: sortNum(c.main.map(Number)), euro: sortNum(c.euro.map(Number)), algo: c.algo || "random" }));
      if (cols.length && cols.every((c) => validColumn(c.main, c.euro)))
        out.push({ created_at: String(t.created_at), target_date: String(t.target_date), algo: String(t.algo || ""), columns: cols,
          price: Number(t.price || 0), played: !!t.played, result: t.result || null });
    } catch { /* skip an invalid ticket */ }
  }
  return out;
}

/* ---------------------------------------------------------------- export */
export const FORMAT = "eurojackpot-analyzer";
export function toJson(draws, tickets, appVersion) {
  const doc = { format: FORMAT, version: 1, app_version: appVersion, exported_at: new Date().toISOString().slice(0, 19), count: draws.length, draws };
  if (tickets && tickets.length) doc.tickets = tickets.map((t) => ({ created_at: t.created_at, target_date: t.target_date, algo: t.algo, columns: t.columns, price: t.price, played: t.played, result: t.result }));
  return JSON.stringify(doc, null, 1);
}
export function toCsv(draws) {
  return ["date;n1;n2;n3;n4;n5;e1;e2", ...draws.map((d) => [d.date, ...d.main, ...d.euro].join(";"))].join("\n") + "\n";
}
export function defaultFilename(fmt) { const n = new Date(); return `eurojackpot-draws-${isoOf(n.getFullYear(), n.getMonth() + 1, n.getDate())}.${fmt}`; }
