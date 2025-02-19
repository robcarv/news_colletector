import feedparser
import json
from datetime import datetime
import os
import logging

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caminho para o arquivo de configuração dos feeds
FEEDS_CONFIG_FILE = "./feeds_config.json"

# Função para carregar a configuração dos feeds
def load_feeds_config():
    try:
        with open(FEEDS_CONFIG_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"❌ Erro ao carregar o arquivo de configuração dos feeds: {e}")
        return []

# Função para coletar notícias de um feed
def collect_news(feed_url, max_news=5):
    feed = feedparser.parse(feed_url)
    news_items = []
    logger.info(f"\n🔍 Processando feed: {feed_url}")
    logger.info(f"📰 Total de entradas encontradas: {len(feed.entries)}")

    for i, entry in enumerate(feed.entries):
        if is_today(entry.published_parsed):
            news_items.append({
                "title": entry.title,
                "summary": entry.summary if "summary" in entry else "",
                "link": entry.link,
                "source": feed.feed.title,
                "publication_date": entry.published if "published" in entry else ""
            })
            logger.info(f"✅ Notícia {i+1} adicionada: {entry.title}")

            if len(news_items) >= max_news:
                logger.info(f"🚫 Limite de {max_news} notícias atingido para este feed.")
                break

    logger.info(f"📥 Total de notícias coletadas de {feed_url}: {len(news_items)}")
    return news_items

# Função para verificar se a data de publicação é hoje
def is_today(published_parsed):
    if not published_parsed:
        logger.warning("⚠️ Aviso: Nenhuma data de publicação encontrada para uma entrada.")
        return False
    published_date = datetime(*published_parsed[:6])
    today = datetime.now()
    return published_date.date() == today.date()

# Função principal
def main():
    # Cria a pasta de dados se não existir
    data_folder = "./data"
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
        logger.info(f"📁 Pasta de dados criada: {data_folder}")

    # Carrega a configuração dos feeds
    feeds_config = load_feeds_config()
    if not feeds_config:
        logger.error("❌ Nenhum feed configurado. Verifique o arquivo feeds_config.json.")
        return

    for feed in feeds_config:
        feed_url = feed.get("url")
        language = feed.get("language")
        if not feed_url or not language:
            logger.warning(f"⚠️ Feed inválido ou sem idioma definido: {feed}")
            continue

        logger.info(f"\n🌐 Coletando notícias de: {feed_url} (Idioma: {language})")
        news = collect_news(feed_url, max_news=10)

        # Salva as notícias coletadas em um arquivo JSON
        feed_name = feed_url.split("//")[1].split("/")[0].replace(".", "_")
        output_file = os.path.join(data_folder, f"{feed_name}_news.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({"language": language, "news": news}, f, ensure_ascii=False, indent=4)

        logger.info(f"💾 Notícias de {feed_url} salvas em {output_file}")
        logger.info(f"📄 Total de notícias salvas para este feed: {len(news)}")

if __name__ == "__main__":
    main()