import os
import json
import logging
from datetime import datetime, timezone
from services.audio_generator import generate_audio_for_article, compile_audio_for_feed, cleanup_and_wait
from services.telegram_service import send_to_telegram
from services.rss_generator import generate_rss_feed  # Importação do gerador de RSS

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caminho da pasta de dados
script_dir = os.path.dirname(os.path.abspath(__file__))
input_folder = os.path.join(script_dir, 'data')
audio_folder = os.path.join(input_folder, 'audio')

# Cria a pasta de áudio se não existir
os.makedirs(audio_folder, exist_ok=True)

def process_news(language="en"):
    try:
        json_files = [f for f in os.listdir(input_folder) if f.endswith('.json')]
        if not json_files:
            raise FileNotFoundError(f"❌ Nenhum arquivo JSON encontrado em: {input_folder}")
        
        for json_file in json_files:
            json_path = os.path.join(input_folder, json_file)
            logger.info(f"📂 Carregando o arquivo JSON: {json_file}")
            
            with open(json_path, 'r', encoding='utf-8') as file:
                json_data = json.load(file)
                
            if not (isinstance(json_data, dict) and "news" in json_data and isinstance(json_data["news"], list)):
                logger.error(f"❌ O arquivo JSON {json_file} não contém uma lista de notícias na chave 'news'.")
                continue
            
            if json_data.get("language", "en") != language:
                logger.info(f"⚠️ Ignorando {json_file} (idioma '{json_data.get('language')}' não é '{language}').")
                continue
            
            news_data = json_data["news"]
            feed_name = json_file.replace("_news.json", "").replace("_", " ").title()
            audio_files = []
            
            for i, article in enumerate(news_data):
                title, summary, source, source_link = article.get('title', ''), article.get('summary', ''), article.get('source', ''), article.get('link', '#')
                
                if title and summary:
                    audio_path = generate_audio_for_article(title, summary, source, audio_folder, language=language)
                    if audio_path:
                        audio_files.append(audio_path)
                        send_to_telegram(title, summary, source, source_link, audio_path)
                        cleanup_and_wait()
            
            compiled_audio_path = compile_audio_for_feed(news_data, feed_name, audio_folder, language=language)
            
            if compiled_audio_path:
                logger.info(f"🔗 Gerando feed RSS para: {feed_name}...")
                episode = {
                    "title": f"Resumo das Notícias - {feed_name}",
                    "description": f"Resumo das notícias de {feed_name}.",
                    "link": f"https://seusite.com/{language}/{feed_name}_compiled.mp3",
                    "audio_url": f"https://seusite.com/{language}/{feed_name}_compiled.mp3",
                    "file_size": os.path.getsize(compiled_audio_path),
                    "pub_date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
                    "duration": "30:00"
                }
                rss_file_path = generate_rss_feed(language, audio_folder, input_folder)

                if rss_file_path:
                    logger.info(f"✅ Feed RSS gerado: {rss_file_path}")
                else:
                    logger.error("❌ Erro ao gerar o feed RSS.")
            else:
                logger.warning(f"⚠️ Nenhum áudio compilado para: {feed_name}")
    
    except Exception as e:
        logger.error(f"❌ Erro no processamento ({language}): {e}", exc_info=True)

if __name__ == "__main__":
    process_news("en")
    process_news("pt")
