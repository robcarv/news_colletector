import json
import logging
import os
import time
import gc
import torch
from transformers import pipeline

# Configuração de logs minimalista
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Configurações de segurança
MAX_RETRIES = 3
MEMORY_CHECK_INTERVAL = 5  # em segundos
BATCH_SIZE = 2  # Notícias por lote
MAX_TEXT_LENGTH = 2000  # caracteres

def get_memory_status():
    """Verifica o status de memória disponível"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / (1024 ** 2)
        reserved = torch.cuda.memory_reserved() / (1024 ** 2)
        return f"GPU: {allocated:.2f}MB alocado, {reserved:.2f}MB reservado"
    return "CPU em uso"

def safe_summarize(content, summarizer, max_length=100, min_length=25):
    """Sumarização com tratamento de erros robusto"""
    try:
        if len(content) > MAX_TEXT_LENGTH:
            content = content[:MAX_TEXT_LENGTH] + " [...]"
            
        return summarizer(
            content,
            max_length=max_length,
            min_length=min_length,
            do_sample=False,
            truncation=True
        )[0]['summary_text']
    except Exception as e:
        logger.warning(f"Falha na sumarização: {str(e)}")
        return content[:500] + " [resumo truncado]" if len(content) > 500 else content

def process_article(article, language, model_cache):
    """Processa um artigo individual com limpeza de memória"""
    try:
        content = article.get('summary', article.get('content', ''))
        if not content or len(content.split()) <= 50:
            return article
            
        # Carrega o modelo sob demanda
        if language not in model_cache:
            model_cache[language] = (
                pipeline("summarization", model="facebook/bart-large-cnn") if language == 'en'
                else pipeline("summarization", model="philschmid/distilbart-cnn-12-6-samsum")
            )
        
        article['summary'] = safe_summarize(content, model_cache[language])
        return article
        
    except Exception as e:
        logger.error(f"Erro processando artigo: {str(e)}")
        return article
    finally:
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

def process_file_with_memory_guard(file_path):
    """Processa arquivo com monitoramento rigoroso de memória"""
    model_cache = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        language = data.get("language")
        news_data = data.get("news", [])
        
        if not isinstance(news_data, list):
            logger.error(f"Dados inválidos em {file_path}")
            return

        processed_count = 0
        for i in range(0, len(news_data), BATCH_SIZE):
            logger.info(f"Processando lote {i//BATCH_SIZE + 1} | {get_memory_status()}")
            
            batch = news_data[i:i+BATCH_SIZE]
            for j, article in enumerate(batch):
                news_data[i+j] = process_article(article, language, model_cache)
                processed_count += 1
                
                # Pausa estratégica a cada 5 artigos
                if processed_count % 5 == 0:
                    time.sleep(2)
                    gc.collect()
                    torch.cuda.empty_cache() if torch.cuda.is_available() else None
            
            # Salva progresso a cada lote
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({"language": language, "news": news_data}, f, ensure_ascii=False)
            
            time.sleep(1)  # Pausa entre lotes

    except Exception as e:
        logger.critical(f"Falha catastrófica ao processar {file_path}: {str(e)}")
    finally:
        # Limpeza final agressiva
        del model_cache
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

def main():
    """Ponto de entrada principal com gerenciamento de recursos"""
    input_folder = './data/'
    
    if not os.path.exists(input_folder):
        logger.error("Pasta de dados não encontrada")
        return

    files = [f for f in os.listdir(input_folder) if f.endswith('.json')]
    for i, filename in enumerate(files):
        file_path = os.path.join(input_folder, filename)
        logger.warning(f"Iniciando processamento de {filename} ({i+1}/{len(files)})")
        
        for attempt in range(MAX_RETRIES):
            try:
                process_file_with_memory_guard(file_path)
                break
            except Exception as e:
                logger.error(f"Tentativa {attempt + 1} falhou: {str(e)}")
                time.sleep(10 * (attempt + 1))
        else:
            logger.critical(f"Falha após {MAX_RETRIES} tentativas para {filename}")

if __name__ == "__main__":
    main()