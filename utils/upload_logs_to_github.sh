#!/bin/bash
# set -x  # Ativa o modo debug (mostra cada comando executado)

# # Configurações
# REPO_DIR="/home/robert/Documents/vscode_projects/news_colletector"
# DATA_DIR="${REPO_DIR}/data"

# echo "=== DEBUG: Verificando diretórios ==="
# ls -la $DATA_DIR
# ls -la $REPO_DIR/.gitignore

# echo "=== DEBUG: Verificando arquivos JSON ==="
# find "$DATA_DIR" -name "*.json" -exec ls -la {} \;

# echo "=== DEBUG: Verificando chave SSH ==="
# ls -la ~/.ssh/
# ssh-add -l



# upload_feeds_to_github.sh - Script para enviar feeds JSON para o GitHub
#!/bin/bash
# upload_logs_to_github.sh - Script para enviar dados JSON e logs para o GitHub

# Cores para o output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Função para log formatado
log() {
    local level=$1
    local message=$2
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    
    case $level in
        "INFO") color=$BLUE ;;
        "SUCCESS") color=$GREEN ;;
        "WARNING") color=$YELLOW ;;
        "ERROR") color=$RED ;;
        *) color=$NC ;;
    esac
    
    echo -e "[${timestamp}] [${level}] ${color}${message}${NC}"
}

# Configurações do repositório
REPO_DIR="/home/robert/Documents/vscode_projects/news_colletector"
DATA_DIR="${REPO_DIR}/data"
LOG_DIR="${REPO_DIR}/logs"
BRANCH="main"
MAX_LOG_FILES=5 # Número máximo de arquivos de log a manter

# Configurações Git
export GIT_SSH_COMMAND="ssh -i /home/robert/.ssh/id_rsa -o StrictHostKeyChecking=no"
export GIT_AUTHOR_NAME="robcarv"
export GIT_AUTHOR_EMAIL="robert_carvalho@hotmail.com"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

# Função para limpar logs antigos
clean_old_logs() {
    log "INFO" "Limpando logs antigos (mantendo os $MAX_LOG_FILES mais recentes)..."
    cd "$LOG_DIR" || return
    
    # Lista todos os logs, ordena por data (mais recente primeiro) e mantém apenas os MAX_LOG_FILES mais novos
    ls -t output_*.log 2>/dev/null | tail -n +$(($MAX_LOG_FILES + 1)) | while read -r old_log; do
        log "INFO" "Removendo log antigo: $old_log"
        rm -f "$old_log"
    done
    
    cd - >/dev/null || return
}

# Função principal
upload_to_github() {
    log "INFO" "${BOLD}=== Iniciando upload de dados e logs para GitHub ===${NC}"
    
    # Verificar se o diretório do repositório existe
    if [ ! -d "$REPO_DIR" ]; then
        log "ERROR" "Diretório do repositório não encontrado: $REPO_DIR"
        return 1
    fi
    
    cd "$REPO_DIR" || {
        log "ERROR" "Falha ao acessar diretório do repositório"
        return 1
    }
    
    # Sincronizar com o repositório remoto
    log "INFO" "Sincronizando com o repositório remoto..."
    git config pull.rebase false
    git pull origin "$BRANCH" 2>&1 | while read -r line; do log "GIT" "$line"; done
    
    # Verificar se há mudanças para commitar
    local changes=false
    
    # Verificar arquivos JSON
    if [ -d "$DATA_DIR" ]; then
        json_files=($(find "$DATA_DIR" -maxdepth 1 -name "*.json"))
        if [ ${#json_files[@]} -gt 0 ]; then
            git add "data/"*.json
            changes=true
            log "INFO" "Adicionados ${#json_files[@]} arquivos JSON"
        fi
    fi
    
    # Verificar arquivos de log
    if [ -d "$LOG_DIR" ]; then
        log_files=($(find "$LOG_DIR" -maxdepth 1 -name "output_*.log"))
        if [ ${#log_files[@]} -gt 0 ]; then
            git add "logs/"output_*.log
            changes=true
            log "INFO" "Adicionados ${#log_files[@]} arquivos de log"
        fi
    fi
    
    if ! $changes; then
        log "WARNING" "Nenhuma mudança detectada para commitar"
        return 0
    fi
    
    # Criar mensagem de commit
    local commit_msg="Atualização automática - $(date +'%d/%m/%Y %H:%M:%S')"
    commit_msg+=$'\n\nArquivos modificados:'
    
    # Listar arquivos modificados na mensagem de commit
    git diff --name-only --cached | while read -r file; do
        commit_msg+=$'\n- '"$file"
    done
    
    # Fazer commit
    log "INFO" "Criando commit..."
    git commit -m "$commit_msg" 2>&1 | while read -r line; do log "GIT" "$line"; done
    
    # Fazer push
    log "INFO" "Enviando para o repositório remoto..."
    if git push origin "$BRANCH" 2>&1 | while read -r line; do log "GIT" "$line"; done; then
        log "SUCCESS" "Dados e logs enviados com sucesso para GitHub!"
        log "INFO" "URL: https://github.com/robcarv/news_colletector/tree/$BRANCH"
        
        # Limpar logs antigos após upload bem-sucedido
        clean_old_logs
    else
        log "ERROR" "Falha ao enviar para o GitHub. Tentando recuperação..."
        
        # Tentar recuperação com rebase
        git pull --rebase origin "$BRANCH" && \
        git push origin "$BRANCH" || {
            log "ERROR" "Falha na recuperação. Resolva os conflitos manualmente."
            return 1
        }
    fi
    
    cd - >/dev/null || return
    log "INFO" "${BOLD}=== Processo concluído ===${NC}"
}

# Executar função principal
upload_to_github

# Verificar se houve erros e sair com código apropriado
if [ $? -eq 0 ]; then
    exit 0
else
    exit 1
fi