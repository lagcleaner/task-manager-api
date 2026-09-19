#!/usr/bin/env bash
set -uo pipefail

f=$(jq -r '.tool_input.file_path // .tool_response.filePath')

case "$f" in
  *.py)
    OUT=$(uv run ruff check --fix "$f" 2>&1)
    uv run ruff format "$f" >/dev/null 2>&1
    if [ -n "$OUT" ]; then
      printf '{"systemMessage": %s}' "$(printf '%s' "$OUT" | jq -Rs .)"
    fi
    ;;
esac
