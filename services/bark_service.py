# services/bark_service.py
import os
import logging
import gc
from bark import SAMPLE_RATE, generate_audio, preload_models
from scipy.io.wavfile import write as write_wav
import numpy as np

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pré-carrega os modelos do Bark
preload_models()

def generate_audio_with_bark(text, output_audio_path):
    """
    Gera um arquivo de áudio a partir de um texto usando o Bark.
    :param text: Texto a ser convertido em áudio.
    :param output_audio_path: Caminho onde o arquivo de áudio será salvo.
    """
    try:
        logger.info("🔧 Gerando áudio com o Bark...")

        # Gera o áudio usando o Bark
        audio_array = generate_audio(text)

        # Salva o áudio em um arquivo WAV
        write_wav(output_audio_path, SAMPLE_RATE, audio_array)

        logger.info(f"🔊 Áudio gerado e salvo em {output_audio_path}")

        # Limpa o cache e libera memória
        gc.collect()
    except Exception as e:
        logger.error(f"❌ Erro ao gerar áudio com o Bark: {e}")