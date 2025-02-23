# text_to_speech_pt.py
import os
import json
import logging
from services.audio_generator import generate_audio_for_article, compile_audio_for_feed, cleanup_and_wait
from services.telegram_service import send_to_telegram
from pydub import AudioSegment

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caminho da pasta de dados (relativo ao local do script)
script_dir = os.path.dirname(os.path.abspath(__file__))
input_folder = os.path.join(script_dir, './data')
audio_folder = os.path.join(input_folder, 'audio')

# Cria a pasta de áudio se não existir
os.makedirs(audio_folder, exist_ok=True)

def main():
    try:
        # Lista de arquivos JSON na pasta de dados
        json_files = [f for f in os.listdir(input_folder) if f.endswith('.json')]

        if not json_files:
            raise FileNotFoundError(f"❌ Nenhum arquivo JSON encontrado em: {input_folder}")

        # Processa cada arquivo JSON
        for json_file in json_files:
            json_path = os.path.join(input_folder, json_file)
            logger.info(f"📂 Carregando o arquivo JSON: {json_file}")

            # Carrega o JSON
            with open(json_path, 'r', encoding='utf-8') as file:
                json_data = json.load(file)

            # Verifica se o JSON contém a chave "news" e se é uma lista
            if isinstance(json_data, dict) and "news" in json_data and isinstance(json_data["news"], list):
                news_data = json_data["news"]  # Extrai a lista de notícias
                language = json_data.get("language", "pt")  # Obtém o idioma do JSON
            else:
                logger.error(f"❌ O arquivo JSON {json_file} não contém uma lista de notícias na chave 'news'.")
                continue

            # Nome do feed (extraído do nome do arquivo JSON)
            feed_name = json_file.replace("_news.json", "").replace("_", " ").title()

            # Lista para armazenar os caminhos dos áudios gerados
            audio_files = []

            # Envia as notícias individuais para o Telegram
            for i, article in enumerate(news_data):
                title = article.get('title', '')
                summary = article.get('summary', '')
                source = article.get('source', '')
                source_link = article.get('link', '#')

                if title and summary:
                    # Gera o áudio para a notícia em português
                    audio_path = generate_audio_for_article(title, summary, source, audio_folder, language=language)

                    if audio_path:
                        # Adiciona o caminho do áudio à lista
                        audio_files.append(audio_path)

                        # Envia a notícia e o áudio para o Telegram
                        logger.info(f"📤 Enviando notícia {i+1} para o Telegram...")
                        send_to_telegram(title, summary, source, source_link, audio_path)

                        # Limpa o cache e espera 5 segundos
                        cleanup_and_wait()

            # Compila todos os áudios do feed em um único arquivo
            compiled_audio_path = compile_audio_for_feed(news_data, feed_name, audio_folder, language=language)

            # Faz o upload do áudio compilado para o Anchor
            # if compiled_audio_path:
            #     logger.info(f"📤 Enviando áudio compilado para o Anchor: {feed_name}...")
            #     # upload_to_anchor(compiled_audio_path, feed_name)
            # else:
            #     logger.warning(f"⚠️ Nenhum áudio compilado gerado para o feed: {feed_name}")

    except Exception as e:
        logger.error(f"❌ Erro durante a execução do script: {e}", exc_info=True)

if __name__ == "__main__":
    main()