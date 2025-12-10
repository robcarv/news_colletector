import re
import logging
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.utils import get_stop_words
from .config import Config

logger = logging.getLogger(__name__)

# Mapeamento simples de códigos de idioma para o Sumy
LANG_MAP = {
    'pt': 'portuguese',
    'en': 'english',
    'es': 'spanish'
}

def clean_html(raw_text):
    """
    Remove tags HTML (<br>, <p>, etc) usando Expressões Regulares (Rápido e Leve).
    """
    if not raw_text:
        return ""
    # Remove tags HTML
    cleanr = re.compile('<.*?>')
    text = re.sub(cleanr, '', raw_text)
    # Remove espaços extras
    return " ".join(text.split())

def summarize_content(text, language='pt', sentences_count=Config.MAX_SUMMARY_SENTENCES):
    """
    Gera um resumo do texto usando LSA (Latent Semantic Analysis).
    """
    if not text:
        return ""

    try:
        # 1. Limpeza inicial
        clean_text = clean_html(text)
        
        # Se o texto for muito curto (ex: só uma manchete), não tenta resumir, retorna ele mesmo.
        if len(clean_text.split()) < 20:
            return clean_text

        # 2. Configura o idioma correto
        full_lang_name = LANG_MAP.get(language, 'portuguese')
        
        # 3. Prepara o parser do Sumy
        parser = PlaintextParser.from_string(clean_text, Tokenizer(full_lang_name))
        summarizer = LsaSummarizer()
        
        # Tenta carregar stopwords (palavras ignoráveis como "o", "a", "de")
        try:
            summarizer.stop_words = get_stop_words(full_lang_name)
        except LookupError:
            logger.warning(f"Stopwords para {full_lang_name} não encontradas. Continuando sem elas.")

        # 4. Gera o resumo
        summary = summarizer(parser.document, sentences_count)
        
        # 5. Converte a lista de frases de volta para texto
        summary_text = " ".join([str(sentence) for sentence in summary])
        
        return summary_text
        
    except Exception as e:
        logger.error(f"⚠️ Erro ao sumarizar: {e}")
        # Fallback: Se der erro no resumo, retorna os primeiros 300 caracteres do texto limpo
        return clean_html(text)[:300] + "..."