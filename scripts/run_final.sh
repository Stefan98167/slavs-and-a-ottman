#!/usr/bin/env bash
set -u -o pipefail

cd "$(dirname "$0")/.."
mkdir -p logs
log_file="logs/final-$(date +%Y%m%d).log"
runner=(uv run arena run --set final --agent unified --parallel 10 --waves 5 -v)

if [[ "$(uname -s)" == Linux ]] && command -v systemd-inhibit >/dev/null 2>&1; then
  command=(systemd-inhibit --what=sleep --why="Tacto Negotiation Arena Live Final" --mode=block -- "${runner[@]}")
elif [[ "$(uname -s)" == Darwin ]] && command -v caffeinate >/dev/null 2>&1; then
  command=(caffeinate -dims "${runner[@]}")
else
  command=("${runner[@]}")
fi

while true; do
  "${command[@]}" 2>&1 | tee -a "$log_file"
  status=${PIPESTATUS[0]}
  if [[ $status -eq 0 ]]; then
    exit 0
  fi
  printf '%s runner exited with status %s; restarting in 3 seconds\n' "$(date --iso-8601=seconds 2>/dev/null || date)" "$status" \
    | tee -a "$log_file"
  sleep 3
done
