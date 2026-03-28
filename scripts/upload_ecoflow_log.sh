#!/bin/bash
# EcoFlow ログを Azure Blob Storage にアップロードする
# cron 例: */15 * * * * /home/dahlia1209/src/ecoflow/scripts/upload_ecoflow_log.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_DIR"
source .venv/bin/activate

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

echo "=== $(date) ===" >> "$PROJECT_DIR/logs/upload_ecoflow.log"
python3 "$PROJECT_DIR/upload_ecoflow_log.py" 2>&1 | tee -a "$PROJECT_DIR/logs/upload_ecoflow.log"
echo "Done: $(date)" >> "$PROJECT_DIR/logs/upload_ecoflow.log"
