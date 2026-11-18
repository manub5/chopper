#!/usr/bin/env bash
set -euo pipefail

SOURCE="$(readlink -f -- "${BASH_SOURCE[0]}")"
PROJECT_DIR="$(cd "$(dirname "${SOURCE}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    echo "Uninstall requires standard Python 3; no application environment is needed." >&2
    exit 1
fi
exec python3 "${PROJECT_DIR}/scripts/install_integrations.py" --uninstall --project "${PROJECT_DIR}"
