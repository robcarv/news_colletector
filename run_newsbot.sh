#!/bin/bash
# =============================================================================
# run_newsbot.sh v3.2 — Executa o NewsBot + GitHub sync (modo leve)
# =============================================================================
# Uso:
#   ./run_newsbot.sh              # Execução completa (cron)
#   ./run_newsbot.sh --dry-run    # Apenas simula
#   ./run_newsbot.sh --feed 2     # Apenas feed específico
# =============================================================================
# Otimizações Raspberry Pi:
#  - nice/ionice para prioridade baixa
#  - Timeout global de 10 minutos
#  - Git push SEMPRE após execução (mesmo com erro parcial)
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

echo "🚀 NewsBot v3.2 — $(date)" > "$LOG_FILE"
echo "===================================" >> "$LOG_FILE"

# 1. Verifica espaço em disco (se < 1GB livre, não executa)
DISK_FREE=$(df / | tail -1 | awk '{print $4}')
if [ "$DISK_FREE" -lt 1000000 ]; then  # < 1GB
    echo "⚠️  Pouco espaço em disco (${DISK_FREE}KB). Pulando execução." | tee -a "$LOG_FILE"
    exit 0
fi

# 2. Executa o coletor com nice (baixa prioridade) e timeout
echo "📡 Executando coleta (nice + ionice)..." | tee -a "$LOG_FILE"
nice -n 19 ionice -c 2 -n 7 \
    timeout 600 "$VENV_DIR/bin/python" main.py "$@" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

echo "📊 Código de saída: $EXIT_CODE" | tee -a "$LOG_FILE"

# (AzuraCast radio metadata removed — was in azura_metadata.py, file never existed)
# Radio data is now collected by portfolio_health_push.sh → health.json

# Export news.json for portfolio (com data real, nao string literal)
echo "📰 Exportando notícias para o portfolio..." | tee -a "$LOG_FILE"

# Gera news.json com a data/hora atual em Python (nao shell, para evitar bug de expansao)
$VENV_DIR/bin/python3 -c "
import json, os
from datetime import datetime, timezone

news_file = '$PROJECT_DIR/history.json'
portfolio_file = '/home/robert/Documents/portfolio-html/news.json'
now_iso = datetime.now(timezone.utc).astimezone().isoformat()

if os.path.exists(news_file):
    with open(news_file) as f:
        data = json.load(f)
    if isinstance(data, list):
        raw = data[-15:]
    elif isinstance(data, dict):
        raw = data.get('history', [])[-15:]
    else:
        raw = []
    items = []
    for item in raw:
        if isinstance(item, str):
            items.append({'title': item, 'source': 'RSS', 'link': '', 'summary': '', 'date': ''})
        elif isinstance(item, dict):
            items.append({
                'title': item.get('title', ''),
                'source': item.get('source', 'RSS'),
                'link': item.get('link', ''),
                'summary': item.get('summary', ''),
                'date': item.get('date', ''),
                'image': item.get('image', '')
            })
        else:
            items.append({'title': str(item), 'source': 'RSS', 'link': '', 'summary': '', 'date': ''})
    output = {'updated': now_iso, 'items': items}
    with open(portfolio_file, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f'  {len(items)} noticias exportadas para portfolio')
else:
    print('  history.json nao encontrado')
    with open(portfolio_file, 'w') as f:
        json.dump({'updated': now_iso, 'items': []}, f, indent=2, ensure_ascii=False)
" >> "$LOG_FILE" 2>&1

# 3. SEMPRE sincroniza com GitHub (mesmo se houve erro, para registrar o log)
echo "🔄 Sincronizando com GitHub..." | tee -a "$LOG_FILE"
bash "$PROJECT_DIR/sync_git.sh" >> "$LOG_FILE" 2>&1
GIT_EXIT=$?

# 4. Limpa logs antigos (mantém só últimos 20)
echo "🧹 Limpando logs antigos..." | tee -a "$LOG_FILE"
ls -t "$LOG_DIR"/newsbot_*.log 2>/dev/null | tail -n +21 | xargs rm -f --
ls -t "$LOG_DIR"/cron.log* 2>/dev/null | tail -n +6 | xargs rm -f --

echo "✅ NewsBot concluído em $(date) (exit: $EXIT_CODE, git: $GIT_EXIT)" | tee -a "$LOG_FILE"
echo "📝 Log: $LOG_FILE"

exit $EXIT_CODE
