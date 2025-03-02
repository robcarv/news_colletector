import os
import logging
import time
import gc
from datetime import datetime
import pytz
from services.tts_service import generate_audio
from utils.text_processing import remove_html_tags, preprocess_text, generate_valid_filename

# Configuração de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Fuso horário do Brasil
brazil_tz = pytz.timezone('America/Sao_Paulo')

# Mapeamento de idiomas para speakers padrão
DEFAULT_SPEAKERS = {
    "pt": "Sofia Hellen",  # Português
    "en": "Gitta Nikolina",  # Inglês
    "es": "Ana Florence",  # Espanhol
    "fr": "Brenda Stern",  # Francês
    "de": "Gitta Nikolina",  # Alemão
    "it": "Henriette Usha",  # Italiano
}

# Contador global para contar execuções do cleanup_and_wait
cleanup_counter = 0

def get_speaker_for_language(language):
    """
    Retorna o speaker padrão para o idioma especificado.
    :param language: Idioma (ex: "pt", "en", "es").
    :return: Nome do speaker.
    """
    return DEFAULT_SPEAKERS.get(language, DEFAULT_SPEAKERS["pt"])  # Usa "pt" como fallback

def generate_audio_for_article(title, summary, source, audio_folder, language="pt"):
    """
    Gera um arquivo de áudio a partir do título, resumo e fonte da notícia.
    :param title: Título da notícia.
    :param summary: Resumo da notícia.
    :param source: Fonte da notícia.
    :param audio_folder: Pasta onde o áudio será salvo.
    :param language: Idioma para a geração do áudio (ex: "pt", "en").
    :return: Caminho do arquivo de áudio gerado.
    """
    try:
        # Combina título, resumo e fonte em um único texto
        combined_text = f"{title}\n\n{summary}\n\nFonte: {source}"

        # Gera um nome de arquivo válido a partir do título
        valid_filename = generate_valid_filename(title)
        audio_path = os.path.join(audio_folder, f'{valid_filename}.mp3')

        # Obtém o speaker padrão para o idioma
        speaker = get_speaker_for_language(language)

        # Gera o áudio
        generate_audio(combined_text, audio_path, speaker=speaker, language=language)

        logger.info(f"🔊 Áudio gerado e salvo em: {audio_path}")
        return audio_path
    except Exception as e:
        logger.error(f"❌ Erro ao gerar áudio para a notícia: {e}")
        return None

def compile_audio_for_feed(news_data, feed_name, audio_folder, language="pt"):
    """
    Compila os títulos das notícias em um único áudio.
    :param news_data: Lista de notícias.
    :param feed_name: Nome do feed.
    :param audio_folder: Pasta onde o áudio será salvo.
    :param language: Idioma para a geração do áudio (ex: "pt", "en").
    :return: Caminho do arquivo de áudio gerado.
    """
    try:
        # Concatena os títulos das notícias em um único texto
        combined_titles = ""
        for article in news_data:
            title = article.get('title', '')
            if title:
                title = remove_html_tags(title)
                processed_text = preprocess_text(title)
                combined_titles += processed_text + "\n\n"

        if combined_titles:
            # Data e horário atual no fuso horário do Brasil
            now = datetime.now(brazil_tz)
            date_time_str = now.strftime("%d %b %H:%M")  # Formato: 22 Set 16:00

            # Nome do episódio
            episode_title = f"{feed_name} {date_time_str}"

            # Gera o arquivo de áudio
            valid_filename = generate_valid_filename(episode_title)
            output_audio = os.path.join(audio_folder, f'{valid_filename}.mp3')
            logger.info(f"🔊 Gerando áudio para o feed: {feed_name}...")

            # Obtém o speaker padrão para o idioma
            speaker = get_speaker_for_language(language)

            # Gera o áudio com o idioma e falante corretos
            generate_audio(combined_titles, output_audio, speaker=speaker, language=language)

            logger.info(f"🔊 Áudio salvo em {output_audio}")
            return output_audio
        else:
            logger.warning(f"⚠️ Nenhum título encontrado para o feed: {feed_name}")
            return None
    except Exception as e:
        logger.error(f"❌ Erro ao compilar áudio para o feed {feed_name}: {e}")
        return None

def cleanup_and_wait():
    """
    Limpa o cache e espera um tempo para evitar sobrecarga no Raspberry Pi.
    """
    global cleanup_counter
    try:
        cleanup_counter += 1  # Incrementa o contador
        start_time = time.time()  # Marca o início
        logger.info(f"🟢 Iniciando cleanup_and_wait() (execução {cleanup_counter})...")
        
        # Limpa o cache e libera memória
        gc.collect()
        logger.info("🧹 Cache limpo e memória liberada.")

        # Adiciona um timeout de 5 segundos
        logger.info("⏳ Aguardando 5 segundos antes da próxima geração...")
        time.sleep(5)

        end_time = time.time()  # Marca o fim
        logger.info(f"🔴 cleanup_and_wait() concluído em {end_time - start_time:.2f} segundos.")
    except Exception as e:
        logger.error(f"❌ Erro ao limpar cache ou esperar: {e}")