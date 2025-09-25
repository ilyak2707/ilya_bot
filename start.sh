#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Устанавливаем/обновляем зависимости внутри venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt

mkdir -p logs
# Запускаем в фоне, логи — в logs/bot.out, PID — в bot.pid
nohup ./venv/bin/python bot.py >> logs/bot.out 2>&1 &
echo $! > bot.pid
echo "Started bot with PID $(cat bot.pid). Logs: $DIR/logs/bot.out"
