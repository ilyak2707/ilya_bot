#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ -f bot.pid ]; then
  PID="$(cat bot.pid)"
  if ps -p "$PID" > /dev/null 2>&1; then
    kill "$PID" || true
    echo "Sent SIGTERM to PID $PID"
  fi
  rm -f bot.pid
  echo "Bot stopped."
else
  echo "No bot.pid — бот, возможно, не запущен."
fi
