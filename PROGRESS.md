# Progress

## >>> ΠΟΥ ΕΧΟΥΜΕ ΜΕΙΝΕΙ (συνέχεια από το σπίτι) <<<
Repo: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer (public). Τελευταίο release: **v1.1.2**.

**Έγινε στην 1.1.2:** fallback όταν το native παράθυρο (pywebview/pythonnet) δεν ξεκινά, π.χ. στο PC `dosma` με
`Failed to resolve Python.Runtime.Loader.Initialize`: η εφαρμογή ανοίγει σε Edge app mode μέσω τοπικού server
(token + έλεγχος Host), γράφει το σφάλμα στο `data\startup.log`, και κλείνει όταν κλείσει το παράθυρο.
Διορθώθηκαν επίσης τα release notes (UTF-8) και οι οδηγίες (SmartScreen, Unblock).

**Επόμενα βήματα:**
1. Δοκιμή της 1.1.2 στο PC `dosma` (και εκεί: Ρυθμίσεις → Έλεγχος σύνδεσης για το παλιό 403). Αν το fallback δεν ανοίξει, στείλε το `data\startup.log`.
2. Splash screen πρώτης εκκίνησης με επιλογή γλώσσας και χώρας (ζήτηση χρήστη).
3. Mac έκδοση, Allwyn login/παιχνίδι, Home Assistant (βλ. Future).

**Σημείωση:** το exe δεν είναι υπογεγραμμένο, οπότε εμφανίζεται SmartScreen «Unknown publisher»· λύση μόνο με code-signing πιστοποιητικό.
Δοκιμή: `.venv\Scripts\python run.py` (ή `--browser`), tests: `.venv\Scripts\python -m pytest -q` (46).
Release: bump `app/version.py` + `CHANGELOG.md`, μετά `powershell -ExecutionPolicy Bypass -File build\release.ps1 -SkipSeed`.
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
