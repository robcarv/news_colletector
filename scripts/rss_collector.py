import feedparser
import json
from datetime import datetime, timedelta
import os
import logging

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lista de feeds RSS
RSS_FEEDS = [
    "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml",
]

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
    data_folder = "../data"
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
        logger.info(f"📁 Pasta de dados criada: {data_folder}")

    for feed_url in RSS_FEEDS:
        logger.info(f"\n🌐 Coletando notícias de: {feed_url}")
        news = collect_news(feed_url, max_news=10)

        # Salva as notícias coletadas em um arquivo JSON
        feed_name = feed_url.split("//")[1].split("/")[0].replace(".", "_")
        output_file = os.path.join(data_folder, f"{feed_name}_news.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(news, f, ensure_ascii=False, indent=4)

        logger.info(f"💾 Notícias de {feed_url} salvas em {output_file}")
        logger.info(f"📄 Total de notícias salvas para este feed: {len(news)}")

if __name__ == "__main__":
    main()