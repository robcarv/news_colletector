# text_to_speech.py
import os
import json
import logging
import time
from utils.text_processing import remove_html_tags, preprocess_text, generate_valid_filename
from services.telegram_service import send_to_telegram
from services.tts_service import generate_audio

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caminho da pasta de dados (relativo ao local do script)
script_dir = os.path.dirname(os.path.abspath(__file__))  # Pasta onde o script está
input_folder = os.path.join(script_dir, 'data')          # Pasta data (no mesmo nível do script)
audio_folder = os.path.join(input_folder, 'audio')      # Pasta audio dentro de data

# Cria a pasta de áudio se não existir
os.makedirs(audio_folder, exist_ok=True)

def detect_language_and_speaker(source_link):
    """
    Detecta o idioma e o falante com base no link da fonte.
    :param source_link: Link da fonte da notícia.
    :return: Idioma e falante.
    """
    if "nytimes.com" in source_link or "bbc.co.uk" in source_link:
        return "en", "en_0"  # Inglês
    else:
        return "pt", "Sofia Hellen"  # Português

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
                data = json.load(file)

            # Verifica se o JSON contém a estrutura esperada
            if isinstance(data, dict) and "news" in data:
                language = data.get("language", "pt")  # Idioma padrão é português
                news_data = data.get("news", [])

                for i, article in enumerate(news_data):
                    title = article.get('title', '')
                    summary = article.get('summary', '')
                    source = article.get('source', '')
                    source_link = article.get('link', '#')  # Obtém o link da fonte

                    if summary:
                        # Remove tags HTML e pré-processa o texto
                        summary = remove_html_tags(summary)
                        processed_text = preprocess_text(summary)
                        logger.info(f"🔧 Texto pré-processado: {processed_text[:100]}...")

                        # Detecta o idioma e o falante com base na fonte
                        detected_language, speaker = detect_language_and_speaker(source_link)

                        # Gera um arquivo de áudio para cada notícia
                        valid_filename = generate_valid_filename(title)
                        output_audio = os.path.join(audio_folder, f'{valid_filename}.mp3')
                        logger.info(f"🔊 Gerando áudio para a notícia {i+1}...")

                        # Gera o áudio com o idioma e falante corretos
                        generate_audio(summary, output_audio, speaker=speaker, language=detected_language)

                        # Envia a notícia e o áudio para o Telegram
                        logger.info(f"📤 Enviando notícia {i+1} para o Telegram...")
                        send_to_telegram(title, summary, source, source_link, output_audio)

                        # Adiciona um timeout de 5 segundos
                        logger.info("⏳ Aguardando 5 segundos antes da próxima geração...")
                        time.sleep(5)
                    else:
                        logger.warning(f"⚠️ Artigo {i+1} não contém um resumo.")
            else:
                logger.error(f"❌ O arquivo JSON {json_file} não contém a estrutura esperada.")
    except Exception as e:
        logger.error(f"❌ Erro durante a execução do script: {e}", exc_info=True)

if __name__ == "__main__":
    main()