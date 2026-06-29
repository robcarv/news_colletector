#!/usr/bin/env python3
"""
AzuraCast → Telegram v2 — Rich Interactive Notifications
=========================================================
Substitui o webhook básico do AzuraCast. A cada música nova:
  1. Busca metadados no Last.fm (tags, playcount, bio)
  2. Busca no MusicBrainz (ano, país, link)
  3. Monta mensagem formatada com box-drawing + inline keyboard
  4. Envia UMA mensagem rica para o Telegram

Uso:
    python3 azura_telegram_v2.py --daemon     # loop eterno, polling a cada 10s
    python3 azura_telegram_v2.py --once       # verifica e envia uma vez (cron-friendly)
    python3 azura_telegram_v2.py --test       # preview no terminal (não envia)

Inline Keyboard:
    [🎧 Listen Live] → stream URL
    [💬 Request]     → Telegram bot
    [🌐 Last.fm]     → Last.fm track page
    [📀 MusicBrainz] → MusicBrainz recording

Requisitos: pip install requests python-dotenv
"""

import argparse
import json
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ─── CONFIG ────────────────────────────────────────────────────────────────
AZURACAST_URL = "https://dublincalling.duckdns.org"
STATION_SHORT = "dublincalling"
NOWPLAYING_API = f"{AZURACAST_URL}/api/nowplaying/{STATION_SHORT}"

# Carrega .env
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

TELEGRAM_TOKEN = os.getenv("DUBLIN_BOT_TOKEN") or os.getenv("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("DUBLIN_CHAT_ID") or os.getenv("CHAT_ID")
# Channel/grupo opcional (envia em paralelo)
TELEGRAM_CHANNEL_ID = os.getenv("CHANNEL_ID", "")

# Cache para evitar duplicatas
CACHE_FILE = Path("/tmp/azura_cache_v2.json")

# Last.fm API key — registre gratuitamente em https://www.last.fm/api/account/create
# Depois coloque LASTFM_API_KEY=xxx no arquivo .env
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "")

# Links (públicos — sem secrets)
LISTEN_URL = f"{AZURACAST_URL}/listen/{STATION_SHORT}/radio.mp3"
REQUEST_BOT = "https://t.me/Siteschanges_bot"
STATION_URL = "https://dublincalling.duckdns.org/public/dublincalling"
STATION_NAME = "DUBLIN CALLING"
STATION_FLAG = "🇮🇪"
# PIX key (chave pública de recebimento — não é secret, é pra ser compartilhada)
PIX_KEY = os.getenv("PIX_KEY", "a8d87cf3-c48f-436a-acb5-7dfd0a64a7f6")
QR_PIX_URL = "https://raw.githubusercontent.com/robcarv/azura-cast-customizations/main/assets/pix_qr.png"

# ─── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("azura_v2")


# ─── API HELPERS ───────────────────────────────────────────────────────────

def fetch_nowplaying():
    """Busca o nowplaying da API do AzuraCast."""
    try:
        resp = requests.get(NOWPLAYING_API, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"Erro API NowPlaying: {e}")
        return None


def extract_info(np_data: dict) -> dict | None:
    """Extrai dados relevantes do nowplaying."""
    if not np_data:
        return None

    np = np_data.get("now_playing", {})
    song = np.get("song", {})
    pn = np_data.get("playing_next", {})
    next_song = pn.get("song", {}) if pn else {}
    station = np_data.get("station", {})
    listeners = np_data.get("listeners", {})
    live = np_data.get("live", {})

    # Extrai ano do nome do álbum como fallback (ex: "Album Name, 2001")
    album = song.get("album", "")
    year = song.get("year", "")
    if not year:
        m = re.search(r"(\d{4})$", album)
        if m:
            year = m.group(1)

    return {
        "title": (song.get("title") or "").strip(),
        "artist": (song.get("artist") or "").strip(),
        "album": album,
        "art": song.get("art", ""),
        "year": year,
        "genre": song.get("genre", ""),
        "duration": np.get("duration", 0),
        "elapsed": np.get("elapsed", 0),
        "remaining": np.get("remaining", 0),
        "playlist": np.get("playlist", ""),
        "is_live": live.get("is_live", False),
        "streamer_name": live.get("streamer_name", ""),
        "listeners_total": listeners.get("total", 0),
        "listeners_unique": listeners.get("unique", 0),
        "next_title": (next_song.get("title") or "").strip(),
        "next_artist": (next_song.get("artist") or "").strip(),
    }


def search_lastfm(artist: str, title: str) -> dict:
    """Busca metadados no Last.fm com fallbacks para tags e bio."""
    result = {}
    api = "https://ws.audioscrobbler.com/2.0/"

    try:
        # 1. Track info (playcount, listeners, url, tags)
        resp = requests.get(api, params={
            "method": "track.getInfo", "api_key": LASTFM_API_KEY,
            "artist": artist, "track": title,
            "format": "json", "autocorrect": 1,
        }, timeout=10)
        data = resp.json()
        track = data.get("track", {})
        if not track:
            return {}

        result["listeners"] = track.get("listeners", "")
        result["playcount"] = track.get("playcount", "")
        result["url"] = track.get("url", "")

        # Album art do Last.fm (maior tamanho disponível)
        album = track.get("album", {})
        images = album.get("image", []) if isinstance(album, dict) else []
        result["art_url"] = ""
        for img in images:
            if img.get("size") == "extralarge":
                result["art_url"] = img.get("#text", "")
        if not result["art_url"] and images:
            result["art_url"] = images[-1].get("#text", "")

        # Tags do track
        toptags = track.get("toptags", {})
        tags_list = toptags.get("tag", []) if isinstance(toptags, dict) else []
        result["tags"] = [t.get("name", "") for t in tags_list[:8] if isinstance(t, dict)]

        # Bio resumida
        artist_info = track.get("artist", {})
        bio_data = artist_info.get("bio", {}) if isinstance(artist_info, dict) else {}
        summary = bio_data.get("summary", "") if isinstance(bio_data, dict) else ""
        result["bio_summary"] = summary if summary else ""

        # 2. Fallback: tags do artista (se track não tem tags)
        if not result["tags"]:
            try:
                resp2 = requests.get(api, params={
                    "method": "artist.getTopTags", "api_key": LASTFM_API_KEY,
                    "artist": artist, "format": "json", "autocorrect": 1,
                }, timeout=8)
                d2 = resp2.json()
                atags = d2.get("toptags", {}).get("tag", [])
                result["tags"] = [t.get("name", "") for t in atags[:6] if isinstance(t, dict)]
            except Exception:
                pass

        # 3. Fallback: bio completa do artista (se track não tem)
        if not result["bio_summary"]:
            try:
                resp3 = requests.get(api, params={
                    "method": "artist.getInfo", "api_key": LASTFM_API_KEY,
                    "artist": artist, "format": "json", "autocorrect": 1, "lang": "en",
                }, timeout=8)
                d3 = resp3.json()
                artist_data = d3.get("artist", {})
                bio = artist_data.get("bio", {}) if isinstance(artist_data, dict) else {}
                result["bio_summary"] = bio.get("summary", "") if isinstance(bio, dict) else ""
                # Similar artists
                similar = artist_data.get("similar", {}).get("artist", []) if isinstance(artist_data, dict) else []
                result["similar"] = [s.get("name", "") for s in similar[:3] if isinstance(s, dict)]
            except Exception:
                pass

        return result
    except Exception as e:
        log.debug(f"Last.fm error: {e}")
        return {}


def search_musicbrainz(artist: str, title: str) -> dict:
    """Busca ano e país no MusicBrainz."""
    try:
        params = {
            "query": f'artist:"{artist}" AND recording:"{title}"',
            "fmt": "json",
            "limit": 1,
        }
        headers = {"User-Agent": "DublinCallingBot/2.0"}
        resp = requests.get(
            "https://musicbrainz.org/ws/2/recording/",
            params=params,
            headers=headers,
            timeout=10,
        )
        data = resp.json()
        recordings = data.get("recordings", [])
        if not recordings:
            return {}

        r = recordings[0]
        releases = r.get("releases", [])
        release_year = ""
        country = ""
        if releases:
            date = releases[0].get("date", "")
            if date and len(date) >= 4:
                release_year = date[:4]
            country = releases[0].get("country", "")

        return {
            "mbid": r.get("id", ""),
            "release_year": release_year,
            "country": country,
            "mb_url": f"https://musicbrainz.org/recording/{r.get('id', '')}" if r.get("id") else "",
        }
    except Exception as e:
        log.debug(f"MusicBrainz error: {e}")
        return {}


# ─── FORMATTING ────────────────────────────────────────────────────────────

def fmt_duration(seconds: int | float) -> str:
    if not seconds:
        return "?:??"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def fmt_count(n: str | int) -> str:
    """Formata números grandes: 1234567 → 1.2M"""
    try:
        n = int(n)
    except (ValueError, TypeError):
        return str(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def clean_bio(text: str, max_len: int = 280) -> str:
    """Remove HTML e trunca a bio do Last.fm."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"Read more.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"User-contributed text.*$", "", text, flags=re.IGNORECASE)
    text = text.strip()
    if len(text) > max_len:
        text = text[: max_len - 3].rsplit(".", 1)[0] + "."
    return text


def build_message(info: dict, lastfm: dict | None = None, mb: dict | None = None) -> str:
    """Monta a mensagem Telegram. Last.fm link gera preview rico automaticamente."""
    if not info or not info.get("title"):
        return ""

    # ── Preview: Last.fm URL gera preview rico. Fallback: página da rádio ──
    preview = ""
    if lastfm and lastfm.get("url"):
        preview = f"🎵 [{info['artist']} — {info['title']}]({lastfm['url']})\n\n"
    else:
        preview = f"📻 [DUBLIN CALLING — Listen Live]({STATION_URL})\n\n"

    # ── Header ──
    header = (
        f"📻 *{STATION_NAME}* {STATION_FLAG}\n"
        "▶  NOW PLAYING"
    )

    # ── Live badge ──
    live_badge = ""
    if info.get("is_live"):
        live_badge = f"\n🔴 **LIVE** — {info.get('streamer_name', 'DJ')}"

    # ── Song + artist ──
    song_line = f"\n🎵 *{info['title']}*"
    artist_display = info['artist'] if info['artist'] else 'Unknown Artist'
    artist_line = f"👤 _{artist_display}_{live_badge}"

    # ── Album ──
    album_line = ""
    if info.get("album"):
        album_line = f"\n💿 `{info['album']}`"

    # ── Tags + stats (Last.fm) ──
    tags_line = ""
    stats_line = ""
    if lastfm:
        tags = lastfm.get("tags", [])
        if tags:
            hashtags = "  ".join([f"`#{t.replace(' ', '')}`" for t in tags[:5]])
            tags_line = f"\n🏷 {hashtags}"

        playcount = lastfm.get("playcount", "")
        listeners = lastfm.get("listeners", "")
        if playcount:
            stats_line = f"📊 {fmt_count(playcount)} plays · {fmt_count(listeners)} listeners"

    # ── Next song (precisa vir antes do divider) ──
    next_line = ""
    if info.get("next_title"):
        next_artist = info.get("next_artist", "")
        if next_artist:
            next_line = f"⏭️  *Next:* {next_artist} — {info['next_title']}"
        else:
            next_line = f"⏭️  *Next:* {info['next_title']}"

    # ── Divider ──
    mid_div = "\n" + "━" * 28 if (tags_line or stats_line) and not next_line else ""

    # ── Year / Duration / Genre / Playlist / Listeners ──
    year = info.get("year", "")
    if not year and mb and mb.get("release_year"):
        year = mb["release_year"]
    duration = fmt_duration(info.get("duration", 0))
    genre = info.get("genre", "") or "—"
    playlist = info.get("playlist", "") or "—"
    listeners_now = info.get("listeners_total", 0)

    detail_parts = []
    if year:
        detail_parts.append(f"📅 {year}")
    detail_parts.append(f"⏱ {duration}")
    detail_parts.append(f"🎸 {genre}")
    detail_parts.append(f"📂 {playlist}")
    detail_parts.append(f"👂 {listeners_now} listening")
    detail_line = "  ".join(detail_parts)

    # ── Artist bio ──
    bio_line = ""
    if lastfm:
        raw_bio = lastfm.get("bio_summary", "")
        if raw_bio:
            bio = clean_bio(raw_bio, max_len=120)
            if bio:
                bio_line = f"\n\n📖 _{bio}_"

    # ── Similar artists ──
    similar_line = ""
    if lastfm:
        similar = lastfm.get("similar", [])
        if similar:
            similar_line = f"\n🔗 *Similar:* {', '.join(similar)}"

    # ── MusicBrainz detail ──
    mb_line = ""
    if mb:
        mb_country = mb.get("country", "")
        mb_year = mb.get("release_year", "")
        if mb_country or mb_year:
            mb_line = "\n📀 "
            if mb_year:
                mb_line += f"Released {mb_year}"
            if mb_country:
                mb_line += f" ({mb_country})"

    # ── Footer ──
    footer = (
        "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔴 [▶ Listen Live]({LISTEN_URL})\n"
        f"💬 [Request a Song]({REQUEST_BOT})"
    )

    # ── MusicBrainz link ──
    if mb and mb.get("mb_url"):
        footer += f"\n📀 [MusicBrainz]({mb['mb_url']})"

    # ── PIX support ──
    footer += f"\n\n🔗 [dublincalling.duckdns.org]({STATION_URL})"
    footer += f"\n💚 *Ajude a rádio!* PIX: `{PIX_KEY}`"

    # ── Divider before next ──
    next_div = "\n" + "━" * 28 if next_line else ""

    # ── Monta ──
    msg = (
        preview
        + "\n"             # força newline após preview invisível
        + header
        + "\n"             # espaço após header
        + song_line
        + "\n"
        + artist_line
        + album_line
        + mid_div
        + tags_line
        + ("\n" + stats_line if stats_line else "")
        + "\n" + detail_line
        + bio_line
        + similar_line
        + mb_line
        + next_div
        + "\n"
        + next_line
        + footer
    )
    return msg


def build_inline_keyboard(lastfm_url: str = "", mb_url: str = "") -> dict:
    """Cria o inline keyboard com botões interativos."""
    buttons = [
        [
            {"text": "🎧 Listen Live", "url": LISTEN_URL},
            {"text": "💬 Request", "url": REQUEST_BOT},
        ],
    ]

    second_row = []
    if lastfm_url:
        second_row.append({"text": "🌐 Last.fm", "url": lastfm_url})
    if mb_url:
        second_row.append({"text": "📀 MusicBrainz", "url": mb_url})
    if second_row:
        buttons.append(second_row)

    # Support button
    buttons.append([
        {"text": "💚 Support (PIX)", "url": QR_PIX_URL},
    ])

    return {"inline_keyboard": buttons}


# ─── TELEGRAM SEND ─────────────────────────────────────────────────────────

def send_telegram(message: str, reply_markup: dict | None = None, chat_id: str | None = None, art_url: str = "") -> bool:
    """Envia via sendPhoto (capa do Last.fm) ou sendMessage (fallback)."""
    if not message:
        return False
    if not TELEGRAM_TOKEN:
        log.error("BOT_TOKEN não configurado")
        return False

    target = chat_id or TELEGRAM_CHAT_ID
    if not target:
        log.error("CHAT_ID não configurado")
        return False

    # Tenta sendPhoto com capa do Last.fm
    if art_url:
        try:
            img_resp = requests.get(art_url, timeout=15)
            if img_resp.status_code == 200 and len(img_resp.content) > 500:
                files = {"photo": ("art.jpg", img_resp.content, "image/jpeg")}
                data = {
                    "chat_id": target,
                    "caption": message[:900],
                    "parse_mode": "Markdown",
                }
                if reply_markup:
                    data["reply_markup"] = json.dumps(reply_markup)
                resp = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                    data=data, files=files, timeout=20
                )
                resp.raise_for_status()
                log.info(f"✅ Foto+legenda enviada para {target}")
                return True
        except Exception as e:
            log.warning(f"sendPhoto falhou: {e}")

    # Fallback: sendMessage
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": target,
        "text": message[:4000],
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        resp = requests.post(url, data=payload, timeout=15)
        resp.raise_for_status()
        log.info(f"✅ Enviado para chat {target}")
        return True
    except Exception as e:
        log.error(f"❌ Erro Telegram ({target}): {type(e).__name__}")
        return False


# ─── CACHE ─────────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            pass
    return {"last_song": "", "timestamp": 0}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache))


def song_key(info: dict) -> str:
    return f"{info.get('artist', '')} — {info.get('title', '')}"


def is_new_song(info: dict, cache: dict) -> bool:
    """True se for uma música nova (diferente da última enviada)."""
    key = song_key(info)
    if key == cache.get("last_song", ""):
        return False
    cache["last_song"] = key
    cache["timestamp"] = time.time()
    save_cache(cache)
    return True


# ─── PROCESS ───────────────────────────────────────────────────────────────

def process(force: bool = False, dry_run: bool = False) -> bool:
    """
    Fluxo completo: fetch → extract → check cache → enrich → build → send.
    Retorna True se enviou ou processou com sucesso.
    """
    cache = load_cache()

    # 1. Fetch
    np_data = fetch_nowplaying()
    if not np_data:
        return False

    info = extract_info(np_data)
    if not info or not info.get("title"):
        return False

    # 2. Nova música?
    if not force and not is_new_song(info, cache):
        log.debug(f"⏭️  Já enviada: {song_key(info)}")
        return False

    log.info(f"🎵 Nova: {song_key(info)}")

    # 3. Enriquecer metadados (sempre, exceto no --test que usa dados fixos)
    lastfm = {}
    mb = {}
    if LASTFM_API_KEY:
        log.info("🔍 Last.fm...")
        lastfm = search_lastfm(info["artist"], info["title"])
    log.info("🔍 MusicBrainz...")
    mb = search_musicbrainz(info["artist"], info["title"])

    # 4. Montar mensagem + keyboard
    msg = build_message(info, lastfm, mb)
    keyboard = build_inline_keyboard(
        lastfm_url=lastfm.get("url", ""),
        mb_url=mb.get("mb_url", ""),
    )

    if dry_run:
        print("=" * 50)
        print(msg)
        print("=" * 50)
        print("KEYBOARD:", json.dumps(keyboard, indent=2))
        return True

    # 5. Enviar
    art_url = lastfm.get("art_url", "")
    ok = send_telegram(msg, reply_markup=keyboard, art_url=art_url)

    # Envia também para o canal (se configurado)
    if ok and TELEGRAM_CHANNEL_ID:
        send_telegram(msg, reply_markup=keyboard, chat_id=TELEGRAM_CHANNEL_ID, art_url=art_url)

    return ok


# ─── TEST MODE ─────────────────────────────────────────────────────────────

def test_data() -> dict:
    return {
        "title": "Rip",
        "artist": "Gary Numan",
        "album": "John Peel Sessions - Maida Vale, 07.02.2001",
        "art": "https://dublincalling.duckdns.org/api/station/dublincalling/art/4048e06a643ab1319027dee3-1765032361.jpg",
        "year": "2001",
        "genre": "Electronic",
        "duration": 308,
        "elapsed": 120,
        "remaining": 188,
        "playlist": "peel session",
        "is_live": False,
        "streamer_name": "",
        "listeners_total": 3,
        "listeners_unique": 2,
        "next_title": "one-two",
        "next_artist": "scientist",
    }


def test_mode():
    """Preview no terminal com dados reais da API + enriquecimento."""
    print("🔧 TEST MODE — preview da mensagem\n")

    info = test_data()
    print("📡 Buscando Last.fm...")
    lastfm = search_lastfm(info["artist"], info["title"])
    print("📡 Buscando MusicBrainz...")
    mb = search_musicbrainz(info["artist"], info["title"])

    msg = build_message(info, lastfm, mb)
    keyboard = build_inline_keyboard(
        lastfm_url=lastfm.get("url", ""),
        mb_url=mb.get("mb_url", ""),
    )

    print()
    print("=" * 50)
    print("MENSAGEM:")
    print("=" * 50)
    print(msg)
    print()
    print("=" * 50)
    print("INLINE KEYBOARD:")
    print("=" * 50)
    print(json.dumps(keyboard, indent=2))
    print()
    print(f"📏 Tamanho: {len(msg)} chars (limite Telegram: 4096)")
    print("✅ Pronto! Use --once para enviar de verdade.")


# ─── MAIN ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AzuraCast → Telegram v2 — Rich Interactive Notifications"
    )
    parser.add_argument("--test", action="store_true", help="Preview no terminal (não envia)")
    parser.add_argument("--once", action="store_true", help="Verifica e envia uma vez")
    parser.add_argument("--force", action="store_true", help="Força envio mesmo se já enviada")
    parser.add_argument("--dry-run", action="store_true", help="Busca dados reais mas NÃO envia (preview)")
    parser.add_argument(
        "--daemon", action="store_true", help="Loop eterno, polling a cada 10s"
    )
    parser.add_argument(
        "--interval", type=int, default=10, help="Intervalo de polling em segundos (daemon)"
    )
    args = parser.parse_args()

    if args.test:
        test_mode()
        return

    if args.dry_run:
        log.info("🔍 DRY RUN — buscando dados reais, sem enviar")
        process(force=True, dry_run=True)
        return

    if args.once or args.force:
        process(force=args.force if args.force else False)
        return

    if args.daemon:
        log.info(f"🚀 Daemon iniciado — polling a cada {args.interval}s")
        log.info("   Pressione Ctrl+C para parar")

        shutdown = False

        def handler(sig, frame):
            nonlocal shutdown
            log.info("🛑 Parando...")
            shutdown = True

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        while not shutdown:
            try:
                process()
            except Exception as e:
                log.error(f"Erro no loop: {e}")

            # Sleep com suporte a interrupção limpa
            for _ in range(args.interval):
                if shutdown:
                    break
                time.sleep(1)

        log.info("👋 Daemon encerrado")
        return

    # Default: sem argumentos = mostra help
    parser.print_help()


if __name__ == "__main__":
    main()
