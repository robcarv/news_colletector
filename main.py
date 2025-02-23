# main.py
import os
import subprocess
import shutil
import logging

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lista de scripts a serem executados
scripts = [
    "rss_collector.py",  # Coleta as notícias dos feeds RSS
    "summarizer.py",     # Sumariza as notícias coletadas
    "text_to_speech_en.py", # Gera áudios e envia para o Telegram e Anchor
    "text_to_speech_pt.py"
]

# Função para limpar o conteúdo de uma pasta
def clean_folder(folder_path):
    """
    Limpa o conteúdo de uma pasta.
    :param folder_path: Caminho da pasta a ser limpa.
    """
    if os.path.exists(folder_path):
        logger.info(f"🧹 Limpando pasta: {folder_path}")
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)  # Remove arquivos e links simbólicos
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)  # Remove subpastas e seu conteúdo
            except Exception as e:
                logger.error(f"❌ Falha ao deletar {file_path}. Motivo: {e}")
    else:
        logger.info(f"📁 Pasta não existe: {folder_path}")

# Função para executar um script
def run_script(script_name):
    """
    Executa um script Python.
    :param script_name: Nome do script a ser executado.
    """
    try:
        logger.info(f"🚀 Executando {script_name}...")
        subprocess.run(["python3", script_name], check=True)
        logger.info(f"✅ {script_name} executado com sucesso.")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Erro ao executar {script_name}: {e}")

# Função principal
def main():
    """
    Função principal que orquestra a execução dos scripts.
    """
    # Navega até a pasta scripts (se necessário)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Limpa as pastas data e audio antes de executar os scripts
    data_folder = "./data"
    audio_folder = os.path.join(data_folder, "audio")
    
    clean_folder(data_folder)  # Limpa a pasta data
    clean_folder(audio_folder)  # Limpa a pasta audio (se existir)

    # Executa cada script na ordem
    for script in scripts:
        run_script(script)

    logger.info("🎉 Todos os scripts foram executados com sucesso.")

if __name__ == "__main__":
    main()