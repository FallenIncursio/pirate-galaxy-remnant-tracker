@echo off
cd /d "%~dp0"
python scripts\tracker.py --config config.toml run
pause
