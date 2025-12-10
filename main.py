import logging
import time
import os
from src.config import Config
from src.collector import collect_feed_data
from src.processor import summarize_content
from src.audio import generate_audio_file
from src.notifier import send_telegram_audio, send_telegram_message

# Configuração do Logger
logger = logging.getLogger(__name__)

def process_feed(feed_config):
    """Processa um único feed de notícias"""
    url = feed_config.get('url')
    lang = feed_config.get('language', 'pt')
    
    logger.info(f"--- Iniciando Feed: {url} ---")
    
    # 1. Coleta
    news_items = collect_feed_data(url, limit=3) # Limite baixo para teste
    
    for item in news_items:
        title = item['title']
        raw_summary = item['raw_summary']
        
        # Cria um ID único baseado no título para o nome do arquivo
        safe_title = "".join([c if c.isalnum() else "_" for c in title])[:50]
        audio_filename = f"{safe_title}.mp3"
        audio_path = str(Config.AUDIO_DIR / audio_filename)
        
        # Verifica se já processamos essa notícia hoje (opcional, simples verificação de arquivo)
        if os.path.exists(audio_path):
            logger.info(f"⏭️ Notícia já processada (arquivo existe): {title}")
            continue

        try:
            # 2. Sumarização
            logger.info(f"📖 Lendo: {title}")
            summary = summarize_content(raw_summary, language=lang)
            
            # Texto que será falado (Título + Pausa + Resumo)
            text_to_speak = f"{title}... {summary}"
            
            # 3. Geração de Áudio
            generated_path = generate_audio_file(text_to_speak, audio_filename, language=lang)
            
            if generated_path:
                # 4. Envio para Telegram
                sent = send_telegram_audio(title, summary, generated_path)
                
                if sent:
                    logger.info("✅ Ciclo completo com sucesso!")
                
                # Pequena pausa para não floodar a API do Telegram
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Erro ao processar item '{title}': {e}")

def main():
    Config.setup_folders()
    logger.info("🚀 Iniciando News Bot V2.0 (Low Memory Edition)")
    
    # Notifica início (opcional)
    # send_telegram_message("🤖 Robô de Notícias V2 iniciado no Raspberry Pi!")
    
    feeds = Config.load_feeds()
    if not feeds:
        logger.error("Nenhum feed configurado em feeds_config.json")
        return

    for feed in feeds:
        process_feed(feed)
    
    logger.info("🏁 Execução finalizada.")

if __name__ == "__main__":
    main()
