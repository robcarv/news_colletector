import asyncio
import logging
import os
import subprocess
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)

# ─── Caminhos do Piper (offline TTS para inglês) ──────────────────────────
BASE_DIR = Config.BASE_DIR
PIPER_EXEC = BASE_DIR / "piper" / "piper"
PIPER_VOICE_MODEL = BASE_DIR / "piper_voices" / "en_US-amy.onnx"
PIPER_VOICE_JSON = BASE_DIR / "piper_voices" / "en_US-amy.onnx.json"

# ─── Edge-TTS vozes (online, naturais) ────────────────────────────────────
# PT-BR: Vozes neutras recomendadas
EDGE_VOICE_PT = "pt-BR-AntonioNeural"      # Masculina, natural
EDGE_VOICE_PT_ALT = "pt-BR-FranciscaNeural" # Feminina, natural
# EN: fallback se Piper falhar
EDGE_VOICE_EN = "en-US-ChristopherNeural"   # Masculina, americana

# ─── Helpers ───────────────────────────────────────────────────────────────

def _check_piper():
    """Verifica se Piper está instalado e funcional."""
    if not os.path.exists(PIPER_EXEC):
        logger.warning(f"Piper não encontrado em {PIPER_EXEC}")
        return False
    if not os.access(PIPER_EXEC, os.X_OK):
        try:
            os.chmod(PIPER_EXEC, 0o755)
        except Exception:
            return False
    if not os.path.exists(PIPER_VOICE_MODEL):
        logger.warning(f"Modelo Piper não encontrado: {PIPER_VOICE_MODEL}")
        return False
    return True


def _generate_with_piper(text, output_path):
    """
    Gera áudio usando Piper TTS (offline, inglês).
    Roda em subprocesso — muito rápido (~0.15x real-time).
    """
    try:
        cmd = [
            str(PIPER_EXEC),
            "--model", str(PIPER_VOICE_MODEL),
            "--config", str(PIPER_VOICE_JSON),
            "--output_file", str(output_path),
        ]
        process = subprocess.run(
            cmd,
            input=text.encode('utf-8'),
            capture_output=True,
            timeout=120,
        )
        if process.returncode != 0:
            logger.error(f"Piper erro (código {process.returncode}): {process.stderr.decode().strip()}")
            return False
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"✅ Piper: {output_path.name} ({os.path.getsize(output_path)//1024}KB)")
            return True
        return False
    except subprocess.TimeoutExpired:
        logger.error("Piper timeout após 120s")
        return False
    except Exception as e:
        logger.error(f"Piper erro: {e}")
        return False


def _generate_with_edge_tts(text, output_path, voice):
    """
    Gera áudio usando Edge-TTS (online, vozes neurais naturais).
    Suporta PT-BR e EN com qualidade superior.
    """
    try:
        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))

        # Edge-tts precisa do módulo importado aqui (pode não estar na venv)
        import edge_tts
        asyncio.run(_run())

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"✅ Edge-TTS ({voice}): {output_path.name} ({os.path.getsize(output_path)//1024}KB)")
            return True
        return False
    except ImportError:
        logger.error("edge-tts não instalado. Instale com: pip install edge-tts")
        return False
    except Exception as e:
        logger.error(f"Edge-TTS erro ({voice}): {e}")
        return False


# ─── API pública ───────────────────────────────────────────────────────────

def generate_audio_file(text, filename, language='en'):
    """
    Gera áudio TTS.

    Args:
        text: Texto a ser falado (headlines curto)
        filename: Nome do arquivo (ex: 'feed_20260605.wav')
        language: 'pt' para português (edge-tts), 'en' para inglês (Piper)

    Returns:
        Caminho do arquivo .wav ou None em caso de erro
    """
    if not text:
        return None

    output_path = Config.AUDIO_DIR / filename
    # Garante extensão .wav
    if output_path.suffix.lower() not in ('.wav', '.mp3'):
        output_path = output_path.with_suffix('.wav')

    # Cache: se já existe, retorna
    if output_path.exists() and output_path.stat().st_size > 1000:
        logger.info(f"⏭️  Áudio em cache: {output_path.name}")
        return str(output_path)

    logger.info(f"🎙️  Gerando áudio ({language.upper()}): {output_path.name}...")

    # Decide qual engine usar baseado no idioma
    if language == 'pt':
        # PT → Edge-TTS (voz natural)
        logger.info(f"   Engine: Edge-TTS ({EDGE_VOICE_PT})")
        success = _generate_with_edge_tts(text, output_path, EDGE_VOICE_PT)
    else:
        # EN → Piper (offline, rápido)
        if _check_piper():
            logger.info("   Engine: Piper (offline)")
            success = _generate_with_piper(text, output_path)
        else:
            # Fallback: Edge-TTS em inglês
            logger.warning("   Piper indisponível, fallback para Edge-TTS (EN)")
            success = _generate_with_edge_tts(text, output_path, EDGE_VOICE_EN)

    if success:
        return str(output_path)
    else:
        logger.error(f"❌ Falha ao gerar áudio: {output_path.name}")
        return None
