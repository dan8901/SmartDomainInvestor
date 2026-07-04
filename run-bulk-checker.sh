#!/usr/bin/env bash
set -e

# --- Setup ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install python-whois colorama --quiet
else
    source .venv/bin/activate
fi

# --- Config ---
INPUT_FILE="${1:-names.csv}"
OUTPUT_FILE="${2:-results.csv}"
TLD="${3:-com}"
COLUMN="${4:-name}"

echo "Checking domains from: $INPUT_FILE"
echo "Output: $OUTPUT_FILE"
echo "TLD: .$TLD"
echo "Column: $COLUMN"
echo "---"

python bulk-checker.py -f "$INPUT_FILE" -o "$OUTPUT_FILE" -t "$TLD" --column "$COLUMN"
