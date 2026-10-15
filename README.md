# EuroJackpot Analyzer

Portable Windows app (Python + WebView2): downloads the full EuroJackpot history (2012 → today), shows
statistics (frequency, overdue numbers, odd/even, sums, pairs) and generates 1–12 columns (2.50 € each).
Greek / English, dark / light, window or full screen (F11).

## Run
- **Portable**: copy the `dist\EuroJackpotApp` folder anywhere and run `EuroJackpotApp.exe`.
  Data and settings are stored in the `data` folder next to the exe (delete it to start fresh).
  Requires the Microsoft Edge WebView2 runtime (preinstalled on Windows 10/11).
- **From source**: `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\python run.py`
- **Browser dev mode**: `python -m app.devserver 8765` then open http://127.0.0.1:8765/index.html

## Build
`powershell -ExecutionPolicy Bypass -File build\build_windows.ps1` → `dist\EuroJackpotApp\`

## Tests
`.venv\Scripts\python -m pytest -q`

## Data sources
- Official EuroJackpot service (eurojackpot.com, full history since 2012-03-23)
- Allwyn/OPAP draws API (game 5149, since 2024-03-08) – used as fallback and cross-check
- Manual import of CSV / JSON (Settings → Import)

Euro numbers pool changed over time (1–8, 1–10 from 2014-10-10, 1–12 from 2022-03-25); statistics only
count draws in which a number actually existed.

Draws are random: statistics do not improve winning odds.
