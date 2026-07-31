#!/bin/bash
# =============================================================================
# News Collector - Sync GitHub v3
# =============================================================================
# Sincroniza o repositorio news_colletector com o GitHub.
# E tambem faz push do portfolio (robcarv.github.io) via sync_portfolio.sh
# =============================================================================
# Melhorias v3:
#  - sem 'set -e' (nao trava em erros parciais)
#  - portfolio sync separado em script proprio
#  - logging mais claro com timestamps
#  - health.json agora via script dedicado
# =============================================================================

PROJECT_DIR="/home/robert/Documents/vscode_projects/news_colletector"
cd "$PROJECT_DIR" || { echo "[ERRO] Diretorio nao encontrado: $PROJECT_DIR"; exit 1; }

DATE=$(date '+%Y-%m-%d %H:%M:%S')
echo "=== sync_git.sh v3 - $DATE ==="

# Configura git para commits automáticos
export GIT_SSH_COMMAND="ssh -i /home/robert/.ssh/id_ed25519 -o StrictHostKeyChecking=no"
export GIT_AUTHOR_NAME="robcarv"
export GIT_AUTHOR_EMAIL="noreply@robcarv.dev"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

# ─── 1. Push news_colletector ───────────────────────────────────────────────

echo "[1/3] Sincronizando news_colletector..."

# Fetch remoto primeiro para evitar divergencia
git fetch origin v4 -q 2>/dev/null || true

# Adiciona apenas arquivos relevantes (exceto .env, audio, logs)
git add -A
git reset -- .env .env.local azura_telegram_metadata.py data/audio/ logs/ 2>/dev/null || true

# Verifica se tem algo para commitar
if git diff --cached --quiet; then
    echo "  Nada para commitar — pulando"
fi

# Pega resumo das mudancas para o commit
SUMMARY=$(git diff --cached --name-only | head -10)
NEWS_COUNT=$(git diff --cached -- '*.json' | grep '"title"' | wc -l)
COMMIT_MSG="NewsBot: $(date '+%d/%m/%Y %H:%M') - ${NEWS_COUNT} noticias

Arquivos alterados:
$(echo "$SUMMARY" | sed 's/^/  - /')"

git commit -m "$COMMIT_MSG" -q 2>/dev/null || true

if git push origin v4 -q 2>&1; then
    echo "  OK news_colletector -> GitHub"
else
    echo "  Remote divergiu, tentando rebase..."
    git stash -q 2>/dev/null || true
    if git pull --rebase origin v4 -q 2>&1 && git push origin v4 -q 2>&1; then
        git stash pop -q 2>/dev/null || true
        echo "  OK news_colletector (com rebase)"
    else
        echo "  ERRO Falha definitiva no push do news_colletector"
    fi
fi

# ─── 2. Push portfolio (robcarv.github.io) via script dedicado ───────────────

echo "[2/3] Sincronizando portfolio (robcarv.github.io)..."
SCRIPT="$PROJECT_DIR/sync_portfolio.sh"
if [ -f "$SCRIPT" ]; then
    bash "$SCRIPT"
    echo "  Portfolio sync exit code: $?"
else
    echo "  Aviso: $SCRIPT nao encontrado, pulando"
fi

# ─── 3. Health check (cron portfolio-health-update gera localmente) ─────────
# Opcional — nao falha se health.json estiver ausente

echo "[3/3] Verificando health.json (gerado pelo cron portfolio-health-update)..."
HEALTH_FILE="/home/robert/Documents/portfolio-html/health.json"
if [ -f "$HEALTH_FILE" ]; then
    AGE=$(( $(date +%s) - $(stat -c %Y "$HEALTH_FILE") ))
    if [ "$AGE" -lt 7200 ]; then
        echo "  OK health.json presente ($((AGE/60))min de idade)"
    else
        echo "  Aviso: health.json com $((AGE/60))min — cron portfolio-health-update atrasado"
    fi
else
    echo "  Aviso: health.json nao encontrado (cron portfolio-health-update nao rodou?)"
fi

echo "=== sync_git.sh concluido ==="
