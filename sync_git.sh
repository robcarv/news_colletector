#!/bin/bash

# Caminho do projeto (Certifique-se que este é o caminho correto!)
PROJECT_DIR="/home/robert/Documents/vscode_projects/news_colletector"
cd "$PROJECT_DIR" || exit

# Data atual para o commit
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# 1. Adiciona os arquivos novos (Logs e Áudios .wav)
# A pasta data/audio pode crescer, se quiser economizar espaço no Git, remova esta linha:
git add data/audio/*.wav

# Adiciona o log principal (vai ser gerado pelo Cron)
git add logs/*.log 

# Adiciona quaisquer arquivos modificados, como o log principal
git add main.py

# 2. Commit e Push
# A flag -q silencia o output do git, mas é bom para o Cron
git commit -q -m "Auto-update: Logs e Áudios de $DATE"
git push -q origin main

echo "✅ Sincronização com GitHub concluída em $DATE"
