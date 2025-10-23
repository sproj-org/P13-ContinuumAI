#!/usr/bin/env bash
set -euo pipefail

# Ensure sqlite directory exists
mkdir -p /workspace/data

# Start the API
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"