#!/bin/bash
set -e

MODEL_NAME="gpt-oss-120b"
PORT="8000"

pids="$(pgrep -f "vllm.entrypoints.openai.api_server" || true)"
if [ -z "$pids" ]; then
  echo "No vLLM api_server process found."
  exit 0
fi

matched_pids=()
for pid in $pids; do
  if [ ! -r "/proc/$pid/cmdline" ]; then
    continue
  fi
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
  if [[ "$cmdline" == *"--served-model-name"*"$MODEL_NAME"* && "$cmdline" == *"--port"*"$PORT"* ]]; then
    matched_pids+=("$pid")
  fi
done

if [ ${#matched_pids[@]} -eq 0 ]; then
  echo "No matching server process found for model=$MODEL_NAME port=$PORT."
  exit 0
fi

echo "Stopping server (model=$MODEL_NAME port=$PORT): ${matched_pids[*]}"
for pid in "${matched_pids[@]}"; do
  kill -TERM "$pid" 2>/dev/null || true
done

sleep 2

still_running=()
for pid in "${matched_pids[@]}"; do
  if kill -0 "$pid" 2>/dev/null; then
    still_running+=("$pid")
  fi
done

if [ ${#still_running[@]} -gt 0 ]; then
  echo "Force killing: ${still_running[*]}"
  for pid in "${still_running[@]}"; do
    kill -KILL "$pid" 2>/dev/null || true
  done
fi

echo "Done."
