#!/bin/bash
# =============================================================================
# sync_portfolio.sh - Push noticias + metadados para robcarv.github.io
# =============================================================================
# Chamado por sync_git.sh apos cada execucao do NewsBot.
# Faz push do news.json (ultimas noticias) e health.json para o portfolio.
# =============================================================================

PORTFOLIO_DIR="/home/robert/Documents/portfolio-html"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "  sync_portfolio.sh - $DATE"

cd "$PORTFOLIO_DIR" || { echo "  ERRO: $PORTFOLIO_DIR nao encontrado"; exit 1; }

# Configura git para commits automaticos
export GIT_SSH_COMMAND="ssh -i /home/robert/.ssh/id_ed25519 -o StrictHostKeyChecking=no"
export GIT_AUTHOR_NAME="robcarv"
export GIT_AUTHOR_EMAIL="nore...c.dev"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

# Verifica se news.json existe (deve ter sido gerado pelo run_newsbot.sh)
if [ ! -f "$PORTFOLIO_DIR/news.json" ]; then
    echo "  Aviso: news.json nao encontrado em $PORTFOLIO_DIR"
    # Cria um vazio para nao quebrar
    echo '{"updated":"'"$DATE"'","items":[]}' > "$PORTFOLIO_DIR/news.json"
fi

# health.json (opcional — pode faltar se Pi5 estiver offline)
if [ -f "$PORTFOLIO_DIR/health.json" ]; then
    git add health.json
    echo "  health.json adicionado"
fi

# Adiciona arquivos essenciais e forca rebuild do GitHub Pages
git add news.json
touch index.html index.en.html index.pt.html
git add index.html index.en.html index.pt.html

# Radio metadata (se atualizado)
if [ -f "$PORTFOLIO_DIR/radio_metadata.json" ]; then
    git add radio_metadata.json
fi

# Verifica se realmente ha mudancas
if git diff --cached --quiet; then
    echo "  Nada novo no portfolio — pulando commit"
    exit 0
fi

# Commit e push
git commit -m "news: update feed $(date '+%d/%m/%Y %H:%M')" -q 2>/dev/null || true

if git push origin main -q 2>&1; then
    echo "  OK robcarv.github.io atualizado"
else
    echo "  Falha no push, tentando pull + rebase..."
    if git pull --rebase origin main -q && git push origin main -q 2>&1; then
        echo "  OK robcarv.github.io (com rebase)"
    else
        echo "  ERRO: falha definitiva no push do portfolio"
    fi
fi
