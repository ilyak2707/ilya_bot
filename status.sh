#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ -f bot.pid ]; then
  PID="$(cat bot.pid)"
  if ps -p "$PID" > /dev/null 2>&1; then
    echo "Бот работает. PID: $PID"
    exit 0
  fi
fi
echo "Бот не запущен."
