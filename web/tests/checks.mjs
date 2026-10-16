/* Parity checks: the JavaScript port against the Python results stored in golden.json (tools/make_golden.py),
 * plus validity checks of the generators. Used by Node (core.test.mjs) and by a browser page (run.html). */
import * as core from "../core.js";

const same = (a, b, path, out) => {
  if (typeof a === "number" && typeof b === "number") {
    const exact = /\.(p|p_any|p_jackpot)$/.test(path);                 // probabilities are not rounded: compare them precisely
    if (exact ? Math.abs(a - b) > 1e-9 * Math.abs(b) : Math.abs(a - b) > 0.0101) out.push(`${path}: ${a} != ${b}`);
    return;
  }
  if (a === null || b === null || typeof a !== "object" || typeof b !== "object") { if (a !== b) out.push(`${path}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`); return; }
  if (Array.isArray(a) !== Array.isArray(b)) { out.push(`${path}: array mismatch`); return; }
  const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
  if (ka.join() !== kb.join()) { out.push(`${path}: keys ${ka} != ${kb}`); return; }
  for (const k of ka) { same(a[k], b[k], `${path}.${k}`, out); if (out.length > 12) return; }
};

const statsView = (s) => {
  const keep = ["n", "count", "eligible", "pct", "gap", "max_gap", "avg_gap", "last_seen", "active"], pick = (x) => Object.fromEntries(keep.map((k) => [k, x[k]]));
  return { n_draws: s.n_draws, n_total: s.n_total, first_date: s.first_date, last_date: s.last_date, main: s.main.map(pick), euro: s.euro.map(pick),
    ranking: s.ranking, odd_even: s.odd_even, low_high: s.low_high, sum_hist: s.sum_hist, sum_avg: s.sum_avg, top_pairs: s.top_pairs };
};

export async function runChecks(loadJson) {
  const failures = [], gold = await loadJson("golden"), seedDoc = await loadJson("seed"), draws = seedDoc.draws;
  const check = (name, a, b) => { const out = []; same(a, b, name, out); failures.push(...out); };
  check("seed_count", draws.length, gold.seed_count);

  for (const [name, g] of Object.entries(gold.stats)) check(`stats[${name}]`, statsView(core.computeStats(draws, g.since, g.until)), g.result);

  gold.evaluation.forEach((g, i) => check(`evaluation[${i}]`, core.evaluateTicket(g.columns, g.draw), g.result));

  for (const [k, expected] of Object.entries(gold.import)) {
    let got;
    try { got = core.parseText(gold.samples[k], k.startsWith("json") ? "x.json" : "x.csv").map((r) => ({ date: r.date, main: r.main, euro: r.euro })); } catch (e) { got = "error"; }
    if (k === "invalid") { if (!(Array.isArray(got) && got.length === 0) && got !== "error") failures.push("import[invalid] should yield nothing"); }
    else check(`import[${k}]`, got, expected);
  }
  for (const g of gold.next_draws) check(`next_draws[${g.now}]`, core.nextDrawDates(new Date(g.now), 4), g.dates);
  check("csv", core.toCsv(gold.csv_input), gold.csv);

  // ticket analysis (probabilities, profile, history check)
  const full = core.computeStats(draws);
  for (const [country, g] of Object.entries(gold.analysis)) check(`analysis[${country}]`, core.analyze(g.columns, draws, full, g.price, g.country), g.result);

  // round trip of the app's own export
  const exp = core.toJson(draws.slice(-5), [], "x"), back = core.parseText(exp, "x.json");
  check("export round trip", back.map((d) => [d.date, d.main, d.euro]), draws.slice(-5).map((d) => [d.date, d.main, d.euro]));

  // generators: every algorithm produces valid, distinct columns (seeded random source -> reproducible)
  const st = core.computeStats(draws), rng = core.seededRng(12345);
  for (const algo of [...core.ALGOS, core.AUTO_COLUMN, core.AUTO_TICKET]) {
    for (let i = 0; i < 40; i++) {
      const t = core.generateTicket(st, 1 + (i % 12), algo, rng, null, 2.5), keys = new Set();
      if (t.columns.length !== 1 + (i % 12)) failures.push(`generate[${algo}]: wrong column count`);
      for (const c of t.columns) {
        if (!core.validColumn(c.main, c.euro) || c.main.some((n, j) => j && n <= c.main[j - 1])) failures.push(`generate[${algo}]: invalid column ${JSON.stringify(c)}`);
        if (c.euro.some((n) => n > core.currentEuroMax())) failures.push(`generate[${algo}]: euro out of range`);
        keys.add(c.main + "|" + c.euro);
      }
      if (keys.size !== t.columns.length) failures.push(`generate[${algo}]: duplicate columns`);
      if (Math.abs(t.total - t.columns.length * 2.5) > 1e-9) failures.push(`generate[${algo}]: total`);
    }
  }
  // locked columns stay where they are
  const keep = [{ main: [1, 2, 3, 4, 5], euro: [1, 2], algo: "random" }, null, null];
  const k = core.generateTicket(st, 3, "hot", rng, keep);
  check("keep", k.columns[0].main, [1, 2, 3, 4, 5]);
  return failures;
}
