import os
from TTS.api import TTS
import json
import logging
import gc  # Módulo para coleta de lixo (garbage collection)

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

input_folder = '../data/'
audio_folder = os.path.join(input_folder, 'audio')
os.makedirs(audio_folder, exist_ok=True)

output_file = os.path.join(input_folder, 'feeds_folha_uol_com_br_news.json')

try:
    # Carrega o modelo de TTS (XTTS multilíngue)
    logger.info("🔧 Carregando o modelo de TTS...")
    tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
    # tts = TTS(model_name="tts_models/pt/cv/vits")
    logger.info("✅ Modelo carregado com sucesso.")

    # Verifica se o arquivo JSON existe
    if not os.path.exists(output_file):
        raise FileNotFoundError(f"❌ Arquivo JSON não encontrado: {output_file}")

    # Carrega o JSON
    logger.info("📂 Carregando o arquivo JSON...")
    with open(output_file, 'r', encoding='utf-8') as file:
        news_data = json.load(file)

    # Verifica se o JSON contém uma lista de notícias
    if isinstance(news_data, list):
        for i, article in enumerate(news_data):
            summary = article.get('summary', '')
            if summary:
                # Gera um arquivo de áudio para cada notícia
                output_audio = os.path.join(audio_folder, f'noticia_{i+1}.mp3')
                logger.info(f"🔊 Gerando áudio para a notícia {i+1}...")

                # Gera o áudio com uma voz em pt-BR
                tts.tts_to_file(
                    text=summary,
                    speaker="Sofia Hellen",  # Voz em pt-BR
                    language="pt",               # Idioma: português
                    file_path=output_audio
                )
                logger.info(f"🔊 Áudio salvo em {output_audio}")

                # Limpa o cache e libera memória
                logger.info("🧹 Limpando cache e liberando memória...")
                del tts  # Remove o objeto TTS da memória
                gc.collect()  # Força a coleta de lixo

                # Recarrega o modelo para o próximo áudio
                tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
                # tts = TTS(model_name="tts_models/pt/cv/vits")
            else:
                logger.warning(f"⚠️ Artigo {i+1} não contém um resumo.")
    else:
        logger.error("❌ O arquivo JSON não contém uma lista de notícias.")

except Exception as e:
    logger.error(f"❌ Erro durante a execução do script: {e}", exc_info=True)