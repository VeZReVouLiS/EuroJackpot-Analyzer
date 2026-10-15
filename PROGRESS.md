# Progress

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

## Future
- [ ] Mac build (same code; build with PyInstaller on a Mac, WKWebView is used by pywebview)
- [ ] Allwyn account login: view / top up / play (needs research; Akamai-protected site)
- [ ] Home Assistant integration (like the Attiki Odos one): sensors for last draw / overdue, optional play
- [ ] App icon, optional code signing
