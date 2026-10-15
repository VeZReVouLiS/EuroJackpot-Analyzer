# Progress

## >>> ΠΟΥ ΕΧΟΥΜΕ ΜΕΙΝΕΙ (συνέχεια από το σπίτι) <<<
App: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer — release **v1.3.0** (δημοσιεύτηκε).
Home Assistant: https://github.com/VeZReVouLiS/EuroJackpot-Analyzer-HA — release **v0.4.0** δημοσιεύτηκε (CI πράσινο), **ΔΕΝ έχει εγκατασταθεί ακόμα στο ha.dosman.gr** (το HA τρέχει 0.3.2). Χρειάζεται έγκριση χρήστη για HACS update + επανεκκίνηση.

**Έγιναν (v1.3.0 app / v0.4.0 HA):** επιλογή χώρας (splash με σημαίες, ρυθμίσεις) και γλώσσας (ΕΛ/EN/DE, dropdown με σημαίες)· χώρες GR (Allwyn layout) και DE (επίσημο eurojackpot.com layout + «Πού κερδήθηκε» ανά χώρα/κρατίδιο, top-3 κατηγορίες)· οι άλλες χώρες δείχνουν «σύντομα» στη γλώσσα τους· τιμή στήλης ρυθμιζόμενη ανά χώρα (GR 2,50, DE 2,00 + προμήθεια)· πλαίσιο «Επόμενη κλήρωση» + αντίστροφη μέτρηση (και στο HA)· νέο εικονίδιο (αστέρι + €, σκούρο φόντο) στο app/exe/taskbar και στο HA brand· README.md (EL) + README.en.md (EN) στο app· seed v2 (με where-won).
Κατάλογος χωρών/γλωσσών: `app/ui/countries.json` (+ `app/ui/flags`, `logo.svg`) → συγχρονίζεται στο HA (`tools/sync_ha_core.py` → `www/assets`).

**Εκκρεμεί (HA docs):** τα README.md / README.en.md του HA repo είναι γραμμένα αλλά **δεν έχουν γίνει commit**· περιμένουν τα τελικά screenshots του πραγματικού HA: `03-dashboard-cards(.png/-en)`, `04-integration`, `05-device`, `06-service` (ελληνικά + `-en`). Τα panel screenshots (01/02/07/08, el+en) είναι έτοιμα (`/tmp`-free: `scratchpad/ha_shots.py`, harness `tools/preview` με `python -m http.server 8770`). Τα αγγλικά 04/05/06 είναι UI του ίδιου του HA → θέλουν προσωρινή αλλαγή γλώσσας προφίλ HA (ρώτα τον χρήστη). Μετά: commit docs στο HA repo (χωρίς νέο release).
**Κανόνες:** (1) αλλαγές στον κοινό πυρήνα/κατάλογο → sync στο HA repo (hook + `tools/sync_ha.ps1`)· (2) μικρές διορθώσεις στο changelog = «Bug fixes / μικρές διορθώσεις»· (3) ελληνικά ΧΩΡΙΣ all-caps· (4) κάθε αλλαγή UI → ξαναβγάζουμε ΟΛΑ τα screenshots (ελληνικά + αγγλικά) και ενημερώνουμε README.md + README.en.md· (5) επιβεβαίωση χρήστη πριν επανεκκίνηση/εγκατάσταση στο HA· (6) το demo dashboard στο HA μένει (δεν το ξαναφτιάχνουμε).
**HA ενημέρωση:** HACS update → επανεκκίνηση HA → Ctrl+F5 στον browser.

**Επόμενα βήματα:**
1. Ολοκλήρωση HA: έγκριση → HACS update 0.4.0 → επανεκκίνηση → πραγματικά screenshots → commit README.
2. **Mac έκδοση** (ζήτηση χρήστη): ίδιος κώδικας, pywebview/WKWebView, build με PyInstaller σε Mac ή GitHub Actions `macos-latest`.
3. Περισσότερες χώρες/γλώσσες (η υποδομή υπάρχει: `countries.json` + locale + layout στο `openDraw()`).
4. Allwyn login/παιχνίδι (app + HA), μη υπογεγραμμένο exe (SmartScreen).

Δοκιμή app: `.venv\Scripts\python run.py` (ή `--browser`), tests: `.venv\Scripts\python -m pytest -q` (60).
Screenshots app: scratchpad `shots.py` (headless Edge + in-process dev server, hash params `#country=DE&lang=en&view=history&draw=...&menu=lang-dd&splash=1&hover=GR,PL`).
Release app: bump `app/version.py` + `CHANGELOG.md`, μετά `powershell -ExecutionPolicy Bypass -File buildelease.ps1 -SkipSeed`.
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
