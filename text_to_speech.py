import os
import json
import logging
import time
import resource
import psutil
from datetime import datetime, timezone
from services.audio_generator import generate_audio_for_article, compile_audio_for_feed, cleanup_and_wait
from services.telegram_service import send_to_telegram
from services.rss_generator import generate_rss_feed

# Configurações de segurança para Raspberry Pi
TTS_MAX_ATTEMPTS = 3  # Número máximo de tentativas por artigo
TTS_COOLDOWN = 30      # Tempo base de espera entre tentativas (segundos)
MAX_CPU_PERCENT = 70   #% máxima de uso da CPU
COOLDOWN_BASE = 10     # segundos base entre operações
MAX_FILES_PER_RUN = 2  # Limite de arquivos por execução
MAX_ARTICLES_PER_FILE = 3  # Limite de artigos por arquivo
# Configurações de segurança para Raspberry Pi
MEMORY_LIMIT = 256      # Reduzido para 256MB
SWAP_THRESHOLD = 100    # MB de swap antes de pausar
COOLDOWN_EXTENDED = 60  # Pausa maior quando swap está alto

# Configuração de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tts_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_system_resources():
    """Obtém estatísticas detalhadas de recursos"""
    try:
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)
        swap = psutil.swap_memory()
        return {
            'mem_used': mem.used / (1024 ** 2),
            'mem_available': mem.available / (1024 ** 2),
            'mem_percent': mem.percent,
            'cpu_percent': cpu,
            'swap_used': swap.used / (1024 ** 2)
        }
    except Exception as e:
        logger.warning(f"Monitoramento de recursos falhou: {e}")
        return None

def check_system_resources():
    """Versão com monitoramento de swap aprimorado"""
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        cpu = psutil.cpu_percent(interval=1)
        
        # Verifica uso de swap primeiro
        # swap_used = swap.used / (1024 ** 2)  # MB
        # if swap_used > SWAP_THRESHOLD:
        #     wait = min(COOLDOWN_EXTENDED, 30 + swap_used / 10)  # Pausa proporcional
        #     logger.warning(f"⚠️ Swap alto: {swap_used:.0f}MB - Pausa de {wait:.0f}s")
        #     time.sleep(wait)
        #     return False
            
        # Demais verificações
        if mem.percent > 85 or cpu > 70:
            wait = COOLDOWN_BASE * 2
            logger.warning(f"⏳ Sistema sobrecarregado (CPU: {cpu}%, Mem: {mem.percent}%) - Pausa de {wait}s")
            time.sleep(wait)
            return False
            
        return True
    except Exception as e:
        logger.warning(f"⚠️ Monitoramento falhou: {e}")
        return True  # Continua mesmo com falha no monitoramento

def set_memory_limit():
    """Define limites de memória com fallback seguro"""
    try:
        soft_limit = MEMORY_LIMIT * 1024 * 1024
        hard_limit = int(soft_limit * 1.1)  # 10% de tolerância
        resource.setrlimit(resource.RLIMIT_AS, (soft_limit, hard_limit))
        logger.info(f"🔒 Limite de memória definido para {MEMORY_LIMIT}MB")
    except Exception as e:
        logger.warning(f"Não foi possível definir limite de memória: {e}")

def process_article(article, audio_folder, language):
    """Processa um artigo com múltiplas tentativas e gerenciamento de recursos"""
    last_error = None
    audio_path = None
    
    for attempt in range(TTS_MAX_ATTEMPTS):
        try:
            # if not check_system_resources():
            #     raise MemoryError("Recursos do sistema insuficientes")
                
            start_time = time.time()
            
            audio_path = generate_audio_for_article(
                article.get('title', ''),
                article.get('summary', ''),
                article.get('source', ''),
                audio_folder,
                language=language
            )
            
            if audio_path:
                # Envio para Telegram com verificação de recursos
                # if check_system_resources():
                send_to_telegram(
                    article.get('title', ''),
                    article.get('summary', ''),
                    article.get('source', ''),
                    article.get('link', '#'),
                    audio_path
                    )
                # else:
                #     logger.warning("Recursos insuficientes para enviar ao Telegram")
                
                # Cooldown adaptativo baseado no tempo de processamento
                processing_time = time.time() - start_time
                cooldown = max(COOLDOWN_BASE, processing_time * 0.75)
                logger.info(f"⏳ Cooldown de {cooldown:.1f}s após artigo")
                time.sleep(cooldown)
                
                return audio_path
                
        except MemoryError as e:
            last_error = e
            wait_time = TTS_COOLDOWN * (attempt + 1)
            logger.warning(
                f"⚠️ Falha de memória na tentativa {attempt + 1}/{TTS_MAX_ATTEMPTS}. "
                f"Aguardando {wait_time}s..."
            )
            cleanup_and_wait()
            time.sleep(wait_time)
            
        except Exception as e:
            last_error = e
            logger.error(f"Erro processando artigo (tentativa {attempt + 1}): {e}")
            time.sleep(COOLDOWN_BASE)
            if attempt == TTS_MAX_ATTEMPTS - 1:  # Última tentativa
                raise
    
    logger.error(
        f"❌ Falha após {TTS_MAX_ATTEMPTS} tentativas. Último erro: {str(last_error)}"
    )
    return None

def process_news(language="en"):
    """Função principal de processamento com gerenciamento completo de recursos"""
    # set_memory_limit()
    start_time = time.time()
    processed_count = 0
    
    try:
        input_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        audio_folder = os.path.join(input_folder, 'audio')
        os.makedirs(audio_folder, exist_ok=True)

        json_files = sorted([
            f for f in os.listdir(input_folder) 
            if f.endswith('.json') and not f.startswith('_')
        ])
        
        if not json_files:
            logger.error(f"❌ Nenhum arquivo JSON encontrado em: {input_folder}")
            return

        logger.info(f"📚 Arquivos a processar ({language}): {len(json_files)}")
        
        for json_file in json_files[:MAX_FILES_PER_RUN]:
            # if not check_system_resources():
            #     break
                
            json_path = os.path.join(input_folder, json_file)
            logger.info(f"📂 Processando: {json_file}")
            
            try:
                with open(json_path, 'r', encoding='utf-8') as file:
                    json_data = json.load(file)
                    
                if json_data.get("language", "en") != language:
                    logger.info(f"Idioma não corresponde - pulando: {json_file}")
                    continue
                    
                news_data = json_data.get("news", [])[:MAX_ARTICLES_PER_FILE]
                audio_files = []
                
                for article in news_data:
                    try:
                        audio_path = process_article(article, audio_folder, language)
                        if audio_path:
                            audio_files.append(audio_path)
                            processed_count += 1
                    except Exception as e:
                        logger.error(f"Erro crítico processando artigo: {e}")
                        continue
                
                # Processamento final do feed
                if audio_files :
                    try:
                        compile_audio_for_feed(
                            news_data, 
                            os.path.splitext(json_file)[0], 
                            audio_folder, 
                            language
                        )
                        generate_rss_feed(language, audio_folder, input_folder)
                    except Exception as e:
                        logger.error(f"Erro gerando feed/RSS: {e}")
                
            except Exception as e:
                logger.error(f"Erro processando arquivo {json_file}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Erro crítico no processamento: {e}", exc_info=True)
    finally:
        total_time = (time.time() - start_time) / 60
        logger.info(
            f"🎉 Processamento concluído. "
            f"Artigos processados: {processed_count} | "
            f"Tempo total: {total_time:.1f} minutos"
        )
        cleanup_and_wait()
        time.sleep(COOLDOWN_BASE)

if __name__ == "__main__":
    logger.info("🚀 Iniciando processamento de notícias")
    
    # Processa um idioma por vez com intervalo maior
    process_news("en")
    
    # if check_system_resources():
    #     time.sleep(30)
    #     process_news("pt")
    # else:
    #     logger.warning("Sistema sobrecarregado - pulando processamento em PT")
    
    logger.info("🏁 Todos os processamentos concluídos")