# utils/text_processing.py
import re

def remove_html_tags(text):
    """
    Remove todas as tags HTML de um texto.
    """
    clean = re.compile(r'<.*?>')
    return re.sub(clean, '', text)

def clean_text(text):
    """
    Remove caracteres que podem causar problemas na formatação Markdown do Telegram.
    Apenas escapa os caracteres especiais usados no Markdown.
    """
    # Lista de caracteres que precisam ser escapados no Markdown do Telegram
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Escapa apenas os caracteres especiais
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def generate_valid_filename(title):
    """
    Gera um nome de arquivo válido a partir do título da notícia, removendo caracteres especiais.
    """
    # Remove caracteres especiais e substitui espaços por underscores
    valid_filename = re.sub(r'[^\w\-_\. ]', '_', title)
    valid_filename = re.sub(r'\s+', '_', valid_filename)
    valid_filename = valid_filename.lower()
    return valid_filename

def preprocess_text(text):
    """
    Pré-processa o texto para TTS, removendo pontuações e formatando endereços web.
    """
    text = re.sub(r'[.,;:!?]+', ' ', text)
    text = re.sub(r'(\b\w+\.com\b)', lambda x: x.group(1).replace('.', ' ponto '), text)
    text = re.sub(r'(\b\w+\.org\b)', lambda x: x.group(1).replace('.', ' ponto '), text)
    text = re.sub(r'(\b\w+\.net\b)', lambda x: x.group(1).replace('.', ' ponto '), text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
# utils/text_processing.py
def format_telegram_message(title, summary, source, source_link, max_length=4096):
    """
    Formata todos os elementos da notícia para uma mensagem do Telegram
    """
    # Limpa cada parte do texto
    clean_title = clean_text(title)
    clean_summary = clean_text(summary)
    clean_source = clean_text(source)

    # Formata a mensagem com Markdown
    message = f"""
    *{clean_title}*
    
    {clean_summary}
    
    Fonte: [{clean_source}]({source_link})
    """
    
    # Limita o tamanho se necessário
    if len(message) > max_length:
        message = message[:max_length-3] + "..."
    
    return message