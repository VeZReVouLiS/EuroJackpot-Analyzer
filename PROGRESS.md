# Progress

## >>> ΠΟΥ ΕΧΟΥΜΕ ΜΕΙΝΕΙ (συνέχεια από το σπίτι) <<<
Repo: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer (public). Τελευταίο release: **v1.2.0**.

**Έγιναν:** v1.1.3 (αυτόματη αφαίρεση του «Mark of the Web» από τα αρχεία — αιτία του pythonnet σφάλματος στο PC `dosma`),
v1.2.0 (ιστορικό δελτίων «Τα δελτία μου» + αυτόματος έλεγχος κερδών + σύνολα + ειδοποίηση + export/import δελτίων),
README με οδηγίες και 7 εικόνες (docs/images, παράγονται με headless Edge και hash params: `#static=1&view=...&lang=...&theme=...&gen=N&draw=YYYY-MM-DD&demo_update=1`).

**Home Assistant:** repo https://github.com/VeZReVouLiS/EuroJackpot-Analyzer-HA (local `C:\Users\DimitrisSarlis\Projects\EuroJackpot-Analyzer-HA`), ονομασία «EuroJackpot Analyzer» όπως η εφαρμογή,
domain `eurojackpot_analyzer`. Sensors (τελευταία/επόμενη κλήρωση, τζάκποτ, most_overdue/most_frequent/least_frequent numbers, generated_ticket) + service `eurojackpot_analyzer.generate_ticket`.
CI πράσινο (13 tests σε HA 2026.10 / Linux, hassfest, HACS). Το HA core δεν τρέχει σε Windows· τα integration tests τρέχουν μόνο στο GitHub Actions.
**Εκκρεμεί:** (α) εγκατάσταση στο ha.dosman.gr μέσω HACS (απαιτεί επανεκκίνηση HA — ΜΕ ΕΓΚΡΙΣΗ του χρήστη), (β) εικόνες/screenshots του integration στο README (από πραγματικό dashboard στο HA), (γ) release/tag του HA repo (HACS προτιμά releases).
**Συγχρονισμός:** κάθε commit στο app repo που αγγίζει `app/rules.py|stats.py|generators.py|seed/draws.json` τρέχει αυτόματα (post-commit hook) το `tools/sync_ha.ps1`. ΣΗΜΕΙΩΣΗ: τα tests του HA repo δεν τρέχουν τοπικά (Windows)· το script κάνει commit/push και το CI ελέγχει.
**Changelog κανόνας:** μικρές διορθώσεις → μία γραμμή «Bug fixes / μικρές διορθώσεις». Εκκρεμεί στο app: «το μήνυμα κατάστασης ακολουθεί τη γλώσσα» (committed, δεν έχει κυκλοφορήσει).

**Επόμενα βήματα:**
1. Ολοκλήρωση HA (εκκρεμή παραπάνω).
2. **Mac έκδοση** (ζήτηση χρήστη, αμέσως μετά το HA): ίδιος κώδικας· pywebview χρησιμοποιεί WKWebView· χρειάζεται Mac για build (PyInstaller) ή GitHub Actions `macos-latest` runner.
3. Splash screen πρώτης εκκίνησης με επιλογή γλώσσας και χώρας.
4. Allwyn login/παιχνίδι, μη υπογεγραμμένο exe (SmartScreen).
Επιβεβαιώθηκε: το `dosma` PC δουλεύει με native παράθυρο (το παράθυρο unblock/SmartScreen βγαίνει μόνο την πρώτη φορά).
Δοκιμή: `.venv\Scripts\python run.py` (ή `--browser`), tests: `.venv\Scripts\python -m pytest -q` (57).
Release: bump `app/version.py` + `CHANGELOG.md`, μετά `powershell -ExecutionPolicy Bypass -File build\release.ps1 -SkipSeed`.
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
