# services/tts_service.py
from TTS.api import TTS
import logging
import gc
import time
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações de segurança para Raspberry Pi
MAX_TEXT_LENGTH = 500  # Limita o tamanho do texto para TTS
MIN_MEMORY_AVAILABLE = 100  # MB mínimos disponíveis para operar

def check_memory():
    """Verifica memória disponível (em MB)"""
    with open('/proc/meminfo', 'r') as f:
        mem = f.read()
        return int(mem.split('MemAvailable:')[1].split()[0]) // 1024

def generate_audio(text, output_audio_path, speaker="Sofia Hellen", language="pt"):
    """Versão otimizada para Raspberry Pi"""
    try:
        # Limita o tamanho do texto
        text = text[:MAX_TEXT_LENGTH]
        
        # Verifica memória antes de prosseguir
        if check_memory() < MIN_MEMORY_AVAILABLE:
            logger.warning("⚠️ Memória insuficiente - aguardando...")
            time.sleep(30)
            if check_memory() < MIN_MEMORY_AVAILABLE:
                raise MemoryError("Memória insuficiente após espera")

        logger.info("🔧 Carregando modelo TTS (modo econômico)...")
        
        # Configuração mínima para o modelo
        tts = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            progress_bar=False,
            gpu=False
        )
        
        # Gera áudio em chunks se necessário
        if len(text) > 200:
            chunks = [text[i:i+200] for i in range(0, len(text), 200)]
            temp_files = []
            for i, chunk in enumerate(chunks):
                temp_path = f"{output_audio_path}_part{i}.wav"
                tts.tts_to_file(
                    text=chunk,
                    speaker=speaker,
                    language=language,
                    file_path=temp_path
                )
                temp_files.append(temp_path)
                time.sleep(1)  # Pausa entre chunks
            
            # Combina os arquivos (requer sox instalado)
            os.system(f"sox {' '.join(temp_files)} {output_audio_path}")
            for f in temp_files:
                os.remove(f)
        else:
            tts.tts_to_file(
                text=text,
                speaker=speaker,
                language=language,
                file_path=output_audio_path
            )
        
        logger.info(f"✅ Áudio gerado em {output_audio_path}")
        
    except Exception as e:
        logger.error(f"❌ Falha ao gerar áudio: {str(e)}")
        raise  # Re-lança a exceção para tratamento superior
    finally:
        # Limpeza agressiva
        if 'tts' in locals():
            del tts
        gc.collect()
        time.sleep(1)  # Pausa para liberação de recursos