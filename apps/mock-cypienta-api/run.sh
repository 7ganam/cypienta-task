#!/bin/sh
set -eu
cd "$(dirname "$0")"
case "${1:-}" in
    ""|--setup) ;;
    *) echo "Usage: $0 [--setup]" >&2; exit 2 ;;
esac

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

if [ ! -x .venv/bin/python ]; then
    if [ -z "${PYTHON_BIN:-}" ]; then
        for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
            if command -v "$candidate" >/dev/null 2>&1 &&
                "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' 2>/dev/null; then
                PYTHON_BIN="$candidate"
                break
            fi
        done
    fi
    if [ -z "${PYTHON_BIN:-}" ]; then
        echo "Python 3.10+ is required. Install it or set PYTHON_BIN to its executable." >&2
        exit 1
    fi
    "$PYTHON_BIN" -m venv .venv
fi
if ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "The existing .venv uses Python older than 3.10. Recreate it with a compatible Python." >&2
    exit 1
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
[ "${1:-}" != --setup ] || exit 0
exec .venv/bin/python manage.py runserver "127.0.0.1:${MOCK_API_PORT:-40759}"
