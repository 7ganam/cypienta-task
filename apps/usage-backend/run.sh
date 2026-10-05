#!/bin/sh

set -eu

cd "$(dirname "$0")"

case "${1:-}" in
    "") requirements=requirements.txt ;;
    --setup) requirements=requirements-dev.txt ;;
    *) echo "Usage: $0 [--setup]" >&2; exit 2 ;;
esac

if [ ! -x .venv/bin/python ]; then
    "${PYTHON_BIN:-python3}" -m venv .venv
fi

if ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'; then
    echo "Python 3.12+ is required. Recreate .venv with a compatible Python." >&2
    exit 1
fi

if command -v uv >/dev/null 2>&1; then
    uv pip install --python .venv/bin/python --require-hashes -r "$requirements"
else
    .venv/bin/python -m ensurepip --upgrade >/dev/null
    .venv/bin/python -m pip install --require-hashes -r "$requirements"
fi

[ "${1:-}" != --setup ] || exit 0

exec .venv/bin/python manage.py runserver "${BACKEND_BIND:-127.0.0.1:41873}"
