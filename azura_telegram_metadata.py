#!/usr/bin/env python3
"""
AzuraCast Metadata Enricher + Telegram Sender
==============================================
Busca a música atual no AzuraCast, enriquece com dados do 
Last.fm / MusicBrainz e envia mensagem caprichada para o Telegram.

Uso:
    python3 azura_telegram_metadata.py              # Envio normal
    python3 azura_telegram_metadata.py --test       # Teste com música fixa
    python3 azura_telegram_metadata.py --once       # Envia uma vez e sai

Dependencias: requests, pip install requests
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ─── CONFIG (de .env ou variáveis de ambiente) ────────────────────────────
AZURACAST_URL = "https://dublincalling.duckdns.org"
STATION_SHORT = "dublincalling"
NOWPLAYING_API = f"{AZURACAST_URL}/api/nowplaying/{STATION_SHORT}"

# Tenta carregar do .env do projeto news_colletector
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

TELEGRAM_TOKEN = os.getenv("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID", "1585519868")

# Cache de capas para não sobrecarregar
CACHE_FILE = Path("/tmp/azura_cache.json")
CACHE_TTL = 86400  # 24h

# ─── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("azura_meta")

# ─── FUNÇÕES ───────────────────────────────────────────────────────────────

def get_now_playing():
    """Pega os dados atuais da rádio via API."""
    try:
        resp = requests.get(NOWPLAYING_API, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Erro API NowPlaying: {e}")
        return None


def extract_song_info(np_data):
    """Extrai informações da música atual."""
    if not np_data:
        return None
    
    now_playing = np_data.get('now_playing', {})
    song = now_playing.get('song', {})
    playing_next = np_data.get('playing_next', {})
    next_song = playing_next.get('song', {}) if playing_next else {}
    station = np_data.get('station', {})
    listeners = np_data.get('listeners', {})
    live = np_data.get('live', {})
    
    return {
        'title': song.get('title', 'Desconhecido'),
        'artist': song.get('artist', 'Desconhecido'),
        'album': song.get('album', ''),
        'art': song.get('art', ''),
        'year': song.get('year', ''),
        'genre': ', '.join(filter(None, [song.get('genre', '')])) if song.get('genre') else '',
        'duration': now_playing.get('duration', 0),
        'playlist': now_playing.get('playlist', ''),
        'is_live': live.get('is_live', False),
        'streamer_name': live.get('streamer_name', ''),
        'listeners_total': listeners.get('total', 0),
        'listeners_unique': listeners.get('unique', 0),
        'station_name': station.get('name', 'Dublin Calling'),
        'station_url': station.get('listen_url', ''),
        'next_title': next_song.get('title', ''),
        'next_artist': next_song.get('artist', ''),
    }


def search_lastfm(artist, title):
    """Busca info extra no Last.fm (API pública limitada)."""
    try:
        url = "https://ws.audioscrobbler.com/2.0/"
        # API keys públicas de demonstração — para produção, registre uma em last.fm/api
        api_key = "a7d4e6c8f9b0d2e4f6a8c0e2d4f6a8b0"
        params = {
            'method': 'track.getInfo',
            'api_key': api_key,
            'artist': artist,
            'track': title,
            'format': 'json',
            'autocorrect': 1,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        track = data.get('track', {})
        if not track:
            return {}
        
        # Biografia do artista
        artist_info = track.get('artist', {})
        bio = artist_info.get('bio', {}) if isinstance(artist_info, dict) else {}
        summary = bio.get('summary', '')[:500] if isinstance(bio, dict) else ''
        
        # Tags
        toptags = track.get('toptags', {})
        tags_list = toptags.get('tag', []) if isinstance(toptags, dict) else []
        tags = [t.get('name', '') for t in tags_list[:5] if isinstance(t, dict)]
        
        # Duração em minutos
        duration_ms = int(track.get('duration', 0))
        duration_min = duration_ms // 60000 if duration_ms > 0 else 0
        
        return {
            'listeners': track.get('listeners', ''),
            'playcount': track.get('playcount', ''),
            'duration_min': duration_min,
            'tags': tags,
            'bio_summary': summary,
            'url': track.get('url', ''),
            'album_meta': track.get('album', {}).get('title', '') if isinstance(track.get('album'), dict) else '',
        }
    except Exception as e:
        logger.debug(f"Last.fm erro: {e}")
        return {}


def search_musicbrainz(artist, title):
    """Busca informações adicionais no MusicBrainz."""
    try:
        url = "https://musicbrainz.org/ws/2/recording/"
        headers = {'User-Agent': 'DublinCallingBot/1.0 ( robert_carvalho@hotmail.com )'}
        params = {
            'query': f'artist:"{artist}" AND recording:"{title}"',
            'fmt': 'json',
            'limit': 1,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        
        recordings = data.get('recordings', [])
        if not recordings:
            return {}
        
        recording = recordings[0]
        
        # Ano de lançamento
        releases = recording.get('releases', [])
        release_year = ''
        if releases:
            date = releases[0].get('date', '')
            if date and len(date) >= 4:
                release_year = date[:4]
        
        # País
        country = releases[0].get('country', '') if releases else ''
        
        return {
            'mbid': recording.get('id', ''),
            'release_year': release_year,
            'country': country,
            'mb_url': f"https://musicbrainz.org/recording/{recording.get('id', '')}" if recording.get('id') else '',
        }
    except Exception as e:
        logger.debug(f"MusicBrainz erro: {e}")
        return {}


def format_duration(seconds):
    """Formata segundos em MM:SS."""
    if not seconds:
        return "?:??"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def build_message(info, lastfm=None, mb=None):
    """
    Monta a mensagem enriquecida para o Telegram.
    Usa o truque do '​' (zero-width space) para mostrar a imagem como preview.
    """
    if not info:
        return None
    
    # Capa como preview (primeira linha invisível)
    preview = f"[​]({info['art']})" if info.get('art') else ""
    
    # Tags do Last.fm
    tags_str = ""
    if lastfm and lastfm.get('tags'):
        tags_str = " · ".join([f"#{t.replace(' ', '')}" for t in lastfm['tags'][:4]])
    
    # Popularidade
    popularity = ""
    if lastfm:
        plays = lastfm.get('playcount', '')
        listeners = lastfm.get('listeners', '')
        if plays:
            popularity = f"\n👥 {plays} plays · {listeners} listeners"
    
    # Biografia curta
    bio = ""
    if lastfm and lastfm.get('bio_summary'):
        raw = lastfm['bio_summary']
        # Limpa links HTML
        import re
        clean_bio = re.sub(r'<[^>]+>', '', raw)[:300]
        bio = f"\n📖 _{clean_bio}_"
    
    # Se for live (DJ ativo)
    live_badge = ""
    if info['is_live']:
        live_badge = f"\n🔴 **LIVE** com {info['streamer_name']}!"
    
    # Listener count
    listeners = f"\n👂 {info['listeners_total']} ouvindo agora"
    
    # Duração formatada
    duration = format_duration(info.get('duration', 0))
    
    # Ano
    year = info.get('year', '')
    if not year and mb and mb.get('release_year'):
        year = mb['release_year']
    
    # Monta mensagem
    msg = f"""{preview}
━━━━━━━━━━━━━━━━━━━━━
📻 **{info['station_name']}** 🇮🇪
━━━━━━━━━━━━━━━━━━━━━

🎵 **{info['title']}**
👤 _{info['artist']}_{live_badge}

💿 `{info['album']}`
📅 {year} · ⏱ {duration} · 🎸 {info.get('genre', '')} · 📂 {info.get('playlist', '')}

{popularity}
{tags_str}
{bio}
{listeners}"""

    # Próxima música
    if info.get('next_title') and info.get('next_artist'):
        msg += f"""

━━━━━━━━━━━━━━━━━━━━━
⏭️ **UP NEXT:**
{info['next_artist']} - {info['next_title']}"""

    # Links
    listen_url = info.get('station_url') or f"{AZURACAST_URL}/public/{STATION_SHORT}"
    msg += f"""

━━━━━━━━━━━━━━━━━━━━━
🔴 [▶ Listen Live]({listen_url})
💬 [Request Song](https://t.me/Siteschanges_bot)
"""

    if lastfm and lastfm.get('url'):
        msg += f"🌐 [More on Last.fm]({lastfm['url']})\n"
    
    if mb and mb.get('mb_url'):
        msg += f"📀 [MusicBrainz]({mb['mb_url']})"

    return msg


def send_telegram(message):
    """Envia a mensagem para o Telegram."""
    if not message:
        logger.warning("Mensagem vazia, não enviando")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # Limita a 4096 chars
    if len(message) > 4000:
        message = message[:3997] + "..."
    
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': False,  # Mostra a capa!
    }
    
    try:
        resp = requests.post(url, data=payload, timeout=15)
        resp.raise_for_status()
        logger.info("✅ Mensagem enviada para Telegram!")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao enviar Telegram: {e}")
        return False


def should_send(info, cache):
    """
    Verifica se devemos enviar baseado na música atual vs última enviada.
    """
    if not info:
        return False
    
    key = f"{info['artist']} - {info['title']}"
    last = cache.get('last_song', '')
    
    if key == last:
        return False
    
    cache['last_song'] = key
    cache['timestamp'] = time.time()
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)
    
    return True


def test_mode():
    """Modo teste: usa dados fixos."""
    info = {
        'title': 'Bohemian Rhapsody',
        'artist': 'Queen',
        'album': 'A Night at the Opera',
        'art': 'https://upload.wikimedia.org/wikipedia/en/4/4d/Queen_A_Night_At_The_Opera.png',
        'year': '1975',
        'genre': 'Rock, Progressive Rock',
        'duration': 354,
        'playlist': 'Classic Rock',
        'is_live': False,
        'streamer_name': '',
        'listeners_total': 42,
        'listeners_unique': 35,
        'station_name': 'Dublin Calling',
        'station_url': 'https://dublincalling.duckdns.org/listen/dublincalling/radio.mp3',
        'next_title': 'Stairway to Heaven',
        'next_artist': 'Led Zeppelin',
    }
    return info


# ─── MAIN ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AzuraCast Metadata Enricher")
    parser.add_argument('--test', action='store_true', help='Modo teste com dados fixos')
    parser.add_argument('--once', action='store_true', help='Envia uma vez e sai')
    parser.add_argument('--daemon', action='store_true', help='Modo daemon (loop)')
    args = parser.parse_args()
    
    logger.info("🚀 AzuraCast Metadata Enricher iniciado")
    
    # Cache
    cache = {'last_song': '', 'timestamp': 0}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)
        except:
            pass
    
    while True:
        # 1. Pega música atual
        if args.test:
            logger.info("🔧 Modo TESTE")
            info = test_mode()
        else:
            np_data = get_now_playing()
            info = extract_song_info(np_data) if np_data else None
        
        if not info:
            logger.warning("⏳ Sem dados da rádio, aguardando...")
            if args.once:
                return
            time.sleep(30)
            continue
        
        # 2. Verifica se já foi enviada
        if not should_send(info, cache) and not args.test and not args.once:
            logger.debug(f"⏭️  Música já enviada: {info['title']}")
            if args.daemon:
                time.sleep(30)
                continue
            return
        
        logger.info(f"🎵 Nova música: {info['artist']} - {info['title']}")
        
        # 3. Enriquece metadados
        logger.info("🔍 Buscando Last.fm...")
        lastfm = search_lastfm(info['artist'], info['title'])
        
        logger.info("🔍 Buscando MusicBrainz...")
        mb = search_musicbrainz(info['artist'], info['title'])
        
        # 4. Monta mensagem
        logger.info("📝 Montando mensagem...")
        message = build_message(info, lastfm, mb)
        
        # 5. Envia
        if args.test:
            logger.info("=== MENSAGEM DE TESTE ===")
            print(message)
            logger.info("=" * 40)
        else:
            send_telegram(message)
        
        if args.once or args.test:
            break
        
        if not args.daemon:
            break
        
        # Modo daemon: espera e verifica novamente
        time.sleep(30)


if __name__ == "__main__":
    main()
