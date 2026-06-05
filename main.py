#!/usr/bin/env python3
"""
News Collector v3.0 — Consolidated Edition
===========================================
Baixa RSS feeds, sumariza, gera 1 áudio por feed, envia para Telegram.
Fluxo otimizado para Raspberry Pi (leve, cron-friendly, com histórico).

Uso:
    python main.py                    # Execução normal
    python main.py --feed 0           # Processa apenas o feed 0
    python main.py --dry-run          # Apenas coleta e mostra, sem enviar
"""

import argparse
import json
import logging
import os
import sys
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
    """Carrega histórico de títulos já processados."""
    if Config.HISTORY_FILE.exists():
        try:
            with open(Config.HISTORY_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []

def save_history(history):
    """Salva histórico, limitando ao máximo."""
    history = history[-Config.MAX_HISTORY:]
    Config.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(Config.HISTORY_FILE, 'w') as f:
        json.dump(history, f, ensure_ascii=False)

def is_duplicate(title, history):
    """Verifica se título já está no histórico (similaridade simples)."""
    clean = clean_html(title).strip().lower()[:80]
    for h in history:
        if clean in h.lower() or h.lower() in clean:
            return True
    return False

# ─── Limpeza de áudios antigos ────────────────────────────────────────────

def cleanup_old_audio():
    """Remove áudios com mais de RETENTION_DAYS dias."""
    import time as t
    now = t.time()
    cutoff = now - (Config.RETENTION_DAYS * 86400)
    removed = 0
    for f in Config.AUDIO_DIR.glob("*.wav"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
            removed += 1
    if removed:
        logger.info(f"🧹 Limpeza: {removed} áudios antigos removidos.")

# ─── Processamento de um feed → 1 resumo + 1 áudio + 1 mensagem ──────────

def process_feed(feed_config, dry_run=False):
    """
    Processa um feed RSS:
      1. Coleta notícias
      2. Filtra duplicatas (histórico)
      3. Gera resumo consolidado do feed
      4. Converte resumo em áudio (Piper TTS)
      5. Envia para Telegram como áudio com legenda
      6. Retorna lista de títulos novos para o histórico
    """
    url = feed_config.get('url')
    lang = feed_config.get('language', 'en')
    name = feed_config.get('name', url.split('/')[2] if '/' in url else url)

    logger.info(f"📰 Processando feed: {name} ({lang})")
    history = load_history()

    # 1. Coleta
    news_items = collect_feed_data(url, limit=Config.MAX_ITEMS_PER_FEED)
    if not news_items:
        logger.info(f"⏭️  Nenhuma notícia nova em: {name}")
        return []

    # 2. Filtra duplicatas e prepara texto consolidado
    new_titles = []
    consolidated_text = f"News from {name}.\n\n"

    for item in news_items:
        title = item['title']
        raw = item.get('raw_summary', '')
        link = item.get('link', '')

        if is_duplicate(title, history):
            logger.info(f"⏭️  Já processado: {title[:60]}...")
            continue

        summary = summarize_content(raw, language=lang)
        consolidated_text += f"{title}. {summary}\n\n"
        new_titles.append(title)
        logger.info(f"📖 + {title[:70]}...")

    if not new_titles:
        logger.info(f"✅ {name}: Nada novo.")
        return []

    logger.info(f"📝 {name}: {len(new_titles)} notícias novas para processar.")

    # 3. Gera um resumo geral do feed (se有很多 notícias)
    if len(new_titles) > 1:
        final_text = f"Today's headlines from {name}.\n\n"
        for i, title in enumerate(new_titles, 1):
            final_text += f"Story {i}: {title}.\n"
    else:
        final_text = consolidated_text

    # Limita o tamanho do texto para o áudio (Piper é rápido mas vamos ser gentis)
    if len(final_text) > Config.MAX_AUDIO_CHARS:
        final_text = final_text[:Config.MAX_AUDIO_CHARS] + "..."

    if dry_run:
        logger.info(f"🔍 [DRY-RUN] Simulação completa para {name}")
        logger.info(f"    Texto do áudio ({len(final_text)} chars):")
        for line in final_text.split('\n')[:5]:
            logger.info(f"    | {line.strip()}")
        logger.info(f"    Títulos: {new_titles}")
        return new_titles

    # 4. Gera áudio
    safe_name = "".join(c if c.isalnum() else "_" for c in name)[:30]
    audio_file = f"{safe_name}_{datetime.now():%Y%m%d}.wav"
    audio_path = generate_audio_file(final_text, audio_file, language=lang)

    if not audio_path:
        logger.error(f"❌ Falha ao gerar áudio para {name}")
        # Fallback: envia só a mensagem de texto
        msg = f"📰 *{name}*\n\n"
        for t in new_titles:
            msg += f"• {t}\n"
        msg += f"\n🤖 Gerado em {datetime.now():%d/%m/%Y %H:%M}"
        send_telegram_message(msg)
        return new_titles

    # 5. Monta legenda amigável
    caption = f"📰 *{name}*\n📅 {datetime.now():%d/%m/%Y}\n\n"
    for t in new_titles:
        # Limita título a 80 chars na legenda
        short = t[:80] + "..." if len(t) > 80 else t
        caption += f"▸ {short}\n"

    # Adiciona info no final
    caption += f"\n🎙️ {len(new_titles)} notícias | 🤖 NewsBot v3"

    # Limita a 1000 chars (limite do Telegram)
    if len(caption) > 1000:
        caption = caption[:997] + "..."

    # 6. Envia para Telegram
    sent = send_telegram_audio(audio_path, caption)
    if sent:
        logger.info(f"✅ {name}: Áudio + resumo enviados para Telegram!")
    else:
        logger.warning(f"⚠️  {name}: Falha no envio Telegram")

    return new_titles

# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="News Collector v3")
    parser.add_argument('--feed', type=int, default=None,
                        help='Processar apenas um feed específico (índice)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Apenas simular, não enviar nada')
    args = parser.parse_args()

    Config.setup_folders()
    logger.info("🚀 News Collector v3.0 iniciado")

    # Limpeza de áudios antigos (1x por execução)
    cleanup_old_audio()

    # Carrega feeds
    feeds = Config.load_feeds()
    if not feeds:
        logger.error("❌ Nenhum feed configurado em feeds_config.json")
        sys.exit(1)

    logger.info(f"📚 {len(feeds)} feeds carregados")

    all_new_titles = []
    for idx, feed in enumerate(feeds):
        if args.feed is not None and idx != args.feed:
            continue

        try:
            new_titles = process_feed(feed, dry_run=args.dry_run)
            all_new_titles.extend(new_titles)
            # Pequena pausa entre feeds
            if not args.dry_run and new_titles:
                time.sleep(3)
        except Exception as e:
            logger.error(f"❌ Erro no feed {idx}: {e}")
            continue

    # Atualiza histórico
    if all_new_titles:
        history = load_history()
        history.extend(all_new_titles)
        save_history(history)
        logger.info(f"💾 Histórico atualizado: {len(all_new_titles)} novos títulos")

    if not args.dry_run and all_new_titles:
        # Mensagem de resumo final
        summary = (f"✅ *NewsBot - Resumo*\n"
                   f"📰 {len(all_new_titles)} notícias de "
                   f"{len([f for f in feeds if args.feed is None or True])} feeds\n"
                   f"⏰ {datetime.now():%d/%m/%Y %H:%M}")
        send_telegram_message(summary)

    logger.info(f"🏁 Execução finalizada. {len(all_new_titles)} notícias novas.")


if __name__ == "__main__":
    main()
