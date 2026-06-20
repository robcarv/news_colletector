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
from src.notifier import send_telegram_audio, send_telegram_message

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
    clean = clean_html(title).strip().lower()[:80]
    for h in history:
        h_title = h if isinstance(h, str) else h.get('title', '')
        if clean in h_title.lower() or h_title.lower() in clean:
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

def process_feed(feed_config, dry_run=False):
    """
    Processa um feed RSS:
      1. Coleta notícias
      2. Filtra duplicatas
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

        summary = summarize_content(raw, language=lang)
        new_items.append((title, summary, link, source, published, image))
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
    audio_path = generate_audio_file(audio_text, audio_file, language=lang)

    # ─── 5. Envia para Telegram ────────────────────────────────────
    if audio_path:
        # Áudio + legenda curta (headlines)
        sent = send_telegram_audio(audio_path, caption_for_audio)
        if sent:
            logger.info(f"✅ {name}: áudio enviado!")
        else:
            logger.warning(f"⚠️  {name}: áudio não enviado")
            # Fallback: envia só texto
            if len(msg) > 1000:
                send_telegram_message(msg[:4000])
            return [{'title': t, 'summary': s, 'link': l, 'source': src, 'date': pub.isoformat() if hasattr(pub, 'isoformat') else str(pub), 'image': img} for t, s, l, src, pub, img in new_items]
    else:
        logger.warning(f"⚠️  {name}: sem áudio, enviando só texto")
        if len(msg) > 1000:
            send_telegram_message(msg[:4000])
        return [{'title': t, 'summary': s, 'link': l, 'source': src, 'date': pub.isoformat() if hasattr(pub, 'isoformat') else str(pub), 'image': img} for t, s, l, src, pub, img in new_items]

    # Se a mensagem for maior que 1000 chars, envia o texto completo separadamente
    if len(msg) > 1000 and len(msg) <= 4000:
        # Envia o texto completo como mensagem de texto
        send_telegram_message(msg)
        logger.info(f"📝 {name}: texto completo enviado ({len(msg)} chars)")

    return [{'title': t, 'summary': s, 'link': l, 'source': src, 'date': pub.isoformat() if hasattr(pub, 'isoformat') else str(pub), 'image': img} for t, s, l, src, pub, img in new_items]


# ─── Main ─────────────────────────────────────────────────────────────────

def _generate_azuracast_jingle(podcast_feeds, feeds):
    """Gera boletim bilíngue natural — PT para Brasil, EN para internacional, com pausas."""
    try:
        from datetime import datetime
        import tempfile
        import shutil

        # Agrupa notícias por região/categoria com fonte
        pt_groups = {"Brasil": []}
        en_groups = {
            "Irlanda": [],
            "Reino Unido": [],
            "Estados Unidos": [],
            "Tecnologia": [],
        }
        seen = set()

        # Mapeia cada feed para seu grupo
        feed_groups = {
            "Folha de S.Paulo": "Brasil",
            "Tenho Mais Discos Que Amigos (Brasil)": "Brasil",
            "RockBizz (Brasil)": "Brasil",
            "Rolling Stone Brasil": "Brasil",
            "Correio Braziliense (Brasil)": "Brasil",
            "Jornal do Commercio (Brasil)": "Brasil",
            "UOL (Brasil)": "Brasil",
            "Estado de Minas (Brasil)": "Brasil",
            "O Tempo (Brasil)": "Brasil",
            "Diário de Pernambuco (Brasil)": "Brasil",
            "Irish Independent": "Irlanda",
            "Hot Press (Ireland)": "Irlanda",
            "GoldenPlec (Ireland Music)": "Irlanda",
            "Dublin Live News": "Irlanda",
            "Irish News Entertainment": "Irlanda",
            "BBC News": "Reino Unido",
            "The Guardian UK": "Reino Unido",
            "NME Music (UK)": "Reino Unido",
            "MusicRadar (UK)": "Reino Unido",
            "NME News (UK)": "Reino Unido",
            "Pitchfork": "Estados Unidos",
            "Rolling Stone Music (US)": "Estados Unidos",
            "Consequence of Sound (US)": "Estados Unidos",
            "Billboard (US)": "Estados Unidos",
            "Stereogum (US)": "Estados Unidos",
            "BrooklynVegan (US)": "Estados Unidos",
            "Loudwire (US)": "Estados Unidos",
            "Spin Magazine (US)": "Estados Unidos",
            "Metal Injection": "Estados Unidos",
            "The Guardian US": "Estados Unidos",
            "IBM": "Tecnologia",
            "Nintendo": "Tecnologia",
            "The Guardian Tech": "Tecnologia",
            "TechCrunch": "Tecnologia",
            "Ars Technica": "Tecnologia",
        }

        for name, items in podcast_feeds.items():
            for item in items:
                title = item.get('title', '') if isinstance(item, dict) else str(item[0])
                if not title or title in seen:
                    continue
                seen.add(title)
                group = feed_groups.get(name, "Estados Unidos")  # default EN
                clean_title = title.strip().rstrip('.')
                # Decide se vai pra PT ou EN
                if group == "Brasil":
                    pt_groups["Brasil"].append((clean_title, name))
                else:
                    en_groups.setdefault(group, []).append((clean_title, name))

        total = sum(len(v) for v in pt_groups.values()) + sum(len(v) for v in en_groups.values())
        if total == 0:
            return

        hora = datetime.now().hour
        saudacao_pt = "Boa noite" if hora >= 18 or hora < 6 else "Boa tarde" if hora >= 12 else "Bom dia"
        # EN greeting adapts to time of day
        greeting_en = "Good evening" if hora >= 18 or hora < 6 else "Good afternoon" if hora >= 12 else "Good morning"

        section_intros_pt = {"Brasil": "No Brasil"}
        section_intros_en = {
            "Irlanda": "In Ireland",
            "Reino Unido": "In the United Kingdom",
            "Estados Unidos": "In the United States",
            "Tecnologia": "In technology",
        }

        # ─── Segmento 1: INTRO (PT) ───────────────────────────────────
        intro_pt = f"Este é o Dublin Calling. Notícias da música, tecnologia e cultura. {saudacao_pt}."
        
        # ─── Segmento 2: BRASIL (PT) ──────────────────────────────────
        brasil_lines = []
        if pt_groups["Brasil"]:
            brasil_lines.append("No Brasil.")
            for title, source in pt_groups["Brasil"][:6]:  # max 6 BR
                short = source.replace(' (Brasil)', '').replace('Brasil ', '').strip()
                brasil_lines.append(f"{short}. {title}.")

        # ─── Segmento 3: INTERNACIONAL (EN) ───────────────────────────
        en_lines = []
        section_order = ["Irlanda", "Reino Unido", "Estados Unidos", "Tecnologia"]
        for group_name in section_order:
            items = en_groups.get(group_name, [])
            if not items:
                continue
            intro = section_intros_en.get(group_name, group_name)
            en_lines.append(f"{intro}.")
            for title, source in items:
                short = source.replace(' (Ireland)', '').replace(' (UK)', '').replace(' (US)', '').strip()
                en_lines.append(f"{short}. {title}.")

        # ─── Segmento 4: OUTRO (PT) ───────────────────────────────────
        outro_pt = "Essas foram as notícias da última hora. Dublin Calling, a sua rádio. Mais notícias em seis horas."

        # Limita tamanho dos segmentos (máx ~60s cada)
        brasil_text = " ".join(brasil_lines) if brasil_lines else ""
        en_text = " ".join(en_lines) if en_lines else ""
        
        max_seg = 2500
        if len(brasil_text) > max_seg:
            brasil_text = brasil_text[:max_seg].rsplit('.', 1)[0] + "."
        if len(en_text) > max_seg:
            en_text = en_text[:max_seg].rsplit('.', 1)[0] + "."

        # ─── Gera áudios separados ────────────────────────────────────
        tmp_dir = Path(tempfile.mkdtemp(prefix="jingle_"))
        audio_files = []  # lista de paths na ordem
        
        # 1. Intro PT
        p = tmp_dir / "01_intro.wav"
        if generate_audio_file(intro_pt, str(p), "pt", force=True):
            audio_files.append(p)
        
        # 2. Brasil PT
        if brasil_text:
            p = tmp_dir / "02_brasil.wav"
            if generate_audio_file(brasil_text, str(p), "pt", force=True):
                audio_files.append(p)
        
        # 3. Internacional EN
        if en_text:
            p = tmp_dir / "03_internacional.wav"
            if generate_audio_file(en_text, str(p), "en", force=True):
                audio_files.append(p)
        
        # 4. Outro PT
        p = tmp_dir / "04_outro.wav"
        if generate_audio_file(outro_pt, str(p), "pt", force=True):
            audio_files.append(p)

        if len(audio_files) < 2:
            logger.warning("Jingle: poucos segmentos gerados, abortando")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        logger.info(f"  Boletim bilíngue: {total} notícias → {len(audio_files)} segmentos de áudio")
        
        # ─── Concatena com pausas (ffmpeg) ────────────────────────────
        # Gera silêncio de 1.5s e 0.8s
        silence_long = tmp_dir / "silence_1.5s.wav"
        silence_short = tmp_dir / "silence_0.8s.wav"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", 
                        "-t", "1.5", str(silence_long)], capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", 
                        "-t", "0.8", str(silence_short)], capture_output=True)
        
        # Concatena todos: segmento + silêncio longo entre grupos
        concat_list = tmp_dir / "concat.txt"
        with open(concat_list, "w") as f:
            for i, af in enumerate(audio_files):
                f.write(f"file '{af}'\n")
                if i < len(audio_files) - 1:
                    # Silêncio longo entre grupos de idioma diferente
                    f.write(f"file '{silence_long}'\n")
        
        jingle_wav = Config.AUDIO_DIR / "news_jingle.wav"
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-ac", "1", "-ar", "22050", str(jingle_wav)],
            capture_output=True, timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"Ffmpeg concat erro: {result.stderr.decode()[-300:]}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return
        
        jingle_size = jingle_wav.stat().st_size if jingle_wav.exists() else 0
        logger.info(f"  ✅ Jingle bilíngue: {jingle_size//1024}KB")
        
        # Limpa temporários
        shutil.rmtree(tmp_dir, ignore_errors=True)

        # Upload para AzuraCast
        from src.azuracast_news import upload_jingle
        if upload_jingle(str(jingle_wav)):
            logger.info("Boletim enviado para AzuraCast")
            from src.notifier import send_telegram_message
            send_telegram_message(f"📻 *News na rádio!* Boletim bilíngue com {total} notícias — tocando na Dublin Calling a cada 30min")
        else:
            logger.info("Boletim gerado mas upload pulado (sem API key?)")
    except Exception as e:
        logger.warning(f"Jingle AzuraCast: {e}", exc_info=True)


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
    podcast_feeds = {}  # {feed_name: [items]} para podcast
    for idx, feed in enumerate(feeds):
        if args.feed is not None and idx != args.feed:
            continue
        try:
            new_titles = process_feed(feed, dry_run=args.dry_run)
            all_new_titles.extend(new_titles)
            if new_titles:
                podcast_feeds[feed.get('name', f'feed_{idx}')] = new_titles
            if not args.dry_run and new_titles:
                time.sleep(2)  # pausa reduzida de 3s para 2s
            # Garbage collection periódico para não acumular memória
            if idx > 0 and idx % Config.GC_INTERVAL == 0:
                collected = gc.collect()
                logger.debug(f"🧹 GC: {collected} objetos coletados após feed {idx}")
        except Exception as e:
            logger.error(f"❌ Erro no feed {idx}: {e}")
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

    logger.info(f"Finalizado. {len(all_new_titles)} noticias novas.")


if __name__ == "__main__":
    main()
