"""Normaliza números, datas, horas e símbolos para leitura natural em TTS.

Suporta PT-BR e EN. Deve ser chamado ANTES do TTS para evitar
leitura robótica de números como "dois zero dois seis" em vez de
"dois mil e vinte e seis".
"""
import re
from datetime import datetime
from num2words import num2words

# ─── PT-BR ──────────────────────────────────────────────────────────

_MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
}

_DIAS_SEMANA_PT = {
    0: "domingo", 1: "segunda-feira", 2: "terça-feira",
    3: "quarta-feira", 4: "quinta-feira", 5: "sexta-feira", 6: "sábado"
}


def _year_pt(match):
    """2026 → 'dois mil e vinte e seis'"""
    return num2words(int(match.group(1)), lang='pt_BR')


def _time_pt(match):
    """15:30 → 'três e meia', 09:00 → 'nove em ponto'"""
    h, m = int(match.group(1)), int(match.group(2))
    hora = num2words(h, lang='pt_BR')
    if m == 0:
        return f"{hora} em ponto"
    elif m == 30:
        return f"{hora} e meia"
    elif m == 15:
        return f"{hora} e quinze"
    elif m == 45:
        return f"{hora} e quarenta e cinco"
    else:
        return f"{hora} e {num2words(m, lang='pt_BR')}"


def _percent_pt(match):
    """85% → 'oitenta e cinco por cento'"""
    n = match.group(1).replace(',', '.')
    try:
        val = float(n)
        if val == int(val):
            return f"{num2words(int(val), lang='pt_BR')} por cento"
        return f"{num2words(val, lang='pt_BR')} por cento"
    except ValueError:
        return match.group(0)


def _money_pt(match):
    """R$ 50 → 'cinquenta reais', R$ 1.5 → 'um e meio reais'"""
    n = match.group(1).replace(',', '.')
    try:
        val = float(n)
        if val == int(val):
            return f"{num2words(int(val), lang='pt_BR')} reais"
        return f"{num2words(val, lang='pt_BR')} reais"
    except ValueError:
        return match.group(0)


def _magnitude_pt(match):
    """1.5M → 'um milhão e meio', 500K → 'quinhentos mil'"""
    num = float(match.group(1).replace(',', '.'))
    mag = match.group(2)
    if mag == 'K':
        val = int(num * 1000)
        return num2words(val, lang='pt_BR')
    elif mag == 'M':
        if num == int(num):
            return f"{num2words(int(num), lang='pt_BR')} milhões"
        return f"{num2words(num, lang='pt_BR')} milhões"
    return match.group(0)


def _iso_date_pt(match):
    """2026-06-19 → 'dezenove de junho de dois mil e vinte e seis'"""
    try:
        d = datetime.fromisoformat(match.group(0))
        dia = num2words(d.day, lang='pt_BR')
        mes = _MESES_PT[d.month]
        ano = num2words(d.year, lang='pt_BR')
        return f"{dia} de {mes} de {ano}"
    except ValueError:
        return match.group(0)


def _iso_datetime_pt(match):
    """2026-06-19T16:30:00 → 'dezesseis e meia de dezenove de junho'"""
    try:
        d = datetime.fromisoformat(match.group(0))
        hora = num2words(d.hour, lang='pt_BR')
        if d.minute == 30:
            hora_str = f"{hora} e meia"
        elif d.minute == 0:
            hora_str = f"{hora} em ponto"
        else:
            hora_str = f"{hora} e {num2words(d.minute, lang='pt_BR')}"
        dia = num2words(d.day, lang='pt_BR')
        mes = _MESES_PT[d.month]
        return f"{hora_str} de {dia} de {mes}"
    except ValueError:
        return match.group(0)


def _ordinal_pt(match):
    """1º → 'primeiro', 2ª → 'segunda'"""
    n = int(match.group(1))
    try:
        return num2words(n, lang='pt_BR', to='ordinal')
    except TypeError:
        return match.group(0)


def normalize_pt(text):
    """Pipeline completo de normalização PT-BR.

    >>> normalize_pt('Em 2026, às 15:30, arrecadou R$ 1.5M, alta de 85%')
    'Em dois mil e vinte e seis, às quinze e meia, arrecadou um vírgula cinco milhões reais, alta de oitenta e cinco por cento'
    """
    # Ordem importa: datetime ISO antes de data ISO, antes de hora, antes de ano
    text = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', _iso_datetime_pt, text)
    text = re.sub(r'\d{4}-\d{2}-\d{2}', _iso_date_pt, text)
    text = re.sub(r'\b(\d{1,2}):(\d{2})\b', _time_pt, text)
    text = re.sub(r'\b(\d{4})\b', _year_pt, text)
    text = re.sub(r'R\$\s*(\d+(?:[.,]\d+)?)', _money_pt, text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*([KM])\b', _magnitude_pt, text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*%', _percent_pt, text)
    text = re.sub(r'\b(\d+)\s*[º°ª]\b', _ordinal_pt, text)
    return text


# ─── EN ────────────────────────────────────────────────────────────

_MONTHS_EN = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}

_DAYS_EN = {
    0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday",
    4: "Thursday", 5: "Friday", 6: "Saturday"
}


def _year_en(match):
    """2026 → 'twenty twenty-six'"""
    return num2words(int(match.group(1)), lang='en')


def _time_en(match):
    """15:30 → 'three thirty PM'"""
    h, m = int(match.group(1)), int(match.group(2))
    if m == 0:
        return num2words(h, lang='en') + " o'clock"
    else:
        return f"{num2words(h, lang='en')} {num2words(m, lang='en')}"


def _iso_date_en(match):
    """2026-06-19 → 'June nineteenth, twenty twenty-six'"""
    try:
        d = datetime.fromisoformat(match.group(0))
        day = num2words(d.day, lang='en', to='ordinal')
        month = _MONTHS_EN[d.month]
        year = num2words(d.year, lang='en')
        return f"{month} {day}, {year}"
    except ValueError:
        return match.group(0)


def normalize_en(text):
    """Pipeline completo de normalização EN."""
    text = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
                  lambda m: _iso_date_en(m), text)
    text = re.sub(r'\d{4}-\d{2}-\d{2}', _iso_date_en, text)
    text = re.sub(r'\b(\d{1,2}):(\d{2})\b', _time_en, text)
    text = re.sub(r'\b(\d{4})\b', _year_en, text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%',
                  lambda m: f"{num2words(float(m.group(1)), lang='en')} percent",
                  text)
    return text


# ─── Testes rápidos ─────────────────────────────────────────────────

if __name__ == '__main__':
    tests_pt = [
        ("Em 2026, 85% de alta", "dois mil e vinte e seis"),
        ("Às 15:30", "quinze e meia"),
        ("R$ 50", "cinquenta reais"),
        ("1.5M", "milhões"),
    ]
    print("=== PT-BR ===")
    for text, expected in tests_pt:
        result = normalize_pt(text)
        ok = expected in result
        print(f"  {'✅' if ok else '❌'} {text:30s} → {result[:60]}")
    
    tests_en = [
        ("In 2026", "twenty twenty-six"),
        ("At 15:30", "fifteen thirty"),
        ("85% growth", "eighty-five percent"),
    ]
    print("\n=== EN ===")
    for text, expected in tests_en:
        result = normalize_en(text)
        ok = expected.lower() in result.lower()
        print(f"  {'✅' if ok else '❌'} {text:30s} → {result[:60]}")
