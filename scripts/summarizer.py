import json
from transformers import pipeline

# Carrega o modelo de sumarização
summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device=-1)  # Força o uso da CPU

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
            content = article.get('summary', article.get('content', ''))  # Usa o resumo se existir, caso contrário, o conteúdo original
            if len(content.split()) > 50:  # Limita o tamanho mínimo
                # Gera o resumo
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

        print("Summarization completed.")
    else:
        print("O arquivo JSON não contém uma lista de notícias.")

except Exception as e:
    print(f"Erro durante a execução do script: {e}")