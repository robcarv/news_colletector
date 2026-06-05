import logging
import os
import requests
from .config import Config

logger = logging.getLogger(__name__)

# ─── Sessão HTTP reutilizável (conexão persistente, mais rápido) ──────────
_session = requests.Session()
# Timeout é passado em cada chamada, não na session

def _telegram_request(method, url, **kwargs):
    """Wrapper para chamadas à API do Telegram com tratamento de erro."""
    try:
        resp = _session.request(method, url, timeout=Config.TELEGRAM_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return True
    except requests.exceptions.Timeout:
        logger.error("⏱️  Timeout na API Telegram")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("🔌 Erro de conexão com Telegram")
        return False
    except Exception as e:
        logger.error(f"❌ Erro Telegram: {e}")
        return False


def send_telegram_message(message):
    """
    Envia uma mensagem de texto para o Telegram.
    """
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        logger.warning("Credenciais do Telegram não configuradas.")
        return False

    # Telegram tem limite de 4096 chars por mensagem
    if len(message) > 4000:
        message = message[:3997] + "..."

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    return _telegram_request("POST", url, data=payload)


def send_telegram_audio(audio_path, caption, title=None):
    """
    Envia arquivo de áudio com legenda para o Telegram.
    Usa sessão reutilizável para evitar overhead de conexão.
    """
    if not os.path.exists(audio_path):
        logger.error(f"Arquivo não encontrado: {audio_path}")
        return False

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendAudio"
    
    if not title:
        title = caption.split('\n')[0].replace('*', '').strip()[:256]
    
    if len(caption) > 1000:
        caption = caption[:997] + "..."

    try:
        with open(audio_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            data = {
                'chat_id': Config.TELEGRAM_CHAT_ID,
                'caption': caption,
                'parse_mode': 'Markdown',
                'title': title[:256],
            }
            logger.info(f"📤 Enviando áudio ({os.path.getsize(audio_path)//1024}KB)...")
            return _telegram_request("POST", url, files=files, data=data)
    except Exception as e:
        logger.error(f"❌ Erro ao enviar áudio: {e}")
        return False
