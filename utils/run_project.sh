#!/bin/bash

# Configurações
LOG_DIR="/home/robert/Documents/vscode_projects/news_colletector/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/output_$(date +'%Y-%m-%d_%H-%M-%S').log"

# Ativa o ambiente virtual
source /home/robert/Documents/vscode_projects/news_colletector/venv/bin/activate

# Navega até o diretório do projeto
cd /home/robert/Documents/vscode_projects/news_colletector

# Executa o script main.py e salva o output
{
    echo "=== INÍCIO DA EXECUÇÃO: $(date) ==="
    python3 main.py
    echo "=== FIM DA EXECUÇÃO: $(date) ==="
    echo "STATUS DE SAÍDA: $?"
} > "$LOG_FILE" 2>&1

# Verifica o resultado
if [ $? -eq 0 ]; then
    echo "✅ Coleta de notícias concluída. Log salvo em $LOG_FILE"
    echo "Iniciando upload para GitHub..."
    
    # Executa o script de upload
    /home/robert/Documents/vscode_projects/news_colletector/utils/upload_logs_to_github.sh
    
    if [ $? -eq 0 ]; then
        echo "✅ Upload concluído com sucesso!"
    else
        echo "❌ Falha no upload para GitHub"
        exit 1
    fi
else
    echo "❌ Falha na coleta de notícias. Verifique o log em $LOG_FILE"
    exit 1
fi