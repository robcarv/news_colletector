import json
from transformers import pipeline
import logging

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega o modelo de sumarização
summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device=-1)  # Usa CPU
input_folder = '../data/'
output_file = input_folder + 'feeds_folha_uol_com_br_news.json'

try:
    # Abre o arquivo JSON com as notícias
    with open(output_file, 'r', encoding='utf-8') as file:
        news_data = json.load(file)

    # Verifica se o JSON contém uma lista de notícias
    if isinstance(news_data, list):
        summarized_news = []
        for i, article in enumerate(news_data):
            content = article.get('summary', article.get('content', ''))
            if len(content.split()) > 50:  # Limita o tamanho mínimo
                logger.info(f"📝 Sumarizando notícia {i+1}...")
                summary = summarizer(
                    content,
                    max_length=100,
                    min_length=25,
                    do_sample=False
                )
                article['summary'] = summary[0]['summary_text']
            else:
                article['summary'] = content  # Se for muito curto, mantém o original
            summarized_news.append(article)

        # Salva as notícias resumidas de volta no arquivo JSON
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(summarized_news, file, indent=4, ensure_ascii=False)

        logger.info("✅ Sumarização concluída.")
    else:
        logger.error("❌ O arquivo JSON não contém uma lista de notícias.")

except Exception as e:
    logger.error(f"❌ Erro durante a execução do script: {e}", exc_info=True)