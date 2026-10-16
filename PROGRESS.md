# Progress

## >>> ΠΟΥ ΕΧΟΥΜΕ ΜΕΙΝΕΙ (συνέχεια από το σπίτι) <<<
App: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer — release **v1.6.0**: Windows zip, Mac zips (arm64/intel), **Android APK**, και **web app (PWA) στο GitHub Pages**: https://vezrevoulis.github.io/EuroJackpot-Analyzer/ (iPhone: Safari → Προσθήκη στην οθόνη Αφετηρίας).
Home Assistant: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer-HA — release **v0.5.0**, εγκατεστημένο στο ha.dosman.gr.

**v1.6.0 / HA 0.5.0:** δικό μου δελτίο (picker), ανάλυση (`app/analysis.py` + `web/core.js`: ακριβείς πιθανότητες, αναμενόμενο κέρδος, προφίλ, έλεγχος ιστορικού), συγχρονισμός δελτίων μέσω ιδιωτικού gist (`app/ticket_sync.py` + `webapi.js`, merge last-updated-wins + tombstones), Android in-app update (`web/android-native/ApkInstallerPlugin.java`, `android.yml`), HA: ειδοποιήσεις/events (`eurojackpot_analyzer_new_draw|jackpot_alert|ticket_result`), κάρτα «Τα δελτία μου», υπηρεσίες `analyze_ticket`/`sync_tickets`, About στο panel. Τα HA tests τρέχουν και τοπικά (βλ. memory ha-local-tests).

**Κινητά (v1.4.0):** `web/core.js` (πύλη Python→JS: rules, stats, generators, evaluation, importer, exporter), `web/webapi.js` (το api.py στον browser, IndexedDB μέσω `web/store.js`), `web/boot.js` (+ service worker), `tools/build_site.py` → `site/` (UI + web/ + κληρώσεις + manifest + sw.js), `tools/update_web_data.py` (νέες κληρώσεις), `tools/make_golden.py` + `web/tests/` (ισοδυναμία Python↔JS: `node --test web/tests/core.test.mjs` στο CI, ή `web/tests/run.html` σε browser). Workflows: `web.yml` (tests + deploy Pages, κάθε πρωί 06:15 UTC και Τρί/Παρ 19:30–22:30 UTC), `android.yml` (Capacitor 7 → APK, υπογραφή από secrets, upload στο release), `mac.yml`, `android-keystore.yml` (έτρεξε μία φορά). Το keystore του Android υπάρχει ΜΟΝΟ ως secrets `ANDROID_KEYSTORE_B64` / `ANDROID_KEYSTORE_PASSWORD` + αντίγραφο στο `C:\Users\DimitrisSarlis\Projects\_secrets_eurojackpot` (εκτός git· κράτα αντίγραφο, αλλιώς οι ενημερώσεις APK θέλουν απεγκατάσταση).
UI κινητού: κάτω μενού ≤760px, `--safe-top/--safe-bottom`, hash `#safe=50` και `#static=1` για screenshots, `#demo=1` δημιουργεί demo δελτία. Screenshots κινητού: `scratchpad/cdp_shots.py` (Edge DevTools, 390x844 / 412x915 @2x) → `docs/images/phone-iphone(-en).png`, `phone-android(-en).png`.
**Δεν έχει δοκιμαστεί σε πραγματικό iPhone/Android/Mac.** Γνωστό: στο CI το Allwyn μπορεί να μπλοκάρει, οπότε οι νέες κληρώσεις στο web έχουν επίσημα στοιχεία αλλά όχι ελληνικούς νικητές.
**Κανόνες:** (1) αλλαγές στον κοινό πυρήνα/κατάλογο χωρών → sync στο HA repo (hook + `tools/sync_ha.ps1`)· (2) μικρές διορθώσεις στο changelog = «Bug fixes / μικρές διορθώσεις»· (3) ελληνικά ΧΩΡΙΣ all-caps· (4) κάθε αλλαγή UI → ξαναβγάζουμε ΟΛΑ τα screenshots (ελληνικά + αγγλικά) και ενημερώνουμε README.md + README.en.md· (5) επιβεβαίωση χρήστη πριν επανεκκίνηση HA / αλλαγή ρυθμίσεων λογαριασμού· (6) το demo dashboard στο HA μένει.

**Επόμενα βήματα:**
1. Δοκιμή σε πραγματικό iPhone / Android / Mac και διορθώσεις.
2. Περισσότερες χώρες/γλώσσες (υποδομή: `countries.json` + locale + layout στο `openDraw()`).
3. Allwyn login/παιχνίδι, υπογραφή exe/app (SmartScreen, Gatekeeper), προαιρετικά App Store / Google Play.

Δοκιμή app: `.venv\Scripts\python run.py`, tests: `.venv\Scripts\python -m pytest -q` (67). Release: bump `app/version.py` + `CHANGELOG.md`, `powershell -ExecutionPolicy Bypass -File build\release.ps1 -SkipSeed` (τα workflows Mac/Android προσθέτουν μόνα τους τα αρχεία).
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
