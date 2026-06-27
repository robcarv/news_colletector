#!/usr/bin/env python3
"""
News Collector v3.1 — Audio por Idioma + Resumo Completo
=========================================================
- PT: edge-tts (voz natural AntonioNeural)
- EN: Piper (offline, rápido)
- Áudio: apenas headlines (curto e direto)
- Mensagem Telegram: resumo completo + links

Uso:
    python main.py                    # Execução normal
    python main.py --feed 0           # Processa apenas o feed 0
    python main.py --dry-run          # Apenas coleta e mostra, sem enviar
"""

import argparse
import gc
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from src.config import Config
from src.collector import collect_feed_data
from src.processor import summarize_content, clean_html
from src.audio import generate_audio_file
from src.notifier import send_telegram_audio, send_telegram_message, send_telegram_long_message

logger = logging.getLogger(__name__)

# ─── Histórico ─────────────────────────────────────────────────────────────

def load_history():
    if Config.HISTORY_FILE.exists():
        try:
            with open(Config.HISTORY_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []

def save_history(history):
    history = history[-Config.MAX_HISTORY:]
    Config.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(Config.HISTORY_FILE, 'w') as f:
        json.dump(history, f, ensure_ascii=False)

def is_duplicate(title, history):
    """Dedup por similaridade: compara titulos limpos (80 chars).
    
    So considera duplicata se:
    1. Titulos sao EXATAMENTE iguais (limpos), OU
    2. Overlap de palavras > 85% com diferenca de tamanho < 20%
    
    Evita falsos positivos como 'Tom Hardy' vs 'Tom Hardy Is Crossing Over...'
    """
    clean = clean_html(title).strip().lower()[:80]
    for h in history:
        h_title = h if isinstance(h, str) else h.get('title', '')
        h_clean = clean_html(h_title).strip().lower()[:80]
        # Exato
        if clean == h_clean:
            return True
        # Fuzzy: overlap de palavras significativo (>85%)
        # Tolerancia de tamanho: ate 50% de diferenca (titulo com/sem subtitulo)
        len_diff = abs(len(clean) - len(h_clean)) / max(len(clean), len(h_clean), 1)
        if len_diff < 0.5:
            words_a = set(clean.split())
            words_b = set(h_clean.split())
            if words_a and words_b:
                overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
                if overlap > 0.85:
                    return True
    return False

# ─── Limpeza ───────────────────────────────────────────────────────────────

def cleanup_old_audio():
    import time as t
    now = t.time()
    cutoff = now - (Config.RETENTION_DAYS * 86400)
    removed = 0
    for f in Config.AUDIO_DIR.glob("*.wav"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
            removed += 1
    if removed:
        logger.info(f"🧹 {removed} áudios antigos removidos.")

# ─── Processamento do feed ─────────────────────────────────────────────────

def process_feed(feed_config, dry_run=False, global_seen=None):
    """
    Processa um feed RSS:
      1. Coleta notícias
      2. Filtra duplicatas (historico + cross-feed)
      3. Gera:
         - Texto CURTO para áudio (só headlines)
         - Texto LONGO para Telegram (resumo + links)
      4. Gera áudio (edge-tts para PT, Piper para EN)
      5. Envia para Telegram: áudio + mensagem com resumo completo
    """
    url = feed_config.get('url')
    lang = feed_config.get('language', 'en')
    name = feed_config.get('name', url.split('/')[2] if '/' in url else url)

    logger.info(f"📰 Processando: {name} ({lang})")
    history = load_history()

    # 1. Coleta
    news_items = collect_feed_data(url, limit=Config.MAX_ITEMS_PER_FEED)
    if not news_items:
        logger.info(f"⏭️  {name}: sem notícias")
        return []

    # 2. Processa cada notícia
    new_items = []  # (title, summary, link, source, published, image)
    for item in news_items:
        title = item['title']
        raw = item.get('raw_summary', '')
        link = item.get('link', '')
        published = item.get('published_at', datetime.now())
        image = item.get('image', '')
        source = name

        if is_duplicate(title, history):
            logger.info(f"⏭️  Já vista: {title[:60]}...")
            continue

        # Cross-feed dedup: evita mesma noticia em BBC + Guardian
        title_key = clean_html(title).strip().lower()[:100]
        if global_seen is not None and title_key in global_seen:
            logger.info(f"⏭️  Cross-feed dup: {title[:60]}...")
            continue

        summary = summarize_content(raw, language=lang)
        new_items.append((title, summary, link, source, published, image))
        if global_seen is not None:
            global_seen.add(title_key)
        logger.info(f"📖 + {title[:70]}...")

    if not new_items:
        logger.info(f"✅ {name}: nada novo.")
        return []

    logger.info(f"📝 {name}: {len(new_items)} notícia(s) nova(s)")

    # ─── 3a. Texto para ÁUDIO (só headlines, curto) ───────────────
    # Double newlines dão pausa natural de ~0.8s entre notícias no Piper
    if lang == 'pt':
        audio_text = f"Notícias de {name}.\n\n"
        audio_text += "\n\n".join(f"{i}. {t}." for i, (t, s, l, src, pub, img) in enumerate(new_items, 1))
    else:
        audio_text = f"News from {name}.\n\n"
        audio_text += "\n\n".join(f"{i}. {t}." for i, (t, s, l, src, pub, img) in enumerate(new_items, 1))

    # Limita tamanho do áudio a ~2000 chars (cabe em ~1min)
    if len(audio_text) > Config.MAX_AUDIO_CHARS:
        audio_text = audio_text[:Config.MAX_AUDIO_CHARS] + "..."

    # ─── 3b. Texto para TELEGRAM (resumo completo, maior) ──────────
    if lang == 'pt':
        msg = f"📰 *{name}*\n📅 {datetime.now():%d/%m/%Y}\n━━━━━━━━━━━━━━\n\n"
    else:
        msg = f"📰 *{name}*\n📅 {datetime.now():%d/%m/%Y}\n━━━━━━━━━━━━━━\n\n"

    for i, (title, summary, link, src, pub, img) in enumerate(new_items, 1):
        # Título em negrito
        msg += f"**{i}. {title}**\n"
        # Resumo (se houver)
        if summary:
            # Limita resumo a ~400 chars por notícia
            short_summary = summary[:400] + "..." if len(summary) > 400 else summary
            msg += f"{short_summary}\n"
        # Link (se houver)
        if link:
            msg += f"[🔗 Ler mais]({link})\n"
        msg += "\n"

    # Rodapé
    total_news = len(new_items)
    if lang == 'pt':
        msg += f"━━━━━━━━━━━━━━\n🎧 Ouça o resumo no áudio acima\n🤖 NewsBot v3.1"
    else:
        msg += f"━━━━━━━━━━━━━━\n🎧 Listen to the summary above\n🤖 NewsBot v3.1"

    # Telegram limita caption a 1024 chars. Se passar, envia como mensagem separada
    caption_for_audio = msg
    if len(caption_for_audio) > 1000:
        caption_for_audio = msg[:997] + "..."

    if dry_run:
        logger.info(f"🔍 [DRY-RUN] {name}")
        logger.info(f"    Áudio ({len(audio_text)} chars): {audio_text[:150]}...")
        logger.info(f"    Mensagem ({len(msg)} chars): {len(new_items)} notícias")
        return [{'title': t, 'summary': s, 'link': l, 'source': src, 'date': pub.isoformat() if hasattr(pub, 'isoformat') else str(pub), 'image': img} for t, s, l, src, pub, img in new_items]

    # ─── 4. Gera áudio (só headlines) ──────────────────────────────
    safe_name = "".join(c if c.isalnum() else "_" for c in name)[:30]
    audio_file = f"{safe_name}_{datetime.now():%Y%m%d}.wav"
    audio_path = generate_audio_file(audio_text, audio_file, language=lang, force=True)

    # ─── 5. Envia para Telegram ────────────────────────────────────
    if audio_path:
        # Áudio + legenda curta (headlines)
        sent = send_telegram_audio(audio_path, caption_for_audio)
        if sent:
            logger.info(f"✅ {name}: áudio enviado!")
        else:
            logger.warning(f"⚠️  {name}: áudio não enviado")
            # Fallback: envia só texto (split se longo)
            send_telegram_long_message(msg)
            return [{'title': t, 'summary': s, 'link': l, 'source': src, 'date': pub.isoformat() if hasattr(pub, 'isoformat') else str(pub), 'image': img} for t, s, l, src, pub, img in new_items]
    else:
        logger.warning(f"⚠️  {name}: sem áudio, enviando só texto")
        send_telegram_long_message(msg)
        return [{'title': t, 'summary': s, 'link': l, 'source': src, 'date': pub.isoformat() if hasattr(pub, 'isoformat') else str(pub), 'image': img} for t, s, l, src, pub, img in new_items]

    # Se a mensagem for maior que 1000 chars, envia o texto completo separadamente
    if len(msg) > 1000:
        # Envia o texto completo como mensagem (split automatico se >4000)
        send_telegram_long_message(msg)
        logger.info(f"📝 {name}: texto completo enviado ({len(msg)} chars)")

    return [{'title': t, 'summary': s, 'link': l, 'source': src, 'date': pub.isoformat() if hasattr(pub, 'isoformat') else str(pub), 'image': img} for t, s, l, src, pub, img in new_items]


# ─── Main ─────────────────────────────────────────────────────────────────

def _generate_jingle(lang_feeds, all_feeds, language):
    """Gera jingle de ~10 minutos — notícias completas com resumos, pausas naturais."""
    try:
        from datetime import datetime
        import tempfile, shutil

        if not lang_feeds:
            return

        # Coleta todas as notícias com resumo
        items = []
        seen = set()
        for name, feed_items in lang_feeds.items():
            for item in feed_items:
                title = item.get('title', '') if isinstance(item, dict) else str(item[0])
                summary = item.get('summary', '') if isinstance(item, dict) else ''
                if not title or title in seen:
                    continue
                seen.add(title)
                clean_title = title.strip().rstrip('.')
                short = name.replace(' (Brasil)', '').replace(' (US)', '').replace(' (UK)', '').replace(' (Ireland)', '').replace('Brasil ', '').strip()
                items.append((clean_title, short, summary))

        if not items:
            return

        hora = datetime.now().hour
        is_pt = language == 'pt'

        # Saudações
        if is_pt:
            saudacao = "Boa noite" if hora >= 18 or hora < 6 else "Boa tarde" if hora >= 12 else "Bom dia"
            flag = "do Brasil"
            target_chars = 8000  # ~10 minutos em PT (~13 chars/s)
        else:
            saudacao = "Good evening" if hora >= 18 or hora < 6 else "Good afternoon" if hora >= 12 else "Good morning"
            flag = "from around the world"
            target_chars = 9000  # ~10 minutos em EN (~15 chars/s)

        tmp_dir = Path(tempfile.mkdtemp(prefix=f"jingle_{language}_"))
        audio_files = []

        # ── "Dublin Calling" (GB) ──
        dc_path = tmp_dir / "00_dc.wav"
        if not generate_audio_file("Dublin Calling.", str(dc_path), "gb", force=True):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        # ── Intro ──
        intro_text = f"Este é o Dublin Calling. Notícias {flag}. {saudacao}." if is_pt else f"This is Dublin Calling. News {flag}. {saudacao}."
        p = tmp_dir / "01_intro.wav"
        if generate_audio_file(intro_text, str(p), language, force=True):
            audio_files.append((language, p))
            audio_files.append(("dc", dc_path))

        # ── Blocos de notícias (~60-90s cada, com resumos) ──
        # Constrói texto rico: "Fonte. Título. Resumo de 2-3 frases."
        all_lines = []
        for title, source, summary in items:
            line = f"{source}. {title}."
            if summary and len(summary) > 30:
                # Limpa e trunca resumo para ~200 chars (2-3 frases)
                clean_summary = summary.strip().rstrip('.')
                if len(clean_summary) > 250:
                    clean_summary = clean_summary[:250].rsplit('.', 1)[0] + "."
                line += f" {clean_summary}"
            all_lines.append(line)

        # Divide em blocos de ~1000 chars (~60s cada)
        block_size = 1000
        blocks = []
        current_block = []
        current_len = 0

        for line in all_lines:
            line_len = len(line) + 2  # +2 for ". " separator
            if current_len + line_len > block_size and current_block:
                blocks.append(" ".join(current_block))
                current_block = []
                current_len = 0
            current_block.append(line)
            current_len += line_len

        if current_block:
            blocks.append(" ".join(current_block))

        # Se ainda não atingiu ~10 min, duplica alguns itens com "Em outras notícias..."
        total_chars = sum(len(b) for b in blocks)
        filler_idx = 0
        while total_chars < target_chars and len(items) > 2:
            # Adiciona bloco extra com as mesmas notícias mas fraseado diferente
            if is_pt:
                extra = "Em resumo. " + " ".join(f"{s}. {t}." for t, s, _ in items[min(filler_idx, len(items)-3):min(filler_idx+3, len(items))])
            else:
                extra = "In summary. " + " ".join(f"{s}. {t}." for t, s, _ in items[min(filler_idx, len(items)-3):min(filler_idx+3, len(items))])
            blocks.append(extra)
            total_chars += len(extra)
            filler_idx = (filler_idx + 2) % max(1, len(items) - 2)
            if len(blocks) > 15:  # safety
                break

        # ── Silencios (gerados antes dos blocos para fallback) ──
        for dur, name in [(1.5, "s15"), (0.8, "s08"), (0.5, "s05")]:
            out = tmp_dir / f"{name}.wav"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                           "-t", str(dur), str(out)], capture_output=True)

        sl15 = tmp_dir / "s15.wav"
        sl08 = tmp_dir / "s08.wav"
        sl05 = tmp_dir / "s05.wav"

        # Gera áudio para cada bloco com retry
        for i, block_text in enumerate(blocks):
            p = tmp_dir / f"block_{i:02d}.wav"
            success = generate_audio_file(block_text, str(p), language, force=True)
            if not success:
                logger.warning(f"  Bloco {i} TTS falhou, retrying...")
                success = generate_audio_file(block_text, str(p), language, force=True)
            if success:
                audio_files.append((language, p))
            else:
                logger.warning(f"  Bloco {i} ignorado apos falha de TTS")
                # Adiciona silencio para nao quebrar o fluxo
                audio_files.append(("silence", sl08))

        # ── Outro ──
        outro_text = "Essas foram as notícias. A sua rádio. Mais notícias em seis horas." if is_pt else "Those were the latest news. Your radio station. More news in six hours."
        p = tmp_dir / f"outro.wav"
        if generate_audio_file(outro_text, str(p), language, force=True):
            audio_files.append((language, p))
            audio_files.append(("dc", dc_path))

        if len(audio_files) < 3:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        total_items = len(items)
        logger.info(f"  Jingle {language.upper()}: {total_items} notícias → {len(blocks)} blocos → {len(audio_files)} segmentos")

        # ── Concatena ──
        # Silencios ja foram gerados antes do loop de blocos
        concat_list = tmp_dir / "concat.txt"
        with open(concat_list, "w") as f:
            for i, (tag, af) in enumerate(audio_files):
                f.write(f"file '{af}'\n")
                if i < len(audio_files) - 1:
                    next_tag = audio_files[i + 1][0]
                    if tag == "dc" or next_tag == "dc":
                        f.write(f"file '{sl05}'\n")
                    elif tag == next_tag:
                        # Blocos do mesmo idioma: pausa de 1.5s entre blocos
                        f.write(f"file '{sl15}'\n")
                    else:
                        f.write(f"file '{sl15}'\n")

        jingle_wav = Config.AUDIO_DIR / f"news_jingle_{language}.wav"
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-ac", "1", "-ar", "22050", str(jingle_wav)],
            capture_output=True, timeout=120
        )

        if result.returncode != 0:
            logger.error(f"Ffmpeg concat erro: {result.stderr.decode()[-200:]}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        size_kb = jingle_wav.stat().st_size // 1024
        dur = float(subprocess.run(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                   '-of', 'csv=p=0', str(jingle_wav)], capture_output=True, text=True).stdout.strip() or 0)
        minutes = int(dur // 60)
        seconds = int(dur % 60)
        logger.info(f"  ✅ Jingle {language.upper()}: {size_kb}KB, {minutes}:{seconds:02d}")

        shutil.rmtree(tmp_dir, ignore_errors=True)

        # Upload
        from src.azuracast_news import upload_jingle
        jingle_filename = f"news_jingle_{language}.mp3"
        if upload_jingle(str(jingle_wav), filename=jingle_filename):
            from src.notifier import send_telegram_message
            send_telegram_message(f"📻 *News na rádio!* Jingle {language.upper()} com {total_items} notícias ({minutes}min)")
        
        # Compatibilidade: PT também sobe como news_jingle.mp3 (playlist legada)
        if language == 'pt':
            upload_jingle(str(jingle_wav), filename="news_jingle.mp3")
    except Exception as e:
        logger.warning(f"Jingle {language}: {e}", exc_info=True)



def _generate_azuracast_jingle(podcast_feeds, feeds):
    """Gera jingle bilíngue (legado — substituído por _generate_jingle por idioma)."""
    # Divide por idioma e gera separadamente
    pt_feeds = {k: v for k, v in podcast_feeds.items()
                if any(f.get('language') == 'pt' for f in feeds if f.get('name') == k)}
    en_feeds = {k: v for k, v in podcast_feeds.items()
                if any(f.get('language') == 'en' for f in feeds if f.get('name') == k)}

    if pt_feeds:
        _generate_jingle(pt_feeds, feeds, 'pt')
    if en_feeds:
        _generate_jingle(en_feeds, feeds, 'en')


def main():
    parser = argparse.ArgumentParser(description="News Collector v4")
    parser.add_argument('--feed', type=int, default=None,
                        help='Processar apenas um feed (índice)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Apenas simular')
    parser.add_argument('--podcast', action='store_true',
                        help='Gerar podcast diário com todas as notícias')
    args = parser.parse_args()

    Config.setup_folders()
    logger.info("🚀 News Collector v4 iniciado")

    # Alerta no celular: notificação Telegram de início
    if not args.dry_run:
        hora = datetime.now().strftime('%H:%M')
        emoji = {0: '🌅', 6: '🌤️', 12: '☀️', 18: '🌆'}.get(datetime.now().hour, '🔔')
        send_telegram_message(f"{emoji} *NewsBot iniciando* — coletando notícias... _{hora}_")

    cleanup_old_audio()

    feeds = Config.load_feeds()
    if not feeds:
        logger.error("❌ Nenhum feed configurado")
        sys.exit(1)

    logger.info(f"📚 {len(feeds)} feeds carregados")

    all_new_titles = []
    global_seen_titles = set()  # cross-feed dedup pool
    podcast_feeds = {}  # {feed_name: [items]} para podcast
    
    # Health tracking
    stats = {'feeds_ok': 0, 'feeds_fail': 0, 'feeds_empty': 0, 'start': time.time()}
    
    for idx, feed in enumerate(feeds):
        if args.feed is not None and idx != args.feed:
            continue
        try:
            new_titles = process_feed(feed, dry_run=args.dry_run, global_seen=global_seen_titles)
            if new_titles:
                stats['feeds_ok'] += 1
            else:
                stats['feeds_empty'] += 1
            all_new_titles.extend(new_titles)
            if new_titles:
                podcast_feeds[feed.get('name', f'feed_{idx}')] = new_titles
            if not args.dry_run and new_titles:
                time.sleep(2)
            if idx > 0 and idx % Config.GC_INTERVAL == 0:
                collected = gc.collect()
                logger.debug(f"🧹 GC: {collected} objetos coletados após feed {idx}")
        except Exception as e:
            logger.error(f"❌ Erro no feed {idx}: {e}")
            stats['feeds_fail'] += 1
            continue

    # Histórico
    if all_new_titles:
        history = load_history()
        history.extend(all_new_titles)
        save_history(history)
        logger.info(f"💾 Histórico: {len(all_new_titles)} novos títulos")

    # Resumo final (só se enviou algo)
    if not args.dry_run and all_new_titles:
        # Conta quantos feeds com notícias
        feed_count = len([f for f in feeds if args.feed is None or f == feeds[args.feed]])
        summary = (f"✅ *NewsBot - Resumo do Dia*\n"
                   f"📰 {len(all_new_titles)} notícias de {len(feeds)} feeds\n"
                   f"⏰ {datetime.now():%d/%m/%Y %H:%M}")
        send_telegram_message(summary)
        logger.info(f"📊 Resumo enviado: {len(all_new_titles)} notícias")

    # Podcast diario (se flag --podcast)
    if args.podcast and podcast_feeds and not args.dry_run:
        try:
            from src.podcast import generate_podcast
            for lang in ['pt', 'en']:
                lang_feeds = {k: v for k, v in podcast_feeds.items() 
                             if any(f.get('language') == lang for f in feeds if f.get('name') == k)}
                if lang_feeds:
                    podcast_path = generate_podcast(lang_feeds, language=lang)
                    if podcast_path:
                        logger.info(f"Podcast {lang.upper()}: {podcast_path}")
        except Exception as e:
            logger.warning(f"Podcast nao gerado: {e}")

    # Jingle para AzuraCast (news na radio) — todos os runs
    if podcast_feeds and not args.dry_run:
        _generate_azuracast_jingle(podcast_feeds, feeds)

    # Health report
    elapsed = time.time() - stats['start']
    feeds_processed = stats['feeds_ok'] + stats['feeds_fail'] + stats['feeds_empty']
    health_msg = (
        f"📊 *NewsBot Health*\n"
        f"✅ {stats['feeds_ok']} feeds com notícias\n"
        f"⏭️ {stats['feeds_empty']} feeds vazios\n"
        f"❌ {stats['feeds_fail']} falhas\n"
        f"📰 {len(all_new_titles)} notícias novas\n"
        f"⏱️ {elapsed:.0f}s ({feeds_processed} feeds)"
    )
    if not args.dry_run:
        send_telegram_message(health_msg)
    logger.info(f"📊 Health: {stats['feeds_ok']}ok/{stats['feeds_empty']}vazios/{stats['feeds_fail']}falha — {elapsed:.0f}s")
    logger.info(f"Finalizado. {len(all_new_titles)} noticias novas.")


if __name__ == "__main__":
    main()
