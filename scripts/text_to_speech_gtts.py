import os
from TTS.api import TTS
from TTS.utils.manage import ModelManager
import json
import logging
import time

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

input_folder = '../data/'
audio_folder = os.path.join(input_folder, 'audio')
os.makedirs(audio_folder, exist_ok=True)

output_file = os.path.join(input_folder, 'feeds_folha_uol_com_br_news.json')

try:
    # Carrega o modelo de TTS
    logger.info("Carregando o modelo de TTS...")
    start_time = time.time()
    model_manager = ModelManager()
    TTS_MODEL = model_manager.list_models()[0]  # Obtém o primeiro modelo disponível
    logger.info(f"Usando o modelo de TTS: {TTS_MODEL}")

    if not TTS_MODEL:
        raise ValueError("Nenhum modelo TTS disponível. Verifique o caminho e a instalação do modelo.")

    tts = TTS(TTS_MODEL)
    logger.info(f"Modelo carregado em {time.time() - start_time:.2f} segundos.")

    # Verifica se o arquivo JSON existe
    if not os.path.exists(output_file):
        raise FileNotFoundError(f"Arquivo JSON não encontrado: {output_file}")

    # Carrega o JSON
    logger.info("Carregando o arquivo JSON...")
    with open(output_file, 'r', encoding='utf-8') as file:
        news_data = json.load(file)

    # Verifica se o JSON contém uma lista de notícias
    if isinstance(news_data, list):
        for i, article in enumerate(news_data):
            summary = article.get('summary', '')
            if summary:
                # Gera um arquivo de áudio para cada notícia
                output_audio = os.path.join(audio_folder, f'noticia_{i+1}.mp3')  # Usa MP3 para arquivos menores
                logger.info(f"Gerando áudio para a notícia {i+1}: {summary[:100]}...")  # Loga apenas os primeiros 100 caracteres

                # Gera o áudio
                start_time = time.time()
                tts.tts_to_file(
                    text=summary,
                    speaker="Gilberto Mathias",  # Verifique se o speaker é válido para o modelo
                    language=tts.languages[0],  # Usa o primeiro idioma suportado
                    file_path=output_audio
                )
                logger.info(f"Áudio gerado em {time.time() - start_time:.2f} segundos.")
                logger.info(f"Áudio salvo em {output_audio}")
            else:
                logger.warning(f"Artigo {i+1} não contém um resumo.")
    else:
        logger.error("O arquivo JSON não contém uma lista de notícias.")

except Exception as e:
    logger.error(f"Erro durante a execução do script: {e}", exc_info=True)