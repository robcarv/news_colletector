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
    Para mensagens longas (>4000 chars), use send_telegram_long_message().
    """
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        logger.warning("Credenciais do Telegram não configuradas.")
        return False

    # Telegram tem limite de 4096 chars por mensagem
    if len(message) > 4000:
        logger.warning(f"Mensagem longa ({len(message)} chars) — truncando. Use send_telegram_long_message().")
        message = message[:3997] + "..."

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    return _telegram_request("POST", url, data=payload)


def send_telegram_long_message(message, max_chunk=3800):
    """
    Envia mensagem longa em chunks numerados.
    Split por quebras de linha duplas (paragrafos) para nao cortar no meio.
    
    Args:
        message: Texto completo da mensagem
        max_chunk: Tamanho maximo por chunk (default 3800, seguro para Markdown)
    
    Returns:
        True se todos os chunks foram enviados
    """
    if not Config.TELEGRAM_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return False
    
    if len(message) <= max_chunk:
        return send_telegram_message(message)
    
    # Split por paragrafos (double newlines)
    paragraphs = message.split('\n\n')
    chunks = []
    current = ""
    
    for p in paragraphs:
        # Se um unico paragrafo excede max_chunk, divide por linhas
        if len(p) > max_chunk:
            lines = p.split('\n')
            for line in lines:
                if len(current) + len(line) + 2 <= max_chunk:
                    current += line + "\n" if current else line
                else:
                    if current:
                        chunks.append(current.strip())
                    current = line
        elif len(current) + len(p) + 2 <= max_chunk:
            current += p + "\n\n" if current else p
        else:
            if current:
                chunks.append(current.strip())
            current = p
    
    if current:
        chunks.append(current.strip())
    
    # Fallback: se ainda tem chunks > max_chunk, split forcado
    final_chunks = []
    for chunk in chunks:
        while len(chunk) > max_chunk:
            final_chunks.append(chunk[:max_chunk])
            chunk = chunk[max_chunk:]
        if chunk:
            final_chunks.append(chunk)
    
    total = len(final_chunks)
    success = True
    for i, chunk in enumerate(final_chunks, 1):
        prefix = f"({i}/{total}) " if total > 1 else ""
        if not send_telegram_message(prefix + chunk):
            success = False
            logger.error(f"Falha ao enviar chunk {i}/{total}")
        else:
            logger.info(f"📤 Chunk {i}/{total} enviado ({len(chunk)} chars)")
    
    return success


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
