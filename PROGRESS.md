# Progress

## >>> ΠΟΥ ΕΧΟΥΜΕ ΜΕΙΝΕΙ (συνέχεια από το σπίτι) <<<
App: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer — release **v1.3.2** (Windows zip + **Mac zips arm64/intel** μέσω GitHub Actions).
Home Assistant: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer-HA — release **v0.4.2**, εγκατεστημένο στο ha.dosman.gr (HACS update + reload της ενσωμάτωσης, χωρίς επανεκκίνηση). Η γλώσσα προφίλ του χρήστη στο HA είναι English (επαναφέρθηκε μετά τα screenshots).

**Έγιναν:** χώρα/γλώσσα (GR/DE, el/en/de, splash, dropdowns με σημαίες), Γερμανία με «πού κερδήθηκε», αντίστροφη μέτρηση, νέο εικονίδιο (αστέρι+€, σκούρο φόντο), κάρτα τελευταίας κλήρωσης HA με εικονίδιο κληρωτηρίου, README.md + README.en.md σε app και HA με screenshots ελληνικά + αγγλικά, χωρίς scrollbars στο app, **Mac έκδοση**.
**Mac:** `paths.py` (δεδομένα στο ~/Library/Application Support/EuroJackpot Analyzer), `appupdate.py` (αυτο-ενημέρωση .app με ditto + sh script), `build/build_mac.sh`, `build/icon.icns`, `.github/workflows/mac.yml` (macos-latest arm64 + macos-15-intel: tests, PyInstaller .app, ad-hoc codesign, `--selftest`, upload στο release). **Δεν έχει δοκιμαστεί σε πραγματικό Mac** (το CI αποδεικνύει build + εκκίνηση χωρίς παράθυρο· το WKWebView παράθυρο, το Gatekeeper και η αυτο-ενημέρωση θέλουν δοκιμή από τον χρήστη).
**Κανόνες:** (1) αλλαγές στον κοινό πυρήνα/κατάλογο χωρών → sync στο HA repo (hook + `tools/sync_ha.ps1`· προσοχή: κάνει `git add -A` στο HA repo)· (2) μικρές διορθώσεις στο changelog = «Bug fixes / μικρές διορθώσεις»· (3) ελληνικά ΧΩΡΙΣ all-caps, κεφαλαίο μόνο το πρώτο γράμμα (π.χ. «Κληρώσεις · Στατιστικά · Δελτία»)· (4) κάθε αλλαγή UI → ξαναβγάζουμε ΟΛΑ τα screenshots (ελληνικά + αγγλικά) και ενημερώνουμε README.md + README.en.md· (5) επιβεβαίωση χρήστη πριν επανεκκίνηση HA / αλλαγή ρυθμίσεων λογαριασμού· (6) το demo dashboard στο HA μένει.
**HA ενημέρωση χωρίς επανεκκίνηση:** HACS download → `homeassistant.reload_config_entry` (entry 01M50J4M8BN61VMQ9QSKV805FB) → Ctrl+F5.

**Επόμενα βήματα:**
1. Δοκιμή της Mac έκδοσης σε πραγματικό Mac και διορθώσεις (παράθυρο, εικονίδιο, αυτο-ενημέρωση, ελληνικά/γερμανικά).
2. Περισσότερες χώρες/γλώσσες (υποδομή: `countries.json` + locale + layout στο `openDraw()`).
3. Allwyn login/παιχνίδι (app + HA), υπογραφή exe/app (SmartScreen, Gatekeeper).

Δοκιμή app: `.venv\Scripts\python run.py` (ή `--browser`), tests: `.venv\Scripts\python -m pytest -q` (64). Release app: bump `app/version.py` + `CHANGELOG.md`, `powershell -ExecutionPolicy Bypass -File buildelease.ps1 -SkipSeed` (το workflow Mac προσθέτει μόνο του τα zip).
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
