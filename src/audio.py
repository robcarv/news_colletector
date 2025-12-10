import logging
import os
import subprocess
from .config import Config # Importa Config para acesso a BASE_DIR e AUDIO_DIR
from pathlib import Path

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÕES DO PIPER (VOZ AMY - INGLÊS) ---
# Os caminhos são construídos a partir da raiz do projeto, garantindo que o cron funcione.
BASE_DIR = Config.BASE_DIR
PIPER_EXEC = BASE_DIR / "piper" / "piper"
VOICE_MODEL = BASE_DIR / "piper_voices" / "en_US-amy.onnx"
VOICE_JSON = BASE_DIR / "piper_voices" / "en_US-amy.onnx.json"

def check_piper_setup():
    """Verifica se os arquivos do Piper estão no lugar e com permissão."""
    # 1. Verifica binário
    if not os.path.exists(PIPER_EXEC):
        logger.error(f"❌ Erro Piper: Executável não encontrado em {PIPER_EXEC}")
        return False
    # 2. Garante permissão de execução
    if not os.access(PIPER_EXEC, os.X_OK):
        try:
            os.chmod(PIPER_EXEC, 0o755)
            logger.warning(f"⚠️ Permissão de execução concedida a {PIPER_EXEC}")
        except Exception as e:
            logger.error(f"❌ Falha ao dar permissão a Piper: {e}")
            return False
    # 3. Verifica modelo de voz
    if not os.path.exists(VOICE_MODEL) or not os.path.exists(VOICE_JSON):
        logger.error("❌ Erro Piper: Arquivo de voz (.onnx ou .json) não encontrado.")
        return False
    return True

def generate_audio_file(text, filename, language='pt'):
    """
    Gera áudio NEURAL OFFLINE usando Piper TTS.
    O formato de saída é .wav (aceito pelo Telegram).
    """
    if not text:
        return None
    
    # 1. Verifica se a instalação está OK
    if not check_piper_setup():
        return None

    # 2. Define o caminho de saída (.mp3 é trocado por .wav)
    output_wav = str(Config.AUDIO_DIR / filename).replace(".mp3", ".wav")
    
    # Cache (evita reprocessar)
    if os.path.exists(output_wav) and os.path.getsize(output_wav) > 1000:
        logger.info(f"⏭️ Áudio em cache: {Path(output_wav).name}")
        return output_wav

    logger.info(f"🎙️ Gerando Piper (Offline, {language.upper()}): {Path(output_wav).name}...")
    
    try:
        # Comando de execução: passa o texto via stdin para maior segurança
        cmd = [
            str(PIPER_EXEC),
            "--model", str(VOICE_MODEL),
            "--config", str(VOICE_JSON),
            "--output_file", output_wav,
        ]
        
        process = subprocess.run(
            cmd,
            input=text.encode('utf-8'), # Envia o texto como input (codificado)
            capture_output=True,
            check=True
        )
        
        # O Piper gera alguns warnings, mas um erro crítico é no stderr
        if process.stderr:
             logger.warning(f"⚠️ Warnings/Erros Piper: {process.stderr.decode().strip()}")

        # 3. Verificação Final
        if os.path.exists(output_wav) and os.path.getsize(output_wav) > 0:
            logger.info(f"✅ Áudio salvo: {output_wav}")
            return output_wav
        else:
            # Se o arquivo não foi criado
            logger.error("❌ Piper gerou arquivo vazio ou falhou silenciosamente.")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Erro de execução no Piper (Código {e.returncode}): {e.stderr.decode().strip()}")
        return None
    except Exception as e:
        logger.error(f"❌ Erro geral Piper: {e}")
        return None