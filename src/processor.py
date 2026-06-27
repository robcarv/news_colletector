"""
Resumo de noticias — leve por padrao, Sumy LSA opcional.
"""
import re
import logging
from .config import Config

logger = logging.getLogger(__name__)

LANG_MAP = {
    'pt': 'portuguese',
    'en': 'english',
    'es': 'spanish'
}


def clean_html(raw_text):
    """Remove HTML tags e normaliza whitespace."""
    if not raw_text:
        return ""
    cleanr = re.compile('<.*?>')
    text = re.sub(cleanr, '', raw_text)
    return " ".join(text.split())


def _summarize_light(text, max_chars=300):
    """Resumo leve: primeiras 2-3 frases do texto original.
    
    Zero dependencias, ~0.001s, <1MB RAM.
    """
    if not text:
        return ""
    clean = clean_html(text)
    if len(clean) <= max_chars:
        return clean
    
    # Extrai frases por pontuacao
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    result = ""
    for s in sentences[:3]:
        if len(result) + len(s) <= max_chars:
            result += s + " "
        else:
            break
    
    result = result.strip()
    return result if result else clean[:max_chars]


def _summarize_sumy(text, language='portuguese', sentences_count=3):
    """Resumo LSA via Sumy (pesado: +40MB RAM)."""
    try:
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.lsa import LsaSummarizer
        from sumy.utils import get_stop_words

        clean = clean_html(text)
        if len(clean.split()) < 20:
            return clean

        parser = PlaintextParser.from_string(clean, Tokenizer(language))
        summarizer = LsaSummarizer()
        try:
            summarizer.stop_words = get_stop_words(language)
        except LookupError:
            pass

        summary = summarizer(parser.document, sentences_count)
        return " ".join([str(s) for s in summary])
    except Exception as e:
        logger.warning(f"Sumy fallback error: {e}")
        return _summarize_light(text)


def summarize_content(text, language='pt', sentences_count=None, use_sumy=False):
    """Gera resumo do texto.
    
    Args:
        text: Texto bruto (pode conter HTML)
        language: 'pt', 'en', 'es'
        sentences_count: Numero de frases (default: Config.MAX_SUMMARY_SENTENCES)
        use_sumy: Se True, usa Sumy LSA (mais pesado). Default: False (leve).
    
    Returns:
        Texto resumido
    """
    if not text:
        return ""

    if sentences_count is None:
        sentences_count = Config.MAX_SUMMARY_SENTENCES

    try:
        if use_sumy:
            full_lang = LANG_MAP.get(language, 'portuguese')
            return _summarize_sumy(text, full_lang, sentences_count)
        else:
            max_chars = sentences_count * 150  # ~150 chars por frase
            return _summarize_light(text, max_chars=max_chars)
    except Exception as e:
        logger.error(f"Erro ao sumarizar: {e}")
        return clean_html(text)[:300] + "..."
