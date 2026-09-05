#!/usr/bin/env python3
# =============================================================================
# export_portfolio_news.py — Converte news_run.json → portfolio news.json
# com MIX REGIONAL (BR + IE + UK + US), substituindo o slice burro (pt+en)[:15]
# que saturava com as 27 noticias PT e nunca chegava ao EN.
# Chamado pelo run_newsbot.sh apos o main.py (cron homelab-newsbot).
# =============================================================================
# Selecao: 15 itens por cotas de regiao (feeds_config.json → campo `region`):
#   br=4, ie=3, uk=3, us=4, global=1
# Regiao com menos itens que a cota: slots sobram e sao preenchidos pelas
# demais regioes (ordem de prioridade do fallback: us, br, uk, global, ie).
# =============================================================================
import json
import os
import shutil
from datetime import datetime, timezone

PROJECT_DIR = "/home/robert/Documents/vscode_projects/news_colletector"
RUN_FILE = f"{PROJECT_DIR}/news_run.json"
FEEDS_FILE = f"{PROJECT_DIR}/feeds_config.json"
AUDIO_SRC = f"{PROJECT_DIR}/data/audio"
PORTFOLIO_FILE = "/home/robert/Documents/portfolio-html/news.json"
AUDIO_DST = "/home/robert/Documents/portfolio-html/audio"

LIMIT = 15
QUOTAS = {"br": 4, "ie": 3, "uk": 3, "us": 4, "global": 1}
FALLBACK_ORDER = ["us", "br", "uk", "global", "ie"]  # p/ slots nao preenchidos


def region_map():
    with open(FEEDS_FILE) as f:
        feeds = json.load(f)
    return {f.get("name", ""): f.get("region", "us") for f in feeds}


def select(items, get_region):
    buckets = {}
    for it in items:
        buckets.setdefault(get_region(it), []).append(it)
    chosen = []
    for r, q in QUOTAS.items():
        chosen.extend(buckets.get(r, [])[:q])
    # slots restantes: fallback nas regioes com sobra (preserva ordem)
    rest = [it for it in items if it not in chosen]
    while len(chosen) < LIMIT and rest:
        for r in FALLBACK_ORDER:
            for it in list(rest):
                if get_region(it) == r:
                    chosen.append(it)
                    rest.remove(it)
                    break
            if len(chosen) >= LIMIT:
                break
    return chosen[:LIMIT]


def main():
    now_iso = datetime.now(timezone.utc).astimezone().isoformat()
    if not os.path.exists(RUN_FILE):
        print("  news_run.json nao encontrado")
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump({"updated": now_iso, "items": []}, f, indent=2, ensure_ascii=False)
        return

    with open(RUN_FILE) as f:
        data = json.load(f)

    reg = region_map()
    all_items = data.get("pt", []) + data.get("en", [])
    chosen = select(all_items, lambda it: reg.get(it.get("source", ""), "us"))

    items = []
    for item in chosen:
        entry = {
            "title": item.get("title", ""),
            "source": item.get("source", "RSS"),
            "link": item.get("link", ""),
            "summary": item.get("summary", ""),
            "date": item.get("date", ""),
            "image": item.get("image", ""),
        }
        # injeta audio por match de titulo (mesmo algoritmo do main.py)
        title = entry["title"]
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:50].strip("_")
        mp3 = safe + ".mp3"
        if os.path.exists(os.path.join(AUDIO_SRC, mp3)):
            entry["audio"] = "audio/" + mp3
        items.append(entry)

    # copia MP3s referenciados para o portfolio (repo publico)
    os.makedirs(AUDIO_DST, exist_ok=True)
    copied = 0
    for it in items:
        if it.get("audio"):
            src = os.path.join(AUDIO_SRC, os.path.basename(it["audio"]))
            dst = os.path.join(AUDIO_DST, os.path.basename(it["audio"]))
            if os.path.exists(src):
                shutil.copy2(src, dst)
                copied += 1

    output = {"updated": now_iso, "items": items}
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Prune: audio/ deve conter SO os MP3s referenciados (evita acumulo —
    # chegou a 1152 arquivos / 183MB no repo publico; cada run = 15 novos)
    referenced = {os.path.basename(it["audio"]) for it in items if it.get("audio")}
    removed = 0
    for fname in os.listdir(AUDIO_DST):
        if fname.endswith(".mp3") and fname not in referenced:
            try:
                os.remove(os.path.join(AUDIO_DST, fname))
                removed += 1
            except OSError:
                pass

    n_audio = sum(1 for i in items if i.get("audio"))
    from collections import Counter
    mix = Counter(reg.get(i["source"], "us") for i in items)
    print(f"  {len(items)} noticias exportadas ({n_audio} com audio, {copied} MP3s copiados, {removed} stale removidos)")
    print(f"  mix regional: {dict(mix)}")


if __name__ == "__main__":
    main()
