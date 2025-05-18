#!/bin/bash

# upload_feeds_to_github.sh - Script para enviar feeds JSON para o GitHub

# Cores para o output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

# Função para log
log_message() {
    local level=$1
    local message=$2
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo -e "[${timestamp}] [${level}] ${message}"
}

# Configurações
REPO_DIR="/home/robert/Documents/vscode_projects/news_colletector"  # Diretório do seu repositório
REPO_URL="git@github.com:robcarv/news_colletector.git"
DATA_DIR="${REPO_DIR}/data"  # Pasta onde os JSONs são gerados
BRANCH="main"

# Configurações Git
export GIT_SSH_COMMAND="ssh -i /home/robert/.ssh/id_rsa -o StrictHostKeyChecking=no"
export GIT_AUTHOR_NAME="robcarv"
export GIT_AUTHOR_EMAIL="robert_carvalho@hotmail.com"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

# Função principal
upload_feeds_to_github() {
    log_message "INFO" "${BOLD}${BLUE}=== Enviando feeds JSON para o GitHub ===${RESET}"
    
    # 1. Verificar se existem arquivos JSON na pasta data
    if [ ! -d "$DATA_DIR" ]; then
        log_message "ERROR" "${RED}Pasta data não encontrada em: ${DATA_DIR}${RESET}"
        return 1
    fi
    
    local json_files=($(find "$DATA_DIR" -maxdepth 1 -name "*.json"))
    if [ ${#json_files[@]} -eq 0 ]; then
        log_message "WARNING" "${YELLOW}Nenhum arquivo JSON encontrado para upload${RESET}"
        return 0
    fi
    
    log_message "INFO" "Arquivos JSON encontrados: ${#json_files[@]}"
    
    # 2. Preparar repositório
    if [ ! -d "$REPO_DIR" ]; then
        log_message "INFO" "Clonando repositório GitHub..."
        git clone "$REPO_URL" "$REPO_DIR" || {
            log_message "ERROR" "${RED}Falha ao clonar repositório${RESET}"
            return 1
        }
    fi
    
    cd "$REPO_DIR" || {
        log_message "ERROR" "${RED}Falha ao acessar diretório do repositório${RESET}"
        return 1
    }
    
    # 3. Sincronizar com remoto
    git config pull.rebase false
    git pull origin "$BRANCH" 2>&1 | while read line; do log_message "GIT" "$line"; done || {
        log_message "WARNING" "${YELLOW}Falha ao atualizar repositório, continuando...${RESET}"
    }
    
    # 4. Copiar arquivos JSON para o repositório (se DATA_DIR for diferente)
    if [ "$DATA_DIR" != "${REPO_DIR}/data" ]; then
        mkdir -p "${REPO_DIR}/data"
        cp -v "$DATA_DIR"/*.json "${REPO_DIR}/data/" | while read line; do log_message "COPY" "$line"; done
    fi
    
    # 5. Commitar e enviar
    git add "data/"*.json
    
    # Verificar se há mudanças para commitar
    if git diff-index --quiet HEAD --; then
        log_message "INFO" "Nenhuma mudança detectada nos arquivos JSON."
    else
        local timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
        local commit_msg="Atualização automática de feeds em $(date '+%d/%m/%Y %H:%M:%S')"
        
        git commit -m "$commit_msg" 2>&1 | while read line; do log_message "GIT" "$line"; done
        
        if git push origin "$BRANCH" 2>&1 | while read line; do log_message "GIT" "$line"; done; then
            log_message "SUCCESS" "${GREEN}Feeds enviados para GitHub com sucesso!${RESET}"
            log_message "INFO" "URL: https://github.com/robcarv/news_colletector/tree/main/data"
        else
            log_message "ERROR" "${RED}Falha no push para o GitHub${RESET}"
            # Tentar recuperação
            git pull --rebase origin "$BRANCH" && \
            git push origin "$BRANCH" || {
                log_message "ERROR" "${RED}Falha na recuperação${RESET}"
                cd - >/dev/null
                return 1
            }
        fi
    fi
    
    # 6. Limpeza
    cd - >/dev/null
    log_message "INFO" "${BOLD}${BLUE}=== Processo concluído ===${RESET}"
}

# Executar função principal
upload_feeds_to_github