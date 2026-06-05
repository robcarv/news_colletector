#!/bin/bash
# =============================================================================
# run_newsbot.sh — Executa o NewsBot + GitHub sync
# =============================================================================
# Uso:
#   ./run_newsbot.sh              # Execução completa (cron)
#   ./run_newsbot.sh --dry-run    # Apenas simula
#   ./run_newsbot.sh --feed 2     # Apenas feed específico
# =============================================================================

set -e

PROJECT_DIR="/home/robert/Documents/vscode_projects/news_colletector"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
DATE=$(date '+%Y-%m-%d_%H%M%S')

export PATH="$VENV_DIR/bin:$PATH"

cd "$PROJECT_DIR" || { echo "❌ Diretório não encontrado"; exit 1; }

# Garantir diretório de logs
mkdir -p "$LOG_DIR"

# Arquivo de log desta execução
LOG_FILE="$LOG_DIR/newsbot_$DATE.log"

echo "🚀 NewsBot v3 — $(date)" > "$LOG_FILE"
echo "================================" >> "$LOG_FILE"

# 1. Executa o coletor
echo "📡 Executando coleta..." | tee -a "$LOG_FILE"
cd "$PROJECT_DIR"

# Ativa venv e roda
"$VENV_DIR/bin/python" main.py "$@" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "📊 Código de saída: $EXIT_CODE" | tee -a "$LOG_FILE"

# 2. Sincroniza com GitHub (só se não for dry-run)
if [[ "$*" != *"--dry-run"* ]]; then
    echo "🔄 Sincronizando com GitHub..." | tee -a "$LOG_FILE"
    bash "$PROJECT_DIR/sync_git.sh" >> "$LOG_FILE" 2>&1
fi

echo "✅ NewsBot concluído em $(date)" | tee -a "$LOG_FILE"
echo "📝 Log: $LOG_FILE"

exit $EXIT_CODE
