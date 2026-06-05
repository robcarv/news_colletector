#!/bin/bash
# =============================================================================
# News Collector - Sync GitHub v2
# =============================================================================
# Sincroniza logs, histórico, config e feeds com o GitHub.
# Chamado pelo cron após cada execução.
# Sempre faz push mesmo se não houver mudanças (força update do log).
# =============================================================================

set -e

PROJECT_DIR="/home/robert/Documents/vscode_projects/news_colletector"
cd "$PROJECT_DIR" || { echo "❌ Diretório não encontrado: $PROJECT_DIR"; exit 1; }

DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Configura git para commits automáticos
export GIT_SSH_COMMAND="ssh -i /home/robert/.ssh/id_rsa -o StrictHostKeyChecking=no"
export GIT_AUTHOR_NAME="robcarv"
export GIT_AUTHOR_EMAIL="robert_carvalho@hotmail.com"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

# Adiciona tudo: logs, histórico, config, scripts
git add -A

# Verifica se tem algo para commitar
if git diff --cached --quiet; then
    echo "📭 Nada novo para commitar em $DATE"
    exit 0
fi

# Pega um resumo das mudanças para a mensagem de commit
SUMMARY=$(git diff --cached --name-only | head -10)
NEWS_COUNT=$(git diff --cached -- '*.json' | grep '"title"' | wc -l)

COMMIT_MSG="NewsBot: $(date '+%d/%m/%Y %H:%M') - ${NEWS_COUNT} noticias

Arquivos alterados:
$(echo "$SUMMARY" | sed 's/^/  - /')"

git commit -m "$COMMIT_MSG" -q

if git push origin main -q 2>&1; then
    echo "✅ GitHub sync concluído em $DATE"
else
    echo "⚠️  Falha no push, tentando pull + rebase..."
    git pull --rebase origin main -q && git push origin main -q && \
        echo "✅ GitHub sync (com rebase) concluído" || \
        echo "❌ Falha definitiva no GitHub push"
fi
