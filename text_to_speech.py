# text_to_speech.py
import os
import json
import logging
import time
from datetime import datetime
import pytz  # Para trabalhar com fusos horários
from services.audio_generator import generate_audio_for_article, compile_audio_for_feed, cleanup_and_wait
from services.telegram_service import send_to_telegram
from services.anchor_uploader import upload_to_anchor
from pydub import AudioSegment  # Para compilar áudios

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caminho da pasta de dados (relativo ao local do script)
script_dir = os.path.dirname(os.path.abspath(__file__))  # Pasta onde o script está
input_folder = os.path.join(script_dir, './data')      # Pasta data (um nível acima)
audio_folder = os.path.join(input_folder, 'audio')      # Pasta audio dentro de data

# Cria a pasta de áudio se não existir
os.makedirs(audio_folder, exist_ok=True)

# Fuso horário do Brasil
brazil_tz = pytz.timezone('America/Sao_Paulo')

def detect_language(source_link):
    """
    Detecta o idioma com base no link da fonte.
    :param source_link: Link da fonte da notícia.
    :return: Idioma ("pt" ou "en").
    """
    if "nytimes.com" in source_link or "ibm.com" in source_link:
        return "en"  # Inglês
    else:
        return "pt"  # Português

def compile_all_audios(audio_files, feed_name, audio_folder):
    """
    Compila todos os áudios de um feed em um único arquivo de áudio.
    :param audio_files: Lista de caminhos dos arquivos de áudio.
    :param feed_name: Nome do feed.
    :param audio_folder: Pasta onde o áudio compilado será salvo.
    :return: Caminho do arquivo de áudio compilado.
    """
    try:
        if not audio_files:
            logger.warning(f"⚠️ Nenhum áudio encontrado para compilar no feed: {feed_name}")
            return None

        # Cria um objeto de áudio vazio
        compiled_audio = AudioSegment.silent(duration=1000)  # 1 segundo de silêncio inicial

        # Concatena todos os áudios
        for audio_file in audio_files:
            if os.path.exists(audio_file):
                audio = AudioSegment.from_file(audio_file)
                compiled_audio += audio
                compiled_audio += AudioSegment.silent(duration=1000)  # 1 segundo de silêncio entre áudios
            else:
                logger.warning(f"⚠️ Arquivo de áudio não encontrado: {audio_file}")

        # Gera o nome do arquivo compilado
        now = datetime.now(brazil_tz)
        date_time_str = now.strftime("%d %b %H:%M")  # Formato: 22 Set 16:00
        compiled_filename = f"{feed_name}_compilado_{date_time_str}.mp3"
        compiled_audio_path = os.path.join(audio_folder, compiled_filename)

        # Salva o áudio compilado
        compiled_audio.export(compiled_audio_path, format="mp3")
        logger.info(f"🔊 Áudio compilado salvo em: {compiled_audio_path}")

        return compiled_audio_path
    except Exception as e:
        logger.error(f"❌ Erro ao compilar áudios: {e}")
        return None

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
                    # Detecta o idioma
                    language = detect_language(source_link)

                    # Gera o áudio para a notícia
                    audio_path = generate_audio_for_article(title, summary, source, audio_folder, language)

                    if audio_path:
                        # Adiciona o caminho do áudio à lista
                        audio_files.append(audio_path)

                        # Envia a notícia e o áudio para o Telegram
                        logger.info(f"📤 Enviando notícia {i+1} para o Telegram...")
                        send_to_telegram(title, summary, source, source_link, audio_path)

                        # Limpa o cache e espera 5 segundos
                        cleanup_and_wait()

            # Compila todos os áudios do feed em um único arquivo
            compiled_audio_path = compile_all_audios(audio_files, feed_name, audio_folder)

            # Faz o upload do áudio compilado para o Anchor
            if compiled_audio_path:
                logger.info(f"📤 Enviando áudio compilado para o Anchor: {feed_name}...")
                # upload_to_anchor(compiled_audio_path, feed_name)
            else:
                logger.warning(f"⚠️ Nenhum áudio compilado gerado para o feed: {feed_name}")

    except Exception as e:
        logger.error(f"❌ Erro durante a execução do script: {e}", exc_info=True)

if __name__ == "__main__":
    main()