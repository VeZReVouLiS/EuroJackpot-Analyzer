# Progress

## >>> ΠΟΥ ΕΧΟΥΜΕ ΜΕΙΝΕΙ (συνέχεια από το σπίτι) <<<
App: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer — release **v1.2.1**.
Home Assistant: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer-HA — release **v0.3.2**, εγκατεστημένο στο ha.dosman.gr μέσω HACS.

**Έγιναν (HA):** sensors + service `eurojackpot_analyzer.generate_ticket`· **panel στο πλαϊνό μενού** (`panel_custom`, όπως το GR e-Pass) πλήρους οθόνης με μεγάλα στοιχεία και κουμπί γλώσσας EL/EN (άμεση αλλαγή, θυμάται την επιλογή)·
3 κάρτες Lovelace (last-draw, stats με χάρτη καθυστέρησης, ticket) που φορτώνονται αυτόματα· README με πραγματικά screenshots· CI πράσινο (tests σε Linux, hassfest, HACS).
**Κανόνες:** (1) αλλαγές στον κοινό πυρήνα → sync στο HA repo (hook + `tools/sync_ha.ps1`)· (2) μικρές διορθώσεις στο changelog = «Bug fixes / μικρές διορθώσεις»· (3) ελληνικά ΧΩΡΙΣ all-caps (το `text-transform: uppercase` κρατά τους τόνους) — πρώτο γράμμα κεφαλαίο μόνο· (4) κάθε αλλαγή UI → ξαναβγάζουμε τα screenshots (app: headless Edge με hash params, HA: Chrome στο ha.dosman.gr + zoom crop χωρίς πλαϊνό μενού).
**HA ενημέρωση:** HACS update → επανεκκίνηση HA → Ctrl+F5 στον browser.

**Εύρημα για Γερμανία:** η επίσημη (γερμανική) πηγή με `adg=ja` δίνει ανά κατηγορία `aufteilung[]` ΜΟΝΟ για τις 3 πρώτες κατηγορίες (5+2, 5+1, 5+0): πού κερδήθηκε, ανά χώρα (~14 χώρες φαίνονται στο ιστορικό, μαζί με την Ελλάδα `GRC`) και για Γερμανία ανά ομόσπονδο κρατίδιο. Για τις υπόλοιπες κατηγορίες υπάρχει μόνο σύνολο όλων των χωρών. Νικητές Γερμανίας ανά κατηγορία δεν υπάρχουν σε καμία πηγή. Ιδέα: ενότητα «Πού κερδήθηκε» στο app και στο HA (top-3 κατηγορίες, Ελλάδα και Γερμανία ξεχωριστά).

**Επόμενα βήματα:**
1. «Πού κερδήθηκε» (ανά χώρα/κρατίδιο, 3 πρώτες κατηγορίες) σε app + HA.
2. **Mac έκδοση** (ζήτηση χρήστη): ίδιος κώδικας, pywebview/WKWebView, build με PyInstaller σε Mac ή GitHub Actions `macos-latest`.
3. Splash screen πρώτης εκκίνησης με επιλογή γλώσσας και χώρας.
4. Allwyn login/παιχνίδι (app + HA), μη υπογεγραμμένο exe (SmartScreen).

Δοκιμή app: `.venv\Scripts\python run.py` (ή `--browser`), tests: `.venv\Scripts\python -m pytest -q` (57).
Release app: bump `app/version.py` + `CHANGELOG.md`, μετά `powershell -ExecutionPolicy Bypass -File build\release.ps1 -SkipSeed`.
Dev DB με demo δελτία: `data\eurojackpot.db` (git-ignored, δεν μπαίνει στο exe).
## Done
- [x] M1 skeleton, venv (.venv), deps
- [x] M2 db.py, sources/official.py (998 draws 2012->2026-10-13 in ~28s), updater.py
- [x] M3 sources/allwyn.py (api.opap.gr game 5149, matches), sources/importer.py (CSV/JSON)
- [x] M4 stats.py (euro pool eras 1-8/1-10/1-12)
- [x] M5 generators.py (7 algorithms + auto per column / per ticket)
- [x] M6 api.py, main.py (pywebview), devserver.py, UI (stats, ticket, draws, settings), EL/EN, dark/light
- [x] M7 PyInstaller portable build (`build\build_windows.ps1`, 26 MB), verified from clean folder
- 31 tests passing: `.venv\Scripts\python -m pytest -q`

## v1.1.0 (in progress)
- [x] prize details per draw, export/import round-trip, offline seed, empty state, diagnostics, app updater (code)
- [x] README with instructions + screenshots (docs/images)
- [x] GitHub: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer (public), releases v1.1.0 and v1.1.1 (zip + sha256); in-app update install tested end-to-end
- Release procedure: bump app/version.py + CHANGELOG.md, then `powershell -ExecutionPolicy Bypass -File build\release.ps1` (add -SkipSeed to reuse the bundled seed)
- [ ] 403 on the user's other PC: root cause unknown; hardened (browser headers, fail-fast, per-source error). Ask for the "Έλεγχος σύνδεσης" report if it persists.

## Future (user requests, to do after v1.1.0)
- [ ] Splash screen at first launch: user picks language and country; app then shows country-specific info (draws/prizes/Allwyn-OPAP data for Greece, other countries' operators)
- [ ] Mac build (same code; build with PyInstaller on a Mac, WKWebView is used by pywebview)
- [ ] Allwyn account login: view / top up / play (needs research; Akamai-protected site)
- [ ] Home Assistant integration (like the Attiki Odos one): sensors for last draw / overdue, optional play
- [ ] App icon, optional code signing
