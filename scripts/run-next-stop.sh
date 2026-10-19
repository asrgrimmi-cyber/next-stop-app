#!/usr/bin/env sh
# Keeps Next Stop running: restarts 5 s after it stops. Exit code 3 = port already in use.
cd "$(dirname "$0")/.." || exit 1
while true; do
  python3 -u server.py --port "${PORT:-8080}" >> server.log 2>&1
  code=$?; [ "$code" = 3 ] && exit 3
  echo "$(date) Next Stop stopped (code $code), restarting in 5 s" >> server.log
  sleep 5
done
