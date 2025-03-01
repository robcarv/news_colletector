# utils/text_processing.py
import re

def remove_html_tags(text):
    """
    Remove todas as tags HTML de um texto.
    """
    clean = re.compile(r'<.*?>')
    return re.sub(clean, '', text)

def escape_markdown_v2(text):
    """
    Escapa caracteres especiais para o formato MarkdownV2 do Telegram.
    """
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def clean_text(text):
    """
    Remove caracteres problemáticos e escapa caracteres especiais para MarkdownV2.
    """
    # Remove tags HTML
    text = remove_html_tags(text)
    
    # Escapa caracteres especiais para MarkdownV2
    text = escape_markdown_v2(text)
    
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

def convert_numbers_to_text(text, language="pt"):
    """
    Converte números em texto (por extenso) em português ou inglês.
    Exemplo (pt): "02/22/2025" -> "dois de fevereiro de dois mil e vinte e cinco"
    Exemplo (en): "02/22/2025" -> "February twenty-second, two thousand twenty-five"
    :param text: Texto contendo números.
    :param language: Idioma para conversão ("pt" para português, "en" para inglês).
    :return: Texto com números convertidos para palavras.
    """
    # Dicionários para mapear números para texto
    if language == "pt":
        units = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]
        teens = ["dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
        tens = ["", "dez", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
        hundreds = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]
        months = [
            "janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
        ]
        ordinal_suffixes = {1: "º", 2: "ª"}
    elif language == "en":
        units = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
        teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
        tens = ["", "ten", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
        hundreds = ["", "one hundred", "two hundred", "three hundred", "four hundred", "five hundred", "six hundred", "seven hundred", "eight hundred", "nine hundred"]
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        ordinal_suffixes = {1: "st", 2: "nd", 3: "rd"}
    else:
        return text  # Retorna o texto original se o idioma não for suportado

    # Função para converter números menores que 1000
    def convert_chunk(number):
        if number < 10:
            return units[number]
        elif 10 <= number < 20:
            return teens[number - 10]
        elif 20 <= number < 100:
            return tens[number // 10] + (" " + convert_chunk(number % 10) if number % 10 != 0 else "")
        elif 100 <= number < 1000:
            return hundreds[number // 100] + (" " + convert_chunk(number % 100) if number % 100 != 0 else "")
        else:
            return ""

    # Função para converter datas no formato MM/DD/YYYY
    def convert_date(date_str):
        try:
            month, day, year = map(int, date_str.split('/'))
            month_text = months[month - 1]
            day_text = convert_chunk(day)
            year_text = convert_chunk(year)
            if language == "pt":
                return f"{day_text} de {month_text} de {year_text}"
            elif language == "en":
                return f"{month_text} {day_text}, {year_text}"
        except (ValueError, IndexError):
            return date_str  # Retorna o original se não for uma data válida

    # Função para converter horas no formato HH:MM
    def convert_time(time_str):
        try:
            hour, minute = map(int, time_str.split(':'))
            hour_text = convert_chunk(hour)
            minute_text = convert_chunk(minute)
            if language == "pt":
                return f"{hour_text} horas e {minute_text} minutos"
            elif language == "en":
                return f"{hour_text} hours and {minute_text} minutes"
        except ValueError:
            return time_str  # Retorna o original se não for uma hora válida

    # Converte datas no formato MM/DD/YYYY
    text = re.sub(r'\b(\d{2}/\d{2}/\d{4})\b', lambda x: convert_date(x.group(1)), text)

    # Converte horas no formato HH:MM
    text = re.sub(r'\b(\d{2}:\d{2})\b', lambda x: convert_time(x.group(1)), text)

    # Converte números ordinais (ex: 41º -> quadragésimo primeiro ou 41st -> forty-first)
    if language == "pt":
        text = re.sub(r'(\d+)(º|ª)', lambda x: convert_chunk(int(x.group(1))) + ("º" if x.group(2) == "º" else "ª"), text)
    elif language == "en":
        text = re.sub(r'(\d+)(st|nd|rd|th)', lambda x: convert_chunk(int(x.group(1))) + x.group(2), text)

    return text

def preprocess_text(text, language="pt"):
    """
    Pré-processa o texto para TTS, removendo pontuações, formatando endereços web e convertendo números em texto.
    :param text: Texto a ser pré-processado.
    :param language: Idioma para conversão de números ("pt" para português, "en" para inglês).
    :return: Texto pré-processado.
    """
    try:
        # Remove pontuações desnecessárias
        text = re.sub(r'[.,;:!?]+', ' ', text)  # Substitui pontuações por espaços

        # Formata endereços web
        text = re.sub(r'(\b\w+\.com\b)', lambda x: x.group(1).replace('.', ' ponto ' if language == "pt" else ' dot '), text)
        text = re.sub(r'(\b\w+\.org\b)', lambda x: x.group(1).replace('.', ' ponto ' if language == "pt" else ' dot '), text)
        text = re.sub(r'(\b\w+\.net\b)', lambda x: x.group(1).replace('.', ' ponto ' if language == "pt" else ' dot '), text)

        # Converte números em texto
        text = convert_numbers_to_text(text, language)

        # Remove espaços extras
        text = re.sub(r'\s+', ' ', text).strip()

        return text
    except Exception as e:
        print(f"Erro ao pré-processar texto: {e}")
        return text  # Retorna o texto original em caso de erro

def format_telegram_message(title, summary, source, source_link):
    """
    Formata a mensagem para o Telegram com MarkdownV2.
    """
    # Limpa e escapa o texto
    title = clean_text(title)
    summary = clean_text(summary)
    source = clean_text(source)
    
    # Formata a mensagem
    message = (
        f"📰 *{title}*\n\n"
        f"🔍 *Resumo:* {summary}\n\n"
        f"📌 *Fonte:* [{source}]({source_link})\n\n"
        f"🎧 Ouça o áudio abaixo:"
    )
    
    return message