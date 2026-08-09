#!/bin/sh

set -eu

request_log="${MCP_REQUEST_LOG:-/scratch/mcp-requests.jsonl}"

while IFS= read -r request; do
    printf '%s\n' "$request" >> "$request_log"
    request_id="$(printf '%s' "$request" | sed -n 's/.*"id":[[:space:]]*\([^,}]*\).*/\1/p')"
    case "$request" in
        *'"method":"initialize"'*)
            printf '{"jsonrpc":"2.0","id":%s,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"clinical-admission","version":"1.0.0"}}}\n' "$request_id"
            ;;
        *'"method":"tools/list"'*)
            printf '{"jsonrpc":"2.0","id":%s,"result":{"tools":[{"name":"admission_probe","description":"Offline admission probe","inputSchema":{"type":"object","properties":{}}}]}}\n' "$request_id"
            ;;
        *'"method":"tools/call"'*)
            printf '{"jsonrpc":"2.0","id":%s,"result":{"content":[{"type":"text","text":"ok"}]}}\n' "$request_id"
            ;;
    esac
done
