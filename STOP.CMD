@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe scripts\tracker.py --config config.toml stop
) else (
  python scripts\tracker.py --config config.toml stop
)
pause
