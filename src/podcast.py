"""Gerador de podcast diário — concatena áudios TTS com intro/outro via ffmpeg.

Uso:
    from src.podcast import generate_podcast
    generate_podcast(all_items, 'podcast_2026-06-20.mp3', language='pt')
"""
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .config import Config
from .audio import generate_audio_file

logger = logging.getLogger(__name__)

BASE_DIR = Config.BASE_DIR
AUDIO_DIR = Config.AUDIO_DIR

# Arquivos estáticos de áudio (criados uma vez)
SILENCE_1S = AUDIO_DIR / "silence_1s.wav"
SILENCE_2S = AUDIO_DIR / "silence_2s.wav"
INTRO = AUDIO_DIR / "intro.mp3"
OUTRO = AUDIO_DIR / "outro.mp3"


def _ensure_static_audio():
    """Gera arquivos de áudio estáticos se não existirem."""
    for path, cmd in [
        (SILENCE_1S, ['ffmpeg', '-y', '-f', 'lavfi', '-i',
         'anullsrc=r=24000:cl=mono', '-t', '1', str(SILENCE_1S)]),
        (SILENCE_2S, ['ffmpeg', '-y', '-f', 'lavfi', '-i',
         'anullsrc=r=24000:cl=mono', '-t', '2', str(SILENCE_2S)]),
    ]:
        if not path.exists():
            logger.info(f"  Gerando {path.name}...")
            subprocess.run(cmd, capture_output=True, timeout=10)

    # Intro e outro: tons musicais simples com fade
    for path, freq, dur, fade_in, fade_out in [
        (INTRO, 440, 8, 2, 2),
        (OUTRO, 330, 6, 1.5, 1.5),
    ]:
        if not path.exists():
            logger.info(f"  Gerando {path.name}...")
            cmd = [
                'ffmpeg', '-y', '-f', 'lavfi',
                '-i', f'sine=frequency={freq}:duration={dur}',
                '-af', f'afade=t=in:d={fade_in},afade=t=out:st={dur - fade_out}:d={fade_out}',
                str(path)
            ]
            subprocess.run(cmd, capture_output=True, timeout=10)


def _date_natural(language='pt'):
    """Retorna a data atual em texto natural."""
    now = datetime.now()
    if language == 'pt':
        from .normalizer import _MESES_PT, _DIAS_SEMANA_PT
        from num2words import num2words
        dia_semana = _DIAS_SEMANA_PT[now.weekday()]
        dia = num2words(now.day, lang='pt_BR')
        mes = _MESES_PT[now.month]
        ano = num2words(now.year, lang='pt_BR')
        return f"{dia_semana}, {dia} de {mes} de {ano}"
    else:
        from .normalizer import _MONTHS_EN, _DAYS_EN
        from num2words import num2words
        day_name = _DAYS_EN[now.weekday()]
        day = num2words(now.day, lang='en', to='ordinal')
        month = _MONTHS_EN[now.month]
        year = num2words(now.year, lang='en')
        return f"{day_name}, {month} {day}, {year}"


def _ffmpeg_concat(file_list, output_path):
    """Concatena arquivos de áudio usando ffmpeg concat demuxer."""
    # Cria arquivo de lista para ffmpeg
    output_path = Path(output_path)
    concat_file = str(output_path) + '.txt'
    with open(concat_file, 'w') as f:
        for ftype, fpath in file_list:
            f.write(f"file '{fpath}'\n")

    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', concat_file,
        '-c:a', 'libmp3lame', '-b:a', '64k',
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)

    # Limpa arquivo temporário
    Path(concat_file).unlink(missing_ok=True)

    if result.returncode != 0:
        logger.error(f"ffmpeg erro: {result.stderr.decode()[:200]}")
        return False

    size = Path(output_path).stat().st_size
    logger.info(f"✅ Podcast: {output_path} ({size//1024}KB)")
    return True


def generate_podcast(feed_items, output_filename=None, language='pt'):
    """
    Gera podcast diário com intro, notícias por feed e outro.

    Args:
        feed_items: dict {feed_name: [(title, source, link, date), ...]}
        output_filename: nome do arquivo (ex: 'podcast_2026-06-20.mp3')
        language: 'pt' ou 'en'

    Returns:
        Path do arquivo MP3 ou None se falhar
    """
    _ensure_static_audio()

    if output_filename is None:
        output_filename = f"podcast_{datetime.now():%Y-%m-%d}.mp3"

    output_path = AUDIO_DIR / output_filename
    segments = []
    t = time.time()

    logger.info(f"🎧 Gerando podcast ({language.upper()}): {output_filename}")

    # 1. Intro musical
    if INTRO.exists():
        segments.append(("file", str(INTRO)))
        segments.append(("file", str(SILENCE_1S)))

    # 2. Saudação com data
    greeting = f"Bem-vindo ao Dublin Calling News. Hoje é {_date_natural(language)}."
    greet_path = generate_audio_file(greeting, "podcast_greeting.wav", language)
    if greet_path:
        segments.append(("file", greet_path))
        segments.append(("file", str(SILENCE_2S)))

    # 3. Notícias por feed
    for feed_name, items in feed_items.items():
        if not items:
            continue

        # Anuncia seção
        if language == 'pt':
            section = f"Notícias de {feed_name}."
        else:
            section = f"News from {feed_name}."
        section_path = generate_audio_file(section, f"podcast_section_{feed_name[:20]}.wav", language)
        if section_path:
            segments.append(("file", section_path))
            segments.append(("file", str(SILENCE_1S)))

        # Lê cada título
        for i, item in enumerate(items):
            title = item[0] if isinstance(item, (tuple, list)) else item.get('title', str(item))
            # Limpa o título para áudio (remove HTML, trunca se muito longo)
            title = str(title)[:150]
            title_path = generate_audio_file(title, f"podcast_{feed_name[:10]}_{i}.wav", language)
            if title_path:
                segments.append(("file", title_path))
                segments.append(("file", str(SILENCE_1S)))

    # 4. Encerramento
    if language == 'pt':
        closing = "Noticiário encerrado. Novas notícias em seis horas. Dublin Calling."
    else:
        closing = "That's all for now. More news in six hours. Dublin Calling."
    close_path = generate_audio_file(closing, "podcast_closing.wav", language)
    if close_path:
        segments.append(("file", close_path))
        segments.append(("file", str(SILENCE_1S)))

    # 5. Outro musical
    if OUTRO.exists():
        segments.append(("file", str(OUTRO)))

    # 6. Concatena
    if len(segments) < 3:
        logger.error("Poucos segmentos para podcast")
        return None

    success = _ffmpeg_concat(segments, output_path)
    elapsed = time.time() - t
    logger.info(f"  Podcast concluído em {elapsed:.1f}s")

    return output_path if success else None
