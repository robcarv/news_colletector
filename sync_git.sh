#!/bin/bash
# =============================================================================
# News Collector - Sync GitHub
# =============================================================================
# Sincroniza logs, histórico e config com o GitHub.
# Chamado pelo cron após cada execução.
# =============================================================================

set -e

PROJECT_DIR="/home/robert/Documents/vscode_projects/news_colletector"
cd "$PROJECT_DIR" || { echo "❌ Diretório não encontrado: $PROJECT_DIR"; exit 1; }

DATE=$(date '+%Y-%m-%d %H:%M:%S')
LOG_DIR="$PROJECT_DIR/logs"

# Verificar se tem algo para commitar
git add -A
if git diff --cached --quiet; then
    echo "📭 Nada novo para commitar em $DATE"
    exit 0
fi

# Commit e push
git commit -m "Auto-update: NewsBot v3 - $DATE" -q
git push origin main -q

echo "✅ GitHub sync concluído em $DATE"
