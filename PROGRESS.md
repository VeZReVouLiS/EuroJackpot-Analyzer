# Progress

## >>> ΠΟΥ ΕΧΟΥΜΕ ΜΕΙΝΕΙ (συνέχεια από το σπίτι) <<<
Repo: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer  (branch `main` = τελευταίο release v1.1.1,
branch `wip-browser-fallback` = ημιτελής δουλειά, δες παρακάτω).

**Πρόβλημα που διορθώνουμε:** σε άλλο PC (`C:\Users\dosma\Downloads\...`) η εφαρμογή σκάει με
`RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize ... pythonnet\runtime\Python.Runtime.dll`
(το native παράθυρο pywebview δεν ξεκινά). Δεν το αναπαράγαμε τοπικά (ούτε με «μπλοκαρισμένα» αρχεία Zone.Identifier).
Πιθανές αιτίες: παλιό .NET Framework (<4.7.2), antivirus/πολιτική, φάκελος Downloads/δίκτυο.

**Λύση που υλοποιούμε (v1.1.2):** fallback χωρίς pythonnet — αν αποτύχει το native παράθυρο, το UI σερβίρεται από
τοπικό server (127.0.0.1, token + έλεγχος Host) και ανοίγει στο Edge/Chrome σε app mode (`--app=`).
- [x] `app/server.py` (AppServer: token, /rpc, /ping heartbeat), `app/devserver.py`, `app/main.py` (native -> fallback, `--browser` για δοκιμή, log στο `data/startup.log`)
- [ ] `app/ui/app.js`: στο browser mode να διαβάζει `?t=TOKEN` από το URL, να στέλνει header `X-Token` στα `/rpc`, και να στέλνει heartbeat `GET /ping` κάθε ~2.5s (μόνο όταν δεν υπάρχει `window.pywebview`)
- [ ] tests για το server (403 χωρίς token / λάθος Host, ok με token) + δοκιμή `EuroJackpotApp.exe --browser`
- [ ] (προαιρετικό) αφαίρεση Zone.Identifier από `_internal` κατά την εκκίνηση
- [ ] README: SmartScreen («More info → Run anyway»), «Unblock» zip, απαιτήσεις (.NET Framework 4.7.2+), τι κάνει το fallback
- [ ] Bump `app/version.py` σε 1.1.2 + CHANGELOG, `powershell -ExecutionPolicy Bypass -File build\release.ps1 -SkipSeed`
- [ ] Διόρθωση release notes στο GitHub (έχουν mojibake): στο `build\release.ps1` το `Get-Content CHANGELOG.md` να γίνει `-Encoding UTF8` και το notes file να γράφεται UTF-8 χωρίς BOM· μετά `gh release edit v1.1.0 / v1.1.1 --notes-file ...`

**Άλλα που περιμένουν (ζήτησες):** splash screen πρώτης εκκίνησης με επιλογή γλώσσας και χώρας.
**Ανοιχτό:** το 403 του πρώτου PC (αν επιμένει στέλνεις τον «Έλεγχο σύνδεσης» από τις Ρυθμίσεις).
**Σημείωση:** η εφαρμογή (unsigned exe) δείχνει SmartScreen «Unknown publisher» — κανονικό· λύση μόνο με code-signing πιστοποιητικό (πληρωμένο).

Τρέξιμο για δοκιμή από τον πηγαίο κώδικα: `.venv\Scripts\python run.py` (ή `--browser`), tests: `.venv\Scripts\python -m pytest -q`.

Plan: `C:\Users\DimitrisSarlis\.claude\plans\moonlit-honking-dawn.md`

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
