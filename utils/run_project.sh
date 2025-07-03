#!/bin/bash

# Configurações
PROJECT_DIR="/home/robert/Documents/vscode_projects/news_colletector"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/output_$(date +'%Y-%m-%d_%H-%M-%S').log"
VENV_ACTIVATE="${PROJECT_DIR}/venv/bin/activate"
UPLOAD_SCRIPT="${PROJECT_DIR}/utils/upload_logs_to_github.sh"

# Função para executar antes de cada Python
pre_python_hook() {
    local script_name=$1
    echo "==== PRE-HOOK para $script_name ===="
    
    # 1. Verificar integridade do ambiente
    if ! python3 -c "import sys; print(sys.executable)" &>/dev/null; then
        echo "❌ Ambiente Python corrompido!"
        return 1
    fi
    
    # 2. Verificar dependências
    if [ "$script_name" == "main.py" ]; then
        echo "Verificando dependências do main.py..."
        python3 -c "import requests, bs4" || {
            echo "❌ Bibliotecas essenciais faltando!"
            return 1
        }
    fi

    # 3. Limpeza temporária
    find /tmp -name "tmp_*" -mtime +1 -delete 2>/dev/null
    
    # 4. Log de recursos
    echo "Uso de recursos pré-execucao:"
    free -h | awk '/Mem:/ {printf("Mem: %s/%s\n", $3, $2)}'
    echo "============================"
    
    return 0
}

# Função segura para executar Python
run_python() {
    local script=$1
    shift
    local args=("$@")
    
    if ! pre_python_hook "$script"; then
        echo "Falha no pre-hook. Abortando $script"
        return 1
    fi
    
    echo "▶️  Executando: python3 $script ${args[*]}"
    python3 "$script" "${args[@]}"
    local status=$?
    
    # Pós-execução
    echo "ℹ️  Status de saída: $status"
    return $status
}

# Execução principal
{
    echo "======== INÍCIO DA EXECUÇÃO ========="
    echo "Data: $(date)"
    echo "Log: $LOG_FILE"
    
    # Ambiente
    source "$VENV_ACTIVATE" || exit 1
    cd "$PROJECT_DIR" || exit 1

    # Executar main.py com hook
    run_python "main.py"
    EXIT_STATUS=$?

    # Tratamento de erros
    case $EXIT_STATUS in
        0) echo "✅ Sucesso" ;;
        137) echo "❌ SIGKILL: Falta de memória?" ;;
        *) echo "❌ Erro $EXIT_STATUS" ;;
    esac
    
    echo "========= FIM DA EXECUÇÃO ========="
 # Upload independente do status 
    if [ -x "$UPLOAD_SCRIPT" ]; then
        echo "Iniciando upload para GitHub..."
        "$UPLOAD_SCRIPT"
        UPLOAD_STATUS=$?
        [ $UPLOAD_STATUS -eq 0 ] && echo "✅ Upload concluído" || echo "❌ Falha no upload"
    fi
    
    exit $EXIT_STATUS  # Mantém o status original da execução do main.py
    
} > "$LOG_FILE" 2>&1