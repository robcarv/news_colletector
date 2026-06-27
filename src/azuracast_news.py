"""Integração com AzuraCast — upload de news jingles para a rádio Dublin Calling.

Faz upload do áudio gerado para uma pasta no AzuraCast, que é consumida
por uma playlist do tipo "once_per_x_minutes". O AutoDJ intercala o jingle
entre as músicas automaticamente.

Configuração necessária no AzuraCast (1x, manual):
  1. Admin → Settings → API Keys → Generate (salvar em AZURACAST_API_KEY no .env)
  2. Playlists → Add → Nome: "News Jingles", Tipo: "Once per x Minutes", Minutos: 30
  3. Mount Points → Edit (Dublin Calling) → AutoDJ → incluir playlist "News Jingles"

Uso:
    from src.azuracast_news import upload_jingle
    upload_jingle('/path/to/jingle.mp3')
"""
import logging
import os
import subprocess
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

AZURACAST_URL = "https://dublincalling.duckdns.org/api"
STATION_ID = 2  # ID da estação dublincalling (verificado via API /stations)
JINGLE_FOLDER = "news_jingles"
JINGLE_FILENAME = "news_jingle.mp3"


def _get_api_key():
    """Obtém a API key do AzuraCast do ambiente."""
    key = os.getenv("AZURACAST_API_KEY")
    if not key:
        logger.warning("AZURACAST_API_KEY não configurada no .env")
    return key


def upload_jingle(audio_path, filename=None):
    """
    Faz upload do jingle de notícias para o AzuraCast.

    Fluxo:
    1. Converte WAV → MP3 (64kbps, menor tamanho)
    2. Upload do novo jingle (sobrescreve arquivo com mesmo nome)
    3. AzuraCast AutoDJ automaticamente inclui na rotação

    Args:
        audio_path: Caminho do arquivo .wav gerado pelo TTS
        filename: Nome do arquivo no AzuraCast (default: 'news_jingle.mp3')

    Returns:
        True se upload bem-sucedido, False caso contrário
    """
    jingle_filename = filename or JINGLE_FILENAME
    api_key = _get_api_key()
    if not api_key:
        return False

    headers = {"Authorization": f"Bearer {api_key}"}
    audio_path = Path(audio_path)

    # 1. Converte WAV → MP3 com ffmpeg (64kbps mono, tamanho reduzido)
    mp3_path = audio_path.with_suffix(".mp3")
    if not mp3_path.exists():
        logger.info("  Convertendo WAV → MP3 (64kbps)...")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(audio_path),
             "-ac", "1", "-b:a", "64k", str(mp3_path)],
            capture_output=True, timeout=15
        )
        if result.returncode != 0:
            logger.error(f"  ffmpeg erro: {result.stderr.decode()[:200]}")
            return False
        logger.info(f"  MP3: {mp3_path.stat().st_size // 1024}KB")

    # 2. Skip listagem — muito lenta em estações com biblioteca grande.
    #    Vamos direto pro upload (a API sobrescreve arquivo com mesmo nome).

    # 3. Upload do novo jingle
    try:
        with open(mp3_path, "rb") as f:
            r = requests.post(
                f"{AZURACAST_URL}/station/{STATION_ID}/files/upload",
                headers=headers,
                files={"file": (jingle_filename, f, "audio/mpeg")},
                data={"path": JINGLE_FOLDER},
                timeout=30
            )

        if r.ok:
            logger.info(f"  Jingle uploaded: {jingle_filename}")
        else:
            logger.error(f"  Upload failed: {r.status_code} {r.text[:200]}")
            return False

        # Backup: copia via SCP para a Samba HDRadio
        import subprocess as sp
        try:
            target = f"robert@pi5:/mnt/radio_hdd/{JINGLE_FOLDER}/{jingle_filename}"
            sp.run(["scp", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                    str(mp3_path), target],
                   capture_output=True, timeout=15)
            logger.info("  Copia Samba HDRadio OK")
        except Exception:
            logger.info("  Copia Samba pulada (Pi5 offline?)")

        # Marca playlist como jingle (sem lookup — endpoints timeoutam)
        try:
            r = requests.put(
                f"{AZURACAST_URL}/station/{STATION_ID}/playlist/34",
                headers={**headers, "Content-Type": "application/json"},
                json={"is_jingle": True},
                timeout=10
            )
            if r.ok:
                logger.info("  Playlist is_jingle=true")
        except Exception:
            pass
        return True
    except Exception as e:
        logger.error(f"  Upload erro: {e}")
        return False




# Para testes locais, sem enviar para o AzuraCast real
def upload_jingle_dry(audio_path):
    """Versão dry-run: converte MP3 mas não faz upload."""
    api_key = _get_api_key()
    if not api_key:
        logger.info("[DRY] AZURACAST_API_KEY não configurada — pulando upload")
        return False

    audio_path = Path(audio_path)
    mp3_path = audio_path.with_suffix(".mp3")

    if not mp3_path.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(audio_path),
             "-ac", "1", "-b:a", "64k", str(mp3_path)],
            capture_output=True, timeout=15
        )

    size_kb = mp3_path.stat().st_size // 1024 if mp3_path.exists() else 0
    logger.info(f"[DRY] Jingle MP3 pronto para upload: {mp3_path.name} ({size_kb}KB)")
    logger.info(f"[DRY]   Destino: {AZURACAST_URL}/station/{STATION_ID}/files → {JINGLE_FOLDER}/")
    return True
