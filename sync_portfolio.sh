#!/bin/bash
# =============================================================================
# sync_portfolio.sh v4 - Push noticias + metadados para robcarv.github.io
# =============================================================================
# Chamado por sync_git.sh apos cada execucao do NewsBot.
# Faz push do news.json (ultimas noticias) e health.json para o portfolio.
# =============================================================================
# v4: usa fetch+reset (nao pull+rebase) para evitar merge conflicts.
#     news.json e health.json sao auto-gerados — sempre sobrescrevem.
# =============================================================================

PORTFOLIO_DIR="/home/robert/Documents/portfolio-html"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "  sync_portfolio.sh v4 - $DATE"

cd "$PORTFOLIO_DIR" || { echo "  ERRO: $PORTFOLIO_DIR nao encontrado"; exit 1; }

# Configura git para commits automaticos
export GIT_SSH_COMMAND="ssh -i /home/robert/.ssh/id_ed25519 -o StrictHostKeyChecking=no"
export GIT_AUTHOR_NAME="robcarv"
export GIT_AUTHOR_EMAIL="noreply@robcarv.dev"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

# Verifica se news.json existe (deve ter sido gerado pelo run_newsbot.sh)
if [ ! -f "$PORTFOLIO_DIR/news.json" ]; then
    echo "  Aviso: news.json nao encontrado em $PORTFOLIO_DIR"
    echo "{\"updated\":\"$DATE\",\"items\":[]}" > "$PORTFOLIO_DIR/news.json"
fi

# ─── Estrategia v4: fetch + reset (evita merge conflicts) ───────────────────
# news.json e health.json sao 100% auto-gerados — SEMPRE sobrescrevem o remoto.
# Em vez de pull+rebase (que conflita), fazemos:
#   1. fetch para pegar o estado do remoto
#   2. reset --soft para posicionar no remoto (mantendo mudancas locais unstaged)
#   3. add apenas os arquivos que queremos
#   4. commit + push

echo "  Fetching remote..."
if ! git fetch origin main -q 2>&1; then
    echo "  Aviso: fetch falhou, tentando push direto..."
fi

# Guarda mudancas locais nao comitadas (se houver)
git stash -q 2>/dev/null || true

# Reseta para o estado do remoto (soft = mantem arquivos locais intactos)
if git rev-parse origin/main >/dev/null 2>&1; then
    git reset --soft origin/main 2>/dev/null || true
else
    echo "  Aviso: origin/main nao encontrado, pulando reset"
fi

# Restaura stash (se havia algo)
git stash pop -q 2>/dev/null || true

# ─── Adiciona arquivos ─────────────────────────────────────────────────────

# health.json (opcional — pode faltar se Pi5 estiver offline)
if [ -f "$PORTFOLIO_DIR/health.json" ]; then
    git add health.json
    echo "  health.json adicionado"
fi

# news.json (sempre — gerado pelo run_newsbot.sh)
git add news.json

# Touch index files para forcar rebuild do GitHub Pages
touch index.html index.en.html index.pt.html
git add index.html index.en.html index.pt.html

# Radio metadata (se atualizado)
if [ -f "$PORTFOLIO_DIR/radio_metadata.json" ]; then
    git add radio_metadata.json
fi

# ─── Commit e push ─────────────────────────────────────────────────────────

# Verifica se realmente ha mudancas comparado ao remoto
if git diff --cached --quiet; then
    echo "  Nada novo no portfolio — pulando commit"
    exit 0
fi

# Commit e push
git commit -m "news: update feed $(date '+%d/%m/%Y %H:%M')" -q 2>/dev/null || true

if git push origin main -q 2>&1; then
    echo "  OK robcarv.github.io atualizado"
else
    # Fallback: force-with-lease (mais seguro que --force)
    echo "  Push normal falhou, tentando force-with-lease..."
    if git push origin main --force-with-lease -q 2>&1; then
        echo "  OK robcarv.github.io (force-with-lease)"
    else
        echo "  ERRO: falha definitiva no push do portfolio"
        exit 1
    fi
fi
