import feedparser
import logging
import socket
from datetime import datetime
from time import mktime

from .config import Config

logger = logging.getLogger(__name__)

# Timeout global para conexões de rede
socket.setdefaulttimeout(Config.DOWNLOAD_TIMEOUT)

def collect_feed_data(feed_url, limit=5):
    """
    Acessa um feed RSS e retorna uma lista de dicionários com as notícias.
    Versão otimizada para Raspberry Pi:
      - Timeout configurável
      - Limite de tentativas
      - Não bloqueia em feeds lentos
    """
    logger.info(f"🔄 Conectando ao feed: {feed_url}")
    
    try:
        # Feedparser com timeout (usa o socket timeout global)
        feed = feedparser.parse(feed_url)
        
        if feed.bozo and not feed.entries:
            # Se deu erro E não tem entradas, é um problema real
            logger.warning(f"⚠️  Erro no feed {feed_url}: {feed.bozo_exception}")
            return []
        elif feed.bozo and feed.entries:
            # Warning de formato mas tem conteúdo — ok
            logger.info(f"⚠️  Aviso de formato (ignorado): {feed.bozo_exception}")

        news_items = []
        for entry in feed.entries[:limit]:
            published_time = entry.get('published_parsed', entry.get('updated_parsed'))
            pub_date = None
            if published_time:
                pub_date = datetime.fromtimestamp(mktime(published_time))
            
            item = {
                'title': entry.get('title', 'Sem título'),
                'link': entry.get('link', ''),
                'raw_summary': entry.get('summary', entry.get('description', '')),
                'published_at': pub_date
            }
            news_items.append(item)
        
        logger.info(f"✅ {len(news_items)} notícias coletadas")
        return news_items

    except socket.timeout:
        logger.error(f"❌ Timeout ao conectar em {feed_url} ({Config.DOWNLOAD_TIMEOUT}s)")
        return []
    except Exception as e:
        logger.error(f"❌ Erro ao coletar {feed_url}: {e}")
        return []
