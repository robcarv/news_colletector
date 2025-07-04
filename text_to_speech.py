import os
import json
import logging
import time
import resource
from datetime import datetime, timezone
from services.audio_generator import generate_audio_for_article, compile_audio_for_feed, cleanup_and_wait
from services.telegram_service import send_to_telegram
from services.rss_generator import generate_rss_feed

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Limites de recursos (ajuste conforme seu hardware)
MAX_CPU_USAGE = 70  # % máxima de uso da CPU
MEMORY_LIMIT = 512  # MB máximo por processo
COOLDOWN_INTERVAL = 3  # segundos entre artigos

def set_memory_limit():
    """Limita o uso de memória do processo"""
    resource.setrlimit(
        resource.RLIMIT_AS,
        (MEMORY_LIMIT * 1024 * 1024, MEMORY_LIMIT * 1024 * 1024)
    )
    logger.info(f"🔒 Limite de memória definido para {MEMORY_LIMIT}MB")

def check_system_resources():
    """Verifica se há recursos suficientes antes de continuar"""
    try:
        # Simples verificação de carga da CPU
        with open('/proc/loadavg', 'r') as f:
            load = float(f.read().split()[0])
            if load > MAX_CPU_USAGE / 100 * os.cpu_count():
                time.sleep(COOLDOWN_INTERVAL * 2)
                logger.warning("⏳ CPU sobrecarregada - pausa estendida")
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível verificar recursos: {e}")

def process_news(language="en"):
    set_memory_limit()  # Aplica limite para todo o processo
    
    try:
        input_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        audio_folder = os.path.join(input_folder, 'audio')
        os.makedirs(audio_folder, exist_ok=True)

        json_files = [f for f in os.listdir(input_folder) if f.endswith('.json')]
        if not json_files:
            raise FileNotFoundError(f"❌ Nenhum arquivo JSON encontrado em: {input_folder}")
        
        for json_file in json_files[:3]:  # Limita a 3 arquivos por execução
            check_system_resources()
            
            json_path = os.path.join(input_folder, json_file)
            logger.info(f"📂 Processando: {json_file}")
            
            with open(json_path, 'r', encoding='utf-8') as file:
                json_data = json.load(file)
                
            if not isinstance(json_data.get("news"), list):
                continue
                
            if json_data.get("language", "en") != language:
                continue
                
            news_data = json_data["news"][:5]  # Limita a 5 artigos por arquivo
            audio_files = []
            
            for article in news_data:
                start_time = time.time()
                
                # Processamento com verificação de recursos
                check_system_resources()
                audio_path = generate_audio_for_article(
                    article.get('title', ''),
                    article.get('summary', ''),
                    article.get('source', ''),
                    audio_folder,
                    language=language
                )
                
                if audio_path:
                    audio_files.append(audio_path)
                    send_to_telegram(
                        article.get('title', ''),
                        article.get('summary', ''),
                        article.get('source', ''),
                        article.get('link', '#'),
                        audio_path
                    )
                    
                    # Pausa estratégica
                    processing_time = time.time() - start_time
                    cooldown = max(COOLDOWN_INTERVAL, processing_time * 0.5)
                    time.sleep(cooldown)
                    cleanup_and_wait()
            
            # Processamento final com intervalo
            time.sleep(COOLDOWN_INTERVAL)
            compile_audio_for_feed(news_data, json_file.replace("_news.json", ""), audio_folder, language)
            generate_rss_feed(language, audio_folder, input_folder)
    
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}", exc_info=True)
    finally:
        logger.info("♻️  Liberando recursos...")
        time.sleep(COOLDOWN_INTERVAL)

if __name__ == "__main__":
    # Processa um idioma por vez com intervalo
    process_news("en")
    time.sleep(10)
    process_news("pt")