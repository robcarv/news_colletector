#!/bin/bash
# sync_health.sh — Copia health.json do Pi5 e faz push pro portfolio
# Chamado via cron a cada 10 min

PORTFOLIO_DIR="/home/robert/Documents/portfolio-html"
DATE=$(date '+%d/%m/%Y %H:%M')

# Copy from Pi5
ssh -o ConnectTimeout=5 pi5 'cat /home/robert/health_reports/health.json' > "$PORTFOLIO_DIR/health.json" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[$(date)] Pi5 offline, skipping health sync"
    exit 0
fi

cd "$PORTFOLIO_DIR" || exit 1

export GIT_SSH_COMMAND="ssh -i /home/robert/.ssh/id_ed25519 -o StrictHostKeyChecking=no"

# Fetch + reset to avoid conflicts
git fetch origin main -q 2>/dev/null || true
git reset --soft origin/main 2>/dev/null || true

git add health.json

if git diff --cached --quiet; then
    exit 0  # no changes
fi

git commit -m "health: all 3 Pis $DATE" -q 2>&1 || true
git push origin main -q 2>&1 && echo "[$(date)] Health pushed OK" || echo "[$(date)] Health push FAILED"
