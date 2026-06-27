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
    wav_name = f"{safe_name}.wav"
    mp3_name = f"{safe_name}.mp3"
    wav_path = generate_audio_file(audio_text, wav_name, language=lang, force=True)
    
    # Converte WAV → MP3 (64kbps mono, ~10x menor)
    mp3_path = None
    if wav_path:
        mp3_full = Config.AUDIO_DIR / mp3_name
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-ac", "1", "-b:a", "64k", str(mp3_full)],
            capture_output=True, timeout=15
        )
        if result.returncode == 0 and mp3_full.exists():
            mp3_path = str(mp3_full)
            # Remove WAV (so usa MP3)
            try:
                Path(wav_path).unlink(missing_ok=True)
            except Exception:
                pass
        else:
            mp3_path = wav_path  # fallback: usa WAV se ffmpeg falhar
            logger.warning("ffmpeg WAV→MP3 falhou, usando WAV")

    # ─── 4b. Copia para Samba (radio) ──────────────────────────────
    if mp3_path and not dry_run:
        try:
            samba_target = f"robert@pi5:/mnt/radio_hdd/news_jingles/{mp3_name}"
            subprocess.run(["scp", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                    mp3_path, samba_target],
                   capture_output=True, timeout=15)
            logger.info(f"📻 Copia Samba: {mp3_name}")
        except Exception:
            pass  # Pi5 offline — nao critico

    # ─── 5. Envia para Telegram ────────────────────────────────────
    audio_path = mp3_path or wav_path
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

def export_run_json(all_new_titles, feeds):
    if not all_new_titles:
        return
    from datetime import timezone
    from pathlib import Path
    
    now_iso = datetime.now(timezone.utc).astimezone().isoformat()
    pt_items = []
    en_items = []
    
    # Build feed language lookup
    feed_lang = {f.get('name', ''): f.get('language', 'en') for f in feeds}
    
    for item in all_new_titles:
        if isinstance(item, dict):
            lang = feed_lang.get(item.get('source', ''), 'en')
            entry = {
                'title': item.get('title', ''),
                'summary': item.get('summary', ''),
                'link': item.get('link', ''),
                'source': item.get('source', ''),
                'date': item.get('date', '')
            }
            if lang == 'pt':
                pt_items.append(entry)
            else:
                en_items.append(entry)
    
    output = {
        'updated': now_iso,
        'total_pt': len(pt_items),
        'total_en': len(en_items),
        'pt': pt_items,
        'en': en_items
    }
    
    # Write to repo root
    run_json = Config.BASE_DIR / 'news_run.json'
    with open(run_json, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Also copy to portfolio directory
    portfolio_json = Path('/home/robert/Documents/portfolio-html/news.json')
    try:
        portfolio_json.parent.mkdir(parents=True, exist_ok=True)
        with open(portfolio_json, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        logger.info(f"📰 news_run.json exportado: {len(pt_items)} PT + {len(en_items)} EN → portfolio")
    except Exception:
        logger.info(f"📰 news_run.json exportado: {len(pt_items)} PT + {len(en_items)} EN")


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

    # Jingle removido — audios de feed vao direto para Samba via process_feed()

    # Exporta news_run.json com noticias do run atual (PT + EN separados)
    export_run_json(all_new_titles, feeds)

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
