import requests
import logging
import os
from .config import Config

logger = logging.getLogger(__name__)

def send_telegram_message(message):
    """
    Envia uma mensagem de texto simples para o Telegram.
    Útil para avisar que o sistema iniciou ou terminou.
    """
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        logger.warning("Credenciais do Telegram não configuradas.")
        return False

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao enviar mensagem Telegram: {e}")
        return False

def send_telegram_audio(audio_path, caption, title=None):
    """
    Envia o arquivo de áudio com legenda formatada para o Telegram.
    
    Args:
        audio_path: Caminho do arquivo .wav
        caption: Texto da legenda (já formatado)
        title: Título opcional (se não fornecido, usa caption)
    """
    if not os.path.exists(audio_path):
        logger.error(f"Arquivo de áudio não encontrado para envio: {audio_path}")
        return False

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendAudio"
    
    # Se title não foi fornecido, usa o caption como título
    if not title:
        title = caption.split('\n')[0].replace('*', '').strip()[:256]
    
    # Limita caption a 1024 caracteres (limite do Telegram)
    if len(caption) > 1000:
        caption = caption[:997] + "..."

    try:
        with open(audio_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            data = {
                'chat_id': Config.TELEGRAM_CHAT_ID,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
            
            logger.info(f"📤 Enviando para Telegram: {title}")
            response = requests.post(url, files=files, data=data, timeout=60)
            response.raise_for_status()
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao enviar áudio Telegram: {e}")
        return False
