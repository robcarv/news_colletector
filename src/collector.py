import feedparser
import logging
from datetime import datetime
from time import mktime
from .config import Config

# Configuração de Log local
logger = logging.getLogger(__name__)

def collect_feed_data(feed_url, limit=5):
    """
    Acessa um feed RSS e retorna uma lista de dicionários com as notícias.
    
    Args:
        feed_url (str): URL do RSS.
        limit (int): Número máximo de notícias para pegar.
    """
    logger.info(f"🔄 Conectando ao feed: {feed_url}")
    
    try:
        # O feedparser baixa e analisa o XML automaticamente
        feed = feedparser.parse(feed_url)
        
        # Verifica se houve erro de conexão (bozo bit)
        if feed.bozo:
            logger.warning(f"⚠️  Aviso de formato no feed {feed_url}: {feed.bozo_exception}")

        news_items = []
        
        # Itera sobre as notícias (respeitando o limite)
        for entry in feed.entries[:limit]:
            # Tenta encontrar a data de publicação (varia muito entre feeds)
            published_time = entry.get('published_parsed', entry.get('updated_parsed'))
            
            # Converte a data para um objeto Python utilizável
            pub_date = None
            if published_time:
                pub_date = datetime.fromtimestamp(mktime(published_time))
            
            # Cria um objeto limpo apenas com o que precisamos
            item = {
                'title': entry.get('title', 'Sem título'),
                'link': entry.get('link', ''),
                # Alguns feeds usam 'summary', outros 'description'
                'raw_summary': entry.get('summary', entry.get('description', '')),
                'published_at': pub_date
            }
            
            news_items.append(item)
            
        logger.info(f"✅ {len(news_items)} notícias coletadas de {feed_url}")
        return news_items

    except Exception as e:
        logger.error(f"❌ Erro crítico ao coletar {feed_url}: {e}")
        return []