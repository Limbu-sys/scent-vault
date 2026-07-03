@echo off
cd /d "%~dp0backend"
echo Starting Scent Vault...
start "Scent Vault Bot" python bot.py
python -m uvicorn server:app --host 127.0.0.1 --port 8782 --reload
