import os
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import feedparser
# from services.rss_generator import generate_rss_feed  # Importação do gerador de RSS

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caminho da pasta de dados (relativo ao local do script)
script_dir = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(script_dir, './data')

# Caminho para o arquivo de configuração de feeds
feeds_config_path = os.path.join(script_dir, 'feeds_config.json')

# Função para extrair texto de HTML
def extract_text_from_html(html_content):
    """
    Extrai texto de um conteúdo HTML.
    :param html_content: Conteúdo HTML.
    :return: Texto extraído.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(separator=" ").strip()
    except Exception as e:
        logger.error(f"❌ Erro ao extrair texto do HTML: {e}")
        return ""

# Função para coletar notícias de um feed
def collect_news(feed_url, max_news=2):
    feed = feedparser.parse(feed_url)
    news_items = []
    logger.info(f"\n🔍 Processando feed: {feed_url}")
    logger.info(f"📰 Total de entradas encontradas: {len(feed.entries)}")

    for i, entry in enumerate(feed.entries):
        try:
            # Verifica se a entrada tem os campos necessários
            if not all(key in entry for key in ['title', 'link', 'published']):
                logger.warning(f"⚠️ Entrada {i+1} do feed {feed_url} está incompleta. Pulando...")
                continue

            # Verifica se a data de publicação é hoje
            if not is_today(entry.published_parsed):
                continue

            # Extrai os dados da notícia
            title = entry.title
            link = entry.link
            source = feed.feed.title if "title" in feed.feed else "Fonte desconhecida"
            publication_date = entry.published

            # Extrai o resumo do campo <description> (que contém HTML)
            summary = ""
            if "description" in entry:
                summary = extract_text_from_html(entry.description)

            # Adiciona a notícia à lista
            news_items.append({
                "title": title,
                "summary": summary,
                "link": link,
                "source": source,
                "publication_date": publication_date
            })
            logger.info(f"✅ Notícia {i+1} adicionada: {title}")

            # Limita o número de notícias coletadas
            if len(news_items) >= max_news:
                logger.info(f"🚫 Limite de {max_news} notícias atingido para este feed.")
                break
        except Exception as e:
            logger.error(f"❌ Erro ao processar entrada {i+1} do feed {feed_url}: {e}")

    logger.info(f"📥 Total de notícias coletadas de {feed_url}: {len(news_items)}")
    return news_items

# Função para salvar notícias em um arquivo JSON
def save_news_to_json(news_items, feed_name, language="pt-br"):
    """
    Salva as notícias coletadas em um arquivo JSON.
    :param news_items: Lista de notícias.
    :param feed_name: Nome do feed (usado para nomear o arquivo JSON).
    :param language: Idioma das notícias.
    """
    try:
        # Cria a pasta de dados se não existir
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)
            logger.info(f"📁 Pasta de dados criada: {data_folder}")

        # Nome do arquivo JSON
        json_filename = f"{feed_name}_news.json"
        json_path = os.path.join(data_folder, json_filename)

        # Salva as notícias em um arquivo JSON
        with open(json_path, 'w', encoding='utf-8') as file:
            json.dump({"language": language, "news": news_items}, file, indent=4, ensure_ascii=False)
        
        logger.info(f"✅ Notícias salvas em: {json_path}")
    except Exception as e:
        logger.error(f"❌ Erro ao salvar notícias em JSON: {e}")

# Função para verificar se a data de publicação é hoje
def is_today(published_parsed):
    if not published_parsed:
        logger.warning("⚠️ Aviso: Nenhuma data de publicação encontrada para uma entrada.")
        return False
    published_date = datetime(*published_parsed[:6])
    today = datetime.now()
    return published_date.date() == today.date()

# Função para carregar a configuração de feeds
def load_feeds_config():
    """
    Carrega a configuração de feeds do arquivo feeds_config.json.
    :return: Lista de feeds configurados.
    """
    try:
        with open(feeds_config_path, 'r', encoding='utf-8') as file:
            feeds_config = json.load(file)
        logger.info("✅ Configuração de feeds carregada com sucesso.")
        return feeds_config
    except Exception as e:
        logger.error(f"❌ Erro ao carregar a configuração de feeds: {e}")
        return []

# Função principal
def main():
    # Carrega a configuração de feeds
    feeds_config = load_feeds_config()
    if not feeds_config:
        logger.error("❌ Nenhum feed configurado. Verifique o arquivo feeds_config.json.")
        return

    # Coleta notícias de cada feed e salva em JSON
    for feed in feeds_config:
        feed_url = feed.get("url")
        language = feed.get("language", "pt-br")  # Idioma padrão: português
        feed_name = feed_url.split("//")[1].split("/")[0].replace(".", "_")  # Gera um nome para o feed

        logger.info(f"🌐 Coletando notícias do feed: {feed_url} (Idioma: {language})")
        news_items = collect_news(feed_url)
        save_news_to_json(news_items, feed_name, language)

if __name__ == "__main__":
    main()