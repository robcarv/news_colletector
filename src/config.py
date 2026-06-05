import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente (.env)
load_dotenv()

class Config:
    # --- Caminhos ---
    # Define a raiz do projeto baseada na localização deste arquivo
    BASE_DIR = Path(__file__).parent.parent.absolute()
    DATA_DIR = BASE_DIR / "data"
    AUDIO_DIR = DATA_DIR / "audio"
    LOG_DIR = BASE_DIR / "logs"
    CONFIG_FILE = BASE_DIR / "feeds_config.json"

    # --- Credenciais (do .env) ---
    TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

    # --- Configurações de Comportamento ---
    # Piper TTS Vozes (offline, leve)
    VOICE_PT = "pt-BR-AntonioNeural"    # não usado (piper só tem EN)
    VOICE_EN = "en_US-amy"              # modelo piper para inglês
    
    # Limites
    MAX_SUMMARY_SENTENCES = 3     # Quantas sentenças o Sumy vai gerar
    MAX_ITEMS_PER_FEED = 3        # Máximo de notícias por feed por execução
    RETENTION_DAYS = 3            # Dias para manter áudios antes de apagar
    MAX_AUDIO_CHARS = 2000        # Máximo de caracteres para gerar áudio (cabe em ~1min)
    
    # Histórico (evita re-enviar notícias)
    HISTORY_FILE = BASE_DIR / "history.json"
    MAX_HISTORY = 100             # Máximo de títulos no histórico

    @staticmethod
    def setup_folders():
        """Garante que as pastas necessárias existem"""
        Config.DATA_DIR.mkdir(exist_ok=True)
        Config.AUDIO_DIR.mkdir(exist_ok=True)
        Config.LOG_DIR.mkdir(exist_ok=True)

    @staticmethod
    def load_feeds():
        """Carrega a lista de RSS do arquivo JSON"""
        if not Config.CONFIG_FILE.exists():
            logging.error(f"Arquivo de configuração não encontrado: {Config.CONFIG_FILE}")
            return []
            
        try:
            with open(Config.CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Erro ao ler feeds_config.json: {e}")
            return []

# Configuração de Log Global
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_DIR / "app.log"),
        logging.StreamHandler()
    ]
)