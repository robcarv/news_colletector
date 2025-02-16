import os
import subprocess
import shutil

# Lista de scripts a serem executados
scripts = [
    "rss_collector.py",
    "summarizer.py",
    "text_to_speech_gtts.py"
]

# Função para limpar o conteúdo de uma pasta
def clean_folder(folder_path):
    if os.path.exists(folder_path):
        print(f"Cleaning folder: {folder_path}")
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)  # Remove arquivos e links simbólicos
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)  # Remove subpastas e seu conteúdo
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")
    else:
        print(f"Folder does not exist: {folder_path}")

# Função para executar um script
def run_script(script_name):
    try:
        print(f"Executing {script_name}...")
        subprocess.run(["python3", script_name], check=True)
        print(f"{script_name} completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error executing {script_name}: {e}")

# Função principal
def main():
    # Navega até a pasta scripts
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Limpa as pastas data e audio antes de executar os scripts
    data_folder = "../data"
    audio_folder = os.path.join(data_folder, "audio")
    
    clean_folder(data_folder)  # Limpa a pasta data
    clean_folder(audio_folder)  # Limpa a pasta audio (se existir)

    # Executa cada script na ordem
    for script in scripts:
        run_script(script)

    print("All scripts executed successfully.")

if __name__ == "__main__":
    main()