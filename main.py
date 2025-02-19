import os
import subprocess
import shutil
import logging

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lista de scripts a serem executados
scripts = [
    "rss_collector.py",
    "summarizer.py",
    "text_to_speech.py"
]

def clean_folder(folder_path):
    """
    Limpa o conteúdo de uma pasta, removendo todos os arquivos e subpastas.
    """
    if os.path.exists(folder_path):
        logger.info(f"🔧 Limpando pasta: {folder_path}")
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
        logger.warning(f"⚠️ Pasta não existe: {folder_path}")

def run_script(script_name):
    """
    Executa um script Python.
    """
    try:
        logger.info(f"🚀 Executando {script_name}...")
        subprocess.run(["python3", script_name], check=True)
        logger.info(f"✅ {script_name} executado com sucesso.")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Erro ao executar {script_name}: {e}")
    except FileNotFoundError:
        logger.error(f"❌ Script não encontrado: {script_name}")

def main():
    """
    Função principal que executa todos os scripts na ordem.
    """
    try:
        # Navega até a pasta do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        logger.info(f"📂 Diretório do script: {script_dir}")

        # Define os caminhos das pastas data e audio
        data_folder = os.path.join(script_dir, "data")
        audio_folder = os.path.join(data_folder, "audio")
        
        # Limpa as pastas data e audio antes de executar os scripts
        clean_folder(data_folder)  # Limpa a pasta data
        clean_folder(audio_folder)  # Limpa a pasta audio (se existir)

        # Executa cada script na ordem
        for script in scripts:
            run_script(script)

        logger.info("🎉 Todos os scripts foram executados com sucesso.")
    except Exception as e:
        logger.error(f"❌ Erro durante a execução do main.py: {e}")

if __name__ == "__main__":
    main()