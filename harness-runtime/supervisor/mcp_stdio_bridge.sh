#!/bin/sh

# Attempt-scoped standard MCP stdio shim for the admitted OpenCode image.
# The image contains only /bin/sh and the OpenCode binary, so this bridge uses
# the same line-delimited JSON-RPC transport proven by the container admission.

set -eu

bundle_path="${1:?attempt bundle path is required}"
audit_path="${2:?audit path is required}"

attempt_id="$(sed -n 's/.*"attempt_id"[[:space:]]*:[[:space:]]*"\([A-Za-z0-9._-]*\)".*/\1/p' "$bundle_path")"
spec_sha256="$(sed -n 's/.*"spec_sha256"[[:space:]]*:[[:space:]]*"\([0-9a-f]*\)".*/\1/p' "$bundle_path")"
if [ -z "$attempt_id" ] || [ "${#spec_sha256}" -ne 64 ]; then
    printf '%s\n' 'invalid MCP attempt bundle' >&2
    exit 2
fi
if ! grep -q '"allowed_tools"[[:space:]]*:[[:space:]]*\[[[:space:]]*"read_input"[[:space:]]*\]' "$bundle_path"; then
    printf '%s\n' 'unsupported MCP capability bundle' >&2
    exit 2
fi

json_escape_file() {
    awk '
        BEGIN { first = 1 }
        {
            gsub(/\\/, "\\\\")
            gsub(/\"/, "\\\"")
            if (!first) printf "\\n"
            printf "%s", $0
            first = 0
        }
    ' "$1"
}

write_audit() {
    tool="$1"
    tool_path="$2"
    result="$3"
    error_message="$4"
    printf '{"attempt_id":"%s","tool":"%s","arguments":{"path":"%s"},"result":"%s","error":%s}\n' \
        "$attempt_id" "$tool" "$tool_path" "$result" "$error_message" >> "$audit_path"
}

while IFS= read -r request; do
    request_id="$(printf '%s' "$request" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*\([^,}]*\).*/\1/p')"
    case "$request" in
        *'"method":"initialize"'*)
            printf '{"jsonrpc":"2.0","id":%s,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{"listChanged":false}},"serverInfo":{"name":"clinical-attempt-broker","version":"1.0.0"}}}\n' "$request_id"
            ;;
        *'"method":"notifications/initialized"'*)
            ;;
        *'"method":"ping"'*)
            printf '{"jsonrpc":"2.0","id":%s,"result":{}}\n' "$request_id"
            ;;
        *'"method":"tools/list"'*)
            printf '{"jsonrpc":"2.0","id":%s,"result":{"tools":[{"name":"read_input","description":"Read one UTF-8 artifact within this Attempt input root.","inputSchema":{"type":"object","additionalProperties":false,"required":["path"],"properties":{"path":{"type":"string","minLength":1}}}}]}}\n' "$request_id"
            ;;
        *'"method":"tools/call"'*)
            tool_name="$(printf '%s' "$request" | sed -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([A-Za-z0-9._-]*\)".*/\1/p')"
            tool_path="$(printf '%s' "$request" | sed -n 's/.*"path"[[:space:]]*:[[:space:]]*"\([A-Za-z0-9._\/-]*\)".*/\1/p')"
            case "$tool_name:$tool_path" in
                read_input:?*) ;;
                *)
                    write_audit "${tool_name:-unknown}" "${tool_path:-}" failed '"invalid tool arguments"'
                    printf '{"jsonrpc":"2.0","id":%s,"error":{"code":-32602,"message":"read_input requires a relative path"}}\n' "$request_id"
                    continue
                    ;;
            esac
            case "$tool_path" in
                /*|*..*|*[!A-Za-z0-9._/-]*)
                    write_audit "$tool_name" "$tool_path" failed '"path escapes input root"'
                    printf '{"jsonrpc":"2.0","id":%s,"error":{"code":-32602,"message":"path escapes input root"}}\n' "$request_id"
                    continue
                    ;;
            esac
            target="/inputs/$tool_path"
            current="/inputs"
            old_ifs="$IFS"
            IFS='/'
            for segment in $tool_path; do
                current="$current/$segment"
                if [ -L "$current" ]; then
                    write_audit "$tool_name" "$tool_path" failed '"symlink rejected"'
                    printf '{"jsonrpc":"2.0","id":%s,"error":{"code":-32602,"message":"symlink rejected"}}\n' "$request_id"
                    target=""
                    break
                fi
            done
            IFS="$old_ifs"
            [ -n "$target" ] || continue
            if [ ! -f "$target" ]; then
                write_audit "$tool_name" "$tool_path" failed '"input artifact unavailable"'
                printf '{"jsonrpc":"2.0","id":%s,"error":{"code":-32000,"message":"input artifact unavailable"}}\n' "$request_id"
                continue
            fi
            write_audit "$tool_name" "$tool_path" succeeded null
            printf '{"jsonrpc":"2.0","id":%s,"result":{"content":[{"type":"text","text":"' "$request_id"
            json_escape_file "$target"
            printf '"}]}}\n'
            ;;
        *)
            if [ -n "$request_id" ]; then
                printf '{"jsonrpc":"2.0","id":%s,"error":{"code":-32601,"message":"method not found"}}\n' "$request_id"
            fi
            ;;
    esac
done
