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
PIPER_VOICE_MODEL = BASE_DIR / "piper_voices" / "en_US-amy-medium.onnx"
PIPER_VOICE_JSON = BASE_DIR / "piper_voices" / "en_US-amy-medium.onnx.json"
PIPER_VOICE_PT = BASE_DIR / "piper_voices" / "pt_BR-faber-medium.onnx"
PIPER_VOICE_PT_JSON = BASE_DIR / "piper_voices" / "pt_BR-faber-medium.onnx.json"
PIPER_VOICE_GB = BASE_DIR / "piper_voices" / "en_GB-aru-medium.onnx"
PIPER_VOICE_GB_JSON = BASE_DIR / "piper_voices" / "en_GB-aru-medium.onnx.json"

# ─── Edge-TTS vozes (online, naturais) ────────────────────────────────────
# PT-BR: Vozes neutras recomendadas
EDGE_VOICE_PT = "pt-BR-AntonioNeural"      # Masculina, natural
EDGE_VOICE_PT_ALT = "pt-BR-FranciscaNeural" # Feminina, natural
# EN: fallback se Piper falhar
EDGE_VOICE_EN = "en-US-ChristopherNeural"   # Masculina, americana

# ─── Helpers ───────────────────────────────────────────────────────────────

def _check_piper(model_path=None, config_path=None):
    """Verifica se Piper está instalado e funcional para um modelo específico."""
    if model_path is None:
        model_path = PIPER_VOICE_MODEL
    if config_path is None:
        config_path = PIPER_VOICE_JSON
    if not os.path.exists(PIPER_EXEC):
        return False
    if not os.access(PIPER_EXEC, os.X_OK):
        try:
            os.chmod(PIPER_EXEC, 0o755)
        except Exception:
            return False
    if not os.path.exists(model_path):
        return False
    return True


def _generate_with_piper(text, output_path, model_path=None, config_path=None):
    """
    Gera áudio usando Piper TTS (offline).
    Roda em subprocesso — muito rápido (~0.2x real-time).
    """
    if model_path is None:
        model_path = PIPER_VOICE_MODEL
    if config_path is None:
        config_path = PIPER_VOICE_JSON
    try:
        cmd = [
            str(PIPER_EXEC),
            "--model", str(model_path),
            "--config", str(config_path),
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

def generate_audio_file(text, filename, language='en', force=False):
    """
    Gera áudio TTS.

    Args:
        text: Texto a ser falado (headlines curto)
        filename: Nome do arquivo (ex: 'feed_20260605.wav')
        language: 'pt' para português, 'en' para inglês
        force: Se True, ignora cache e regenera sempre

    Returns:
        Caminho do arquivo .wav ou None em caso de erro
    """
    if not text:
        return None

    # Normaliza números e datas ANTES do TTS (voz mais natural)
    try:
        from .normalizer import normalize_pt, normalize_en
        if language == 'pt':
            text = normalize_pt(text)
        else:
            text = normalize_en(text)
    except ImportError:
        pass  # normalizer opcional, não quebra se ausente

    output_path = Config.AUDIO_DIR / filename
    # Garante extensão .wav
    if output_path.suffix.lower() not in ('.wav', '.mp3'):
        output_path = output_path.with_suffix('.wav')

    # Cache: se já existe, retorna (a menos que force=True)
    if not force and output_path.exists() and output_path.stat().st_size > 1000:
        logger.info(f"⏭️  Áudio em cache: {output_path.name}")
        return str(output_path)

    logger.info(f"🎙️  Gerando áudio ({language.upper()}): {output_path.name}...")

    # Decide qual engine usar baseado no idioma
    if language == 'pt':
        # PT → Piper offline (faber) primeiro, Edge-TTS fallback
        if _check_piper(PIPER_VOICE_PT, PIPER_VOICE_PT_JSON):
            logger.info("   Engine: Piper (offline, faber)")
            success = _generate_with_piper(text, output_path, PIPER_VOICE_PT, PIPER_VOICE_PT_JSON)
        else:
            logger.info(f"   Engine: Edge-TTS ({EDGE_VOICE_PT})")
            success = _generate_with_edge_tts(text, output_path, EDGE_VOICE_PT)
    elif language == 'gb':
        # GB → Piper offline (aru, RP britânico) primeiro
        if _check_piper(PIPER_VOICE_GB, PIPER_VOICE_GB_JSON):
            logger.info("   Engine: Piper (offline, aru GB)")
            success = _generate_with_piper(text, output_path, PIPER_VOICE_GB, PIPER_VOICE_GB_JSON)
        else:
            logger.warning("   Piper GB indisponível, fallback para Edge-TTS (EN)")
            success = _generate_with_edge_tts(text, output_path, EDGE_VOICE_EN)
    else:
        # EN → Piper offline (amy) primeiro, Edge-TTS fallback
        if _check_piper():
            logger.info("   Engine: Piper (offline, amy)")
            success = _generate_with_piper(text, output_path)
        else:
            logger.warning("   Piper indisponível, fallback para Edge-TTS (EN)")
            success = _generate_with_edge_tts(text, output_path, EDGE_VOICE_EN)

    if success:
        return str(output_path)
    else:
        logger.error(f"❌ Falha ao gerar áudio: {output_path.name}")
        return None
