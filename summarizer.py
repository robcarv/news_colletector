import json
from transformers import pipeline
import logging
import os

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega os modelos de sumarização para inglês e português
summarizer_en = pipeline("summarization", model="facebook/bart-large-cnn", device=-1)  # Modelo para inglês
summarizer_pt = pipeline("summarization", model="philschmid/bart-large-cnn-samsum", device=-1)  # Modelo para português

# Pasta de entrada (onde os arquivos JSON estão armazenados)
input_folder = './data/'

def summarize_article(content, language):
    """
    Sumariza o conteúdo com base no idioma.
    """
    if language == 'en':
        summarizer = summarizer_en
    elif language == 'pt':
        summarizer = summarizer_pt
    else:
        return content  # Retorna o conteúdo original se o idioma não for suportado

    if len(content.split()) > 50:  # Limita o tamanho mínimo para sumarização
        summary = summarizer(
            content,
            max_length=100,
            min_length=25,
            do_sample=False
        )
        return summary[0]['summary_text']
    else:
        return content  # Se for muito curto, mantém o original

def process_file(file_path):
    """
    Processa um arquivo JSON, sumarizando as notícias.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        language = data.get("language")
        news_data = data.get("news", [])

        if isinstance(news_data, list):
            summarized_news = []
            for i, article in enumerate(news_data):
                content = article.get('summary', article.get('content', ''))
                logger.info(f"📝 Sumarizando notícia {i+1}...")
                article['summary'] = summarize_article(content, language)
                summarized_news.append(article)

            # Salva as notícias resumidas de volta no arquivo JSON
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump({"language": language, "news": summarized_news}, file, indent=4, ensure_ascii=False)

            logger.info(f"✅ Sumarização concluída para {file_path}.")
        else:
            logger.error(f"❌ O arquivo {file_path} não contém uma lista de notícias.")

    except Exception as e:
        logger.error(f"❌ Erro durante o processamento do arquivo {file_path}: {e}", exc_info=True)

def main():
    # Itera sobre todos os arquivos JSON na pasta de dados
    for filename in os.listdir(input_folder):
        if filename.endswith('.json'):
            file_path = os.path.join(input_folder, filename)
            logger.info(f"🌐 Processando arquivo: {filename}")
            process_file(file_path)

if __name__ == "__main__":
    main()