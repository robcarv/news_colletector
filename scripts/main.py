import os
import subprocess

# Lista de scripts a serem executados
scripts = [
    "rss_collector.py",
    "summarizer.py",
    "text_to_speech_gtts.py"
]

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

    # Executa cada script na ordem
    for script in scripts:
        run_script(script)

    print("All scripts executed successfully.")

if __name__ == "__main__":
    main()