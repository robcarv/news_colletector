# bark_text_to_speech.py
import os
import json
import logging
from services.bark_service import generate_audio_with_bark
from services.telegram_service import send_to_telegram
from services.anchor_uploader import upload_to_anchor
from utils.text_processing import generate_valid_filename

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caminho da pasta de dados (relativo ao local do script)
script_dir = os.path.dirname(os.path.abspath(__file__))
input_folder = os.path.join(script_dir, '../data')
audio_folder = os.path.join(input_folder, 'audio')

# Cria a pasta de áudio se não existir
os.makedirs(audio_folder, exist_ok=True)

def generate_audio_for_article_with_bark(title, summary, source, audio_folder):
    """
    Gera um arquivo de áudio a partir do título, resumo e fonte da notícia usando o Bark.
    :param title: Título da notícia.
    :param summary: Resumo da notícia.
    :param source: Fonte da notícia.
    :param audio_folder: Pasta onde o áudio será salvo.
    :return: Caminho do arquivo de áudio gerado.
    """
    try:
        # Combina título, resumo e fonte em um único texto
        combined_text = f"{title}\n\n{summary}\n\nFonte: {source}"

        # Gera um nome de arquivo válido a partir do título
        valid_filename = generate_valid_filename(title)
        audio_path = os.path.join(audio_folder, f'{valid_filename}_bark.wav')

        # Gera o áudio com o Bark
        generate_audio_with_bark(combined_text, audio_path)

        logger.info(f"🔊 Áudio gerado com Bark e salvo em: {audio_path}")
        return audio_path
    except Exception as e:
        logger.error(f"❌ Erro ao gerar áudio com Bark para a notícia: {e}")
        return None

def compile_audio_for_feed_with_bark(news_data, feed_name, audio_folder):
    """
    Compila os títulos das notícias em um único áudio usando o Bark.
    :param news_data: Lista de notícias.
    :param feed_name: Nome do feed.
    :param audio_folder: Pasta onde o áudio será salvo.
    :return: Caminho do arquivo de áudio gerado.
    """
    try:
        # Concatena os títulos das notícias em um único texto
        combined_titles = ""
        for article in news_data:
            title = article.get('title', '')
            if title:
                processed_text = preprocess_text(title)
                combined_titles += processed_text + "\n\n"

        if combined_titles:
            # Gera o arquivo de áudio
            valid_filename = generate_valid_filename(f"{feed_name}_bark")
            output_audio = os.path.join(audio_folder, f'{valid_filename}.wav')
            logger.info(f"🔊 Gerando áudio com Bark para o feed: {feed_name}...")

            # Gera o áudio com o Bark
            generate_audio_with_bark(combined_titles, output_audio)

            logger.info(f"🔊 Áudio com Bark salvo em {output_audio}")
            return output_audio
        else:
            logger.warning(f"⚠️ Nenhum título encontrado para o feed: {feed_name}")
            return None
    except Exception as e:
        logger.error(f"❌ Erro ao compilar áudio com Bark para o feed {feed_name}: {e}")
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
                    # Gera o áudio com o Bark
                    audio_path = generate_audio_for_article_with_bark(title, summary, source, audio_folder)

                    if audio_path:
                        # Adiciona o caminho do áudio à lista
                        audio_files.append(audio_path)

                        # Envia a notícia e o áudio para o Telegram
                        logger.info(f"📤 Enviando notícia {i+1} para o Telegram...")
                        send_to_telegram(title, summary, source, source_link, audio_path)

            # Compila todos os áudios do feed em um único arquivo
            compiled_audio_path = compile_audio_for_feed_with_bark(news_data, feed_name, audio_folder)

            # Faz o upload do áudio compilado para o Anchor
            if compiled_audio_path:
                logger.info(f"📤 Enviando áudio compilado para o Anchor: {feed_name}...")
                upload_to_anchor(compiled_audio_path, f"{feed_name}_bark")
            else:
                logger.warning(f"⚠️ Nenhum áudio compilado gerado para o feed: {feed_name}")

    except Exception as e:
        logger.error(f"❌ Erro durante a execução do script: {e}", exc_info=True)

if __name__ == "__main__":
    main()