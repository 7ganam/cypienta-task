#!/bin/sh
set -eu

repo_root=$(CDPATH= cd "$(dirname "$0")/.." && pwd -P)
server_pids=$(lsof -nP -tiTCP:3000 -tiTCP:41873 -tiTCP:40759 -sTCP:LISTEN 2>/dev/null || true)
stopped=0

for server_pid in $server_pids; do
    server_cwd=$(lsof -a -p "$server_pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
    server_command=$(ps -p "$server_pid" -o command= 2>/dev/null || true)

    # A port alone does not identify our app: Docker Desktop may own it.
    # Require both this checkout's app directory and a known dev-server command.
    case "$server_cwd" in
        "$repo_root/apps/usage-backend"|"$repo_root/apps/mock-cypienta-api")
            case "$server_command" in
                *" manage.py runserver "*) ;;
                *) continue ;;
            esac
            ;;
        "$repo_root/apps/web")
            case "$server_command" in
                *"/vite/bin/vite.js "*|*"node_modules/.bin/vite "*) ;;
                *) continue ;;
            esac
            ;;
        *) continue ;;
    esac

    if kill -TERM "$server_pid" 2>/dev/null; then
        printf 'Stopped dev server %s in %s\n' "$server_pid" "$server_cwd"
        stopped=$((stopped + 1))
    fi
done

if [ "$stopped" -eq 0 ]; then
    printf 'No project dev servers running on the default ports.\n'
fi
