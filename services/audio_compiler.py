# services/audio_compiler.py
import os
import logging
from datetime import datetime
import pytz  # Para trabalhar com fusos horários
from services.tts_service import generate_audio
from utils.text_processing import remove_html_tags, preprocess_text, generate_valid_filename

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fuso horário do Brasil
brazil_tz = pytz.timezone('America/Sao_Paulo')

def compile_audio_for_feed(news_data, feed_name, audio_folder):
    """
    Compila os resumos das notícias em um único áudio.
    :param news_data: Lista de notícias.
    :param feed_name: Nome do feed.
    :param audio_folder: Pasta onde o áudio será salvo.
    :return: Caminho do arquivo de áudio gerado.
    """
    try:
        # Concatena os resumos das notícias em um único texto
        combined_summary = ""
        for article in news_data:
            summary = article.get('summary', '')
            if summary:
                summary = remove_html_tags(summary)
                processed_text = preprocess_text(summary)
                combined_summary += processed_text + "\n\n"

        if combined_summary:
            # Data e horário atual no fuso horário do Brasil
            now = datetime.now(brazil_tz)
            date_time_str = now.strftime("%d %b %H:%M")  # Formato: 22 Set 16:00

            # Nome do episódio
            episode_title = f"{feed_name} {date_time_str}"

            # Gera o arquivo de áudio
            valid_filename = generate_valid_filename(episode_title)
            output_audio = os.path.join(audio_folder, f'{valid_filename}.mp3')
            logger.info(f"🔊 Gerando áudio para o feed: {feed_name}...")

            # Detecta o idioma e o falante com base no feed
            language, speaker = "pt", "Sofia Hellen"  # Padrão para português
            if "pitchfork.com" in news_data[0].get('link', '') or "bbc.co.uk" in news_data[0].get('link', '') or"bbci.co.uk" in news_data[0].get('link', '') :
                language, speaker = "en", "Claribel Dervla"  # Inglês

            # Gera o áudio com o idioma e falante corretos
            generate_audio(combined_summary, output_audio, speaker=speaker, language=language)

            logger.info(f"🔊 Áudio salvo em {output_audio}")
            return output_audio
        else:
            logger.warning(f"⚠️ Nenhum resumo encontrado para o feed: {feed_name}")
            return None
    except Exception as e:
        logger.error(f"❌ Erro ao compilar áudio para o feed {feed_name}: {e}")
        return None