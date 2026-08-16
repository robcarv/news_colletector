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
#   2. add SOMENTE os arquivos gerados (news.json/health.json/radio_metadata.json)
#   3. commit + push (com pull --rebase se o remoto andou)
# NOTA (2026-07-31): NUNCA adicionar/tocar index.html ou outros arquivos de
# layout — um add indevido ja atropelou o layout do portfolio (commit c211428).

echo "  Fetching remote..."
git fetch origin main -q 2>&1 || echo "  Aviso: fetch falhou"

# ─── Adiciona SOMENTE arquivos gerados ─────────────────────────────────────

# health.json (opcional — pode faltar se o health cron nao rodou)
if [ -f "$PORTFOLIO_DIR/health.json" ]; then
    git add health.json
    echo "  health.json adicionado"
fi

# news.json (sempre — gerado pelo run_newsbot.sh)
git add news.json

# audio/ (MP3s per-article — gerados pelo run_newsbot.sh)
if [ -d "$PORTFOLIO_DIR/audio" ]; then
    git add audio/
fi

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
    # Remoto andou? rebase e tenta de novo (sem force)
    echo "  Push falhou — rebase e nova tentativa..."
    if git pull --rebase origin main -q 2>&1 && git push origin main -q 2>&1; then
        echo "  OK robcarv.github.io atualizado (apos rebase)"
    else
        echo "  ERRO: falha definitiva no push do portfolio"
        exit 1
    fi
fi
