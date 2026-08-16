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
echo "📰 Exportando notícias para o portfolio (com áudio per-article)..." | tee -a "$LOG_FILE"

# Gera news.json a partir do news_run.json (que já tem audio) + copia MP3s para audio/
$VENV_DIR/bin/python3 -c "
import json, os, shutil
from datetime import datetime, timezone

run_file = '$PROJECT_DIR/news_run.json'
audio_src = '$PROJECT_DIR/data/audio'
portfolio_file = '/home/robert/Documents/portfolio-html/news.json'
audio_dst = '/home/robert/Documents/portfolio-html/audio'
now_iso = datetime.now(timezone.utc).astimezone().isoformat()

items = []
if os.path.exists(run_file):
    with open(run_file) as f:
        data = json.load(f)
    raw = (data.get('pt', []) + data.get('en', []))[:15]
    for item in raw:
        entry = {
            'title': item.get('title', ''),
            'source': item.get('source', 'RSS'),
            'link': item.get('link', ''),
            'summary': item.get('summary', ''),
            'date': item.get('date', ''),
            'image': item.get('image', '')
        }
        # injeta audio por match de titulo (mesmo algoritmo do main.py)
        title = entry['title']
        safe = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in title)[:50].strip('_')
        mp3 = safe + '.mp3'
        if os.path.exists(os.path.join(audio_src, mp3)):
            entry['audio'] = 'audio/' + mp3
        items.append(entry)
    # copia MP3s referenciados para o portfolio (repo publico)
    os.makedirs(audio_dst, exist_ok=True)
    copied = 0
    for it in items:
        if it.get('audio'):
            src = os.path.join(audio_src, os.path.basename(it['audio']))
            dst = os.path.join(audio_dst, os.path.basename(it['audio']))
            if os.path.exists(src):
                shutil.copy2(src, dst)
                copied += 1
    output = {'updated': now_iso, 'items': items}
    with open(portfolio_file, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    n_audio = sum(1 for i in items if i.get('audio'))
    print(f'  {len(items)} noticias exportadas ({n_audio} com audio, {copied} MP3s copiados)')
else:
    print('  news_run.json nao encontrado')
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
