#!/bin/bash

# Ativa o ambiente virtual
source /home/robert/Documents/vscode_projects/news_colletector/venv/bin/activate

# Navega até o diretório do projeto
cd /home/robert/Documents/vscode_projects/news_colletector

# Executa o script main.py
python3 main.py

# Verifica se a execução foi bem-sucedida antes de continuar
if [ $? -eq 0 ]; then
    echo "✅ Coleta de notícias concluída com sucesso. Iniciando upload para GitHub..."
    
    # Executa o script de upload para o GitHub a partir do diretório utils
    /home/robert/Documents/vscode_projects/news_colletector/utils/upload_logs_to_github.sh
    
    # Verifica o resultado do upload
    if [ $? -eq 0 ]; then
        echo "✅ Upload para GitHub concluído com sucesso!"
    else
        echo "❌ Falha no upload para GitHub"
        exit 1
    fi
else
    echo "❌ Falha na coleta de notícias. Upload para GitHub cancelado."
    exit 1
fi