# services/tts_service.py
from TTS.api import TTS
import logging
import gc

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_audio(text, output_audio_path, speaker="Sofia Hellen", language="pt"):
    """
    Gera um arquivo de áudio a partir de um texto usando TTS.
    :param text: Texto a ser convertido em áudio.
    :param output_audio_path: Caminho onde o arquivo de áudio será salvo.
    :param speaker: Nome do falante (voz) a ser usado.
    :param language: Idioma do texto (pt para português, en para inglês).
    """
    try:
        logger.info("🔧 Carregando o modelo de TTS...")
        tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
        logger.info("✅ Modelo carregado com sucesso.")

        # Verifica se o idioma e o falante são suportados
        supported_languages = ["pt", "en"]
        if language not in supported_languages:
            logger.warning(f"⚠️ Idioma '{language}' não suportado. Usando 'pt' como padrão.")
            language = "pt"

        # Gera o áudio
        tts.tts_to_file(
            text=text,
            speaker=speaker,
            language=language,
            file_path=output_audio_path
        )
        logger.info(f"🔊 Áudio salvo em {output_audio_path}")

        # Limpa o cache e libera memória
        del tts
        gc.collect()
    except Exception as e:
        logger.error(f"❌ Erro ao gerar áudio: {e}")