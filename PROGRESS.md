# Progress

Plan: `C:\Users\DimitrisSarlis\.claude\plans\moonlit-honking-dawn.md`

## Done
- [x] M1 skeleton, venv (.venv), deps (pywebview, pyinstaller, pytest)
- [x] M2 db.py, sources/official.py (full history 2012->today, 998 draws in ~28s), updater.py
- [x] M3 sources/allwyn.py (api.opap.gr game 5149, verified matches), sources/importer.py (CSV/JSON)
- [x] M4 stats.py (euro pool eras 1-8/1-10/1-12 handled)
- [x] M5 generators.py (random, hot, cold, overdue, weighted, balanced, smart, auto per column/ticket)
- 31 tests passing: `.venv\Scripts\python -m pytest -q`

## Next
- [ ] M6 api.py + main.py (pywebview) + UI (ui/index.html, styles.css, app.js, chart.js vendored) + i18n el/en
- [ ] M7 PyInstaller portable build (build/build_windows.ps1) + README
- [ ] Later: Mac build, Allwyn login/play, Home Assistant
