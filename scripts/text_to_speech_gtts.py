import os
from TTS.api import TTS
import json
import logging
import gc
import time
import re
import requests
from dotenv import load_dotenv

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Constantes para o Telegram (carregadas do .env)
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Token do bot do Telegram
CHAT_ID = os.getenv('CHAT_ID')  # ID do chat do Telegram

# Função para remover tags HTML
def remove_html_tags(text):
    """
    Remove todas as tags HTML de um texto.
    
    :param text: Texto contendo tags HTML
    :return: Texto sem tags HTML
    """
    clean = re.compile(r'<.*?>')
    return re.sub(clean, '', text)

# Função para limpar caracteres problemáticos
def clean_text(text):
    """
    Remove caracteres que podem causar problemas na formatação Markdown do Telegram.
    
    :param text: Texto a ser limpo
    :return: Texto limpo
    """
    # Remove caracteres especiais que podem interferir na formatação Markdown
    text = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)
    return text

# Função para enviar mensagem formatada para o Telegram
def send_to_telegram(title, summary, source, audio_path):
    """
    Envia uma mensagem formatada para o Telegram com o título, resumo, fonte e áudio da notícia.
    
    :param title: Título da notícia
    :param summary: Resumo da notícia
    :param source: Fonte da notícia
    :param audio_path: Caminho do arquivo de áudio
    """
    try:
        # Remove tags HTML e limpa o texto
        title = remove_html_tags(title)
        summary = remove_html_tags(summary)
        source = remove_html_tags(source)

        # Limpa caracteres problemáticos
        title = clean_text(title)
        summary = clean_text(summary)
        source = clean_text(source)

        # Formata a mensagem
        message = (
            f"📰 *{title}*\n\n"
            f"🔍 *Resumo:* {summary}\n\n"
            f"📌 *Fonte:* {source}\n\n"
            f"🎧 Ouça o áudio abaixo:"
        )

        # Envia a mensagem de texto
        url_text = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'  # Usa Markdown para formatação
        }
        response_text = requests.post(url_text, data=payload)
        if response_text.status_code != 200:
            logger.error(f"❌ Erro ao enviar mensagem de texto para o Telegram: {response_text.text}")
            return

        # Envia o áudio
        url_audio = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"
        with open(audio_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            data = {'chat_id': CHAT_ID}
            response_audio = requests.post(url_audio, files=files, data=data)
            if response_audio.status_code != 200:
                logger.error(f"❌ Erro ao enviar áudio para o Telegram: {response_audio.text}")
            else:
                logger.info(f"✅ Áudio e mensagem enviados com sucesso para o Telegram.")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar mensagem ou áudio para o Telegram: {e}")

# Função de pré-processamento
def preprocess_text(text):
    # Remove pontuações desnecessárias
    text = re.sub(r'[.,;:!?]+', ' ', text)  # Substitui pontuações por espaços

    # Formata endereços web
    text = re.sub(r'(\b\w+\.com\b)', lambda x: x.group(1).replace('.', ' ponto '), text)
    text = re.sub(r'(\b\w+\.org\b)', lambda x: x.group(1).replace('.', ' ponto '), text)
    text = re.sub(r'(\b\w+\.net\b)', lambda x: x.group(1).replace('.', ' ponto '), text)

    # Remove espaços extras
    text = re.sub(r'\s+', ' ', text).strip()

    return text

input_folder = '../data/'
audio_folder = os.path.join(input_folder, 'audio')
os.makedirs(audio_folder, exist_ok=True)

output_file = os.path.join(input_folder, 'feeds_folha_uol_com_br_news.json')

try:
    # Carrega o modelo de TTS específico para português
    logger.info("🔧 Carregando o modelo de TTS...")
    tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
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
            title = article.get('title', '')
            summary = article.get('summary', '')
            source = article.get('source', '')
            if summary:
                # Remove tags HTML e pré-processa o texto
                summary = remove_html_tags(summary)
                processed_text = preprocess_text(summary)
                logger.info(f"🔧 Texto pré-processado: {processed_text[:100]}...")  # Loga os primeiros 100 caracteres

                # Gera um arquivo de áudio para cada notícia
                output_audio = os.path.join(audio_folder, f'noticia_{i+1}.mp3')
                logger.info(f"🔊 Gerando áudio para a notícia {i+1}...")

                # Gera o áudio com o modelo em português
                tts.tts_to_file(
                    text=summary,
                    speaker="Sofia Hellen",  # Voz em pt-BR
                    language="pt",           # Idioma: português
                    file_path=output_audio
                )
                logger.info(f"🔊 Áudio salvo em {output_audio}")

                # Envia a notícia e o áudio para o Telegram
                logger.info(f"📤 Enviando notícia {i+1} para o Telegram...")
                send_to_telegram(title, summary, source, output_audio)

                # Limpa o cache e libera memória
                logger.info("🧹 Limpando cache e liberando memória...")
                del tts  # Remove o objeto TTS da memória
                gc.collect()  # Força a coleta de lixo

                # Adiciona um timeout de 5 segundos
                logger.info("⏳ Aguardando 5 segundos antes da próxima geração...")
                time.sleep(5)

                # Recarrega o modelo para o próximo áudio
                tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
            else:
                logger.warning(f"⚠️ Artigo {i+1} não contém um resumo.")
    else:
        logger.error("❌ O arquivo JSON não contém uma lista de notícias.")

except Exception as e:
    logger.error(f"❌ Erro durante a execução do script: {e}", exc_info=True)