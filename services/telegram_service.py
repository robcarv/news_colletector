# services/telegram_service.py
import os
import requests
import logging
from dotenv import load_dotenv
from utils.text_processing import format_telegram_message, clean_text

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

def send_to_telegram(title, summary, source, source_link, audio_path):
    """
    Envia uma mensagem formatada para o Telegram com o título, resumo, fonte e áudio da notícia.
    """
    try:
        # Formata a mensagem para o Telegram
        message = format_telegram_message(title, summary, source, source_link)

        # Envia a mensagem de texto
        url_text = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'MarkdownV2'  # Usa MarkdownV2 para melhor formatação
        }
        response_text = requests.post(url_text, data=payload)
        if response_text.status_code != 200:
            logger.error(f"❌ Erro ao enviar mensagem de texto para o Telegram: {response_text.text}")
            return

        # Verifica se o arquivo de áudio existe antes de enviar
        if not os.path.exists(audio_path):
            logger.error(f"❌ Arquivo de áudio não encontrado: {audio_path}")
            return

        # Envia o áudio
        url_audio = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"
        with open(audio_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            data = {'chat_id': CHAT_ID}
            response_audio = requests.post(url_audio, files=files, data=data)
            if response_audio.status_code != 200:
                logger.error(f"❌ Erro ao enviar áudio para o Telegram: {response_audio.text}")
            else:
                logger.info(f"✅ Áudio e mensagem enviados com sucesso para o Telegram.")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar mensagem ou áudio para o Telegram: {e}")