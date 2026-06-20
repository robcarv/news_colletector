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
import sys
import time
from datetime import datetime

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
    if lang == 'pt':
        audio_text = f"Notícias de {name}.\n\n"
        audio_text += "\\n".join(f"{i}. {t}" for i, (t, s, l, src, pub, img) in enumerate(new_items, 1))
    else:
        audio_text = f"News from {name}.\\n\\n"
        audio_text += "\\n".join(f"{i}. {t}" for i, (t, s, l, src, pub, img) in enumerate(new_items, 1))

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
    """Gera boletim jornalístico natural — estilo telejornal, com todas as notícias."""
    try:
        # Agrupa notícias por região/categoria com fonte
        groups = {
            "Brasil": [],
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
            "IBM": "Tecnologia",
            "Nintendo": "Tecnologia",
            "The Guardian Tech": "Tecnologia",
            "The Guardian US": "Estados Unidos",
        }

        for name, items in podcast_feeds.items():
            for item in items:
                title = item.get('title', '') if isinstance(item, dict) else str(item[0])
                summary = item.get('summary', '') if isinstance(item, dict) else ''
                if not title or title in seen:
                    continue
                seen.add(title)
                group = feed_groups.get(name, "Internacional")
                # Limpa o título para leitura natural
                clean_title = title.strip().rstrip('.')
                groups[group].append((clean_title, name, summary))

        # Conta total
        total = sum(len(v) for v in groups.values())
        if total == 0:
            return

        # Monta o boletim no estilo telejornal
        from datetime import datetime
        hora = datetime.now().hour
        saudacao = "Boa noite" if hora >= 18 or hora < 6 else "Boa tarde" if hora >= 12 else "Bom dia"

        lines = []
        lines.append(f"Este é o Dublin Calling. Notícias da música, tecnologia e cultura. {saudacao}.")

        # Cada grupo vira uma seção do noticiário
        section_intros = {
            "Brasil": "No Brasil",
            "Irlanda": "Na Irlanda",
            "Reino Unido": "No Reino Unido",
            "Estados Unidos": "Nos Estados Unidos",
            "Tecnologia": "Em tecnologia",
        }

        for group_name, items in groups.items():
            if not items:
                continue
            lines.append(f"{section_intros[group_name]}.")
            for title, source, summary in items:
                # Simplifica nome da fonte
                short = source.replace(' (Brasil)', '').replace(' (US)', '').replace(' (UK)', '').replace(' (Ireland)', '').replace('Brasil ', '').strip()
                # Formato: "Fonte: notícia."
                if short in title[:30]:
                    # Se o título já começa com a fonte, só lê o título
                    lines.append(f"{title}.")
                else:
                    lines.append(f"{short}. {title}.")
                # Inclui resumo se disponível e curto
                if summary and len(summary) < 120:
                    lines.append(f"{summary}.")

        lines.append("Essas foram as notícias da última hora. Dublin Calling, a sua rádio. Mais notícias em seis horas.")

        jingle_text = " ".join(lines)

        # Limita a ~90 segundos (~4000 chars no Piper PT)
        max_chars = 4000
        if len(jingle_text) > max_chars:
            # Trunca inteligentemente: remove grupos do fim até caber
            while len(jingle_text) > max_chars:
                # Remove o último grupo que ainda tem itens
                for rev_group in reversed(list(groups.keys())):
                    if groups[rev_group] and len(groups[rev_group]) > 1:
                        groups[rev_group].pop()
                        break
                # Reconstrói
                lines = [f"Este é o Dublin Calling. Notícias da música, tecnologia e cultura. {saudacao}."]
                for gn, its in groups.items():
                    if not its:
                        continue
                    lines.append(f"{section_intros[gn]}.")
                    for title, source, summary in its:
                        short = source.replace(' (Brasil)', '').replace(' (US)', '').replace(' (UK)', '').replace(' (Ireland)', '').replace('Brasil ', '').strip()
                        if short in title[:30]:
                            lines.append(f"{title}.")
                        else:
                            lines.append(f"{short}. {title}.")
                        if summary and len(summary) < 120:
                            lines.append(f"{summary}.")
                lines.append("Essas foram as notícias da última hora. Dublin Calling, a sua rádio. Mais notícias em seis horas.")
                jingle_text = " ".join(lines)

        total_incluidas = sum(len(v) for v in groups.values())

        # Gera áudio (force=True para ignorar cache e sempre usar o texto mais recente)
        logger.info(f"  Boletim: {total_incluidas} notícias de {total} totais, {len(jingle_text)} chars (~{len(jingle_text)//60}s)")
        jingle_path = generate_audio_file(jingle_text, "news_jingle.wav", "pt", force=True)
        if not jingle_path:
            logger.warning("Jingle audio nao gerado")
            return

        logger.info(f"  Jingle texto: {jingle_text[:200]}...")

        # Upload para AzuraCast
        from src.azuracast_news import upload_jingle
        if upload_jingle(jingle_path):
            logger.info("Boletim enviado para AzuraCast")
            from src.notifier import send_telegram_message
            send_telegram_message(f"📻 *News na rádio!* Boletim com {total_incluidas} notícias — tocando na Dublin Calling a cada 30min")
        else:
            logger.info("Boletim gerado mas upload pulado (sem API key?)")
    except Exception as e:
        logger.warning(f"Jingle AzuraCast: {e}")


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
