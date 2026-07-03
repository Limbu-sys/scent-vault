#!/bin/sh
set -e
cd /app/backend
python bot.py &
exec uvicorn server:app --host 0.0.0.0 --port "${PORT:-80}"
