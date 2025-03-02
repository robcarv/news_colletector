# rss_collector.py
import os
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from services.rss_generator import generate_rss_feed  # Importação do gerador de RSS

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caminho da pasta de dados (relativo ao local do script)
script_dir = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(script_dir, './data')

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
def collect_news(feed_url, max_news=10):
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
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
        logger.info(f"📁 Pasta de dados criada: {data_folder}")

    # Lista de arquivos JSON na pasta de dados
    json_files = [f for f in os.listdir(data_folder) if f.endswith('.json')]

    if not json_files:
        logger.error("❌ Nenhum arquivo JSON encontrado. Verifique a pasta de dados.")
        return

    # Processa cada arquivo JSON
    for json_file in json_files:
        json_path = os.path.join(data_folder, json_file)
        logger.info(f"📂 Carregando o arquivo JSON: {json_file}")

        try:
            # Carrega o JSON
            with open(json_path, 'r', encoding='utf-8') as file:
                json_data = json.load(file)

            # Verifica se o JSON contém a chave "news" e se é uma lista
            if not (isinstance(json_data, dict) and "news" in json_data and isinstance(json_data["news"], list)):
                logger.error(f"❌ O arquivo JSON {json_file} não contém uma lista de notícias na chave 'news'.")
                continue

            # Extrai o idioma do JSON
            language = json_data.get("language", "pt-br")  # Idioma padrão: português
            logger.info(f"🌐 Idioma do feed: {language}")

            # Extrai a lista de notícias
            news_data = json_data["news"]

            # Nome do feed (extraído do nome do arquivo JSON)
            feed_name = json_file.replace("_news.json", "").replace("_", " ").title()

            # Gera o feed RSS com o idioma correto
            rss_file_path = generate_rss_feed(feed_name, news_data, data_folder, language=language)
            if rss_file_path:
                logger.info(f"✅ Feed RSS gerado e salvo em: {rss_file_path}")
            else:
                logger.error("❌ Erro ao gerar o feed RSS.")

        except Exception as e:
            logger.error(f"❌ Erro ao processar o arquivo {json_file}: {e}")

if __name__ == "__main__":
    main()