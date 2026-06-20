# NewsBot v4.1 — Documentação Técnica Final

> **Repositório:** `git@github.com:robcarv/news_colletector.git` (branch `v4`)
> **Diretório:** `~/Documents/vscode_projects/news_colletector/`
> **Host:** Raspberry Pi 5 (ARM64, Linux 6.12.87+rpt-rpi-2712)
> **Data:** 2026-06-20 | **Versão:** v4.1
> **Commit:** `4ef8ae9`

---

## 1. Arquitetura do Sistema

```
┌──────────────────────────────────────────────────────────────────────┐
│                       NEWS COLLECTOR v4.1                            │
│                   Pipeline Completo de Notícias                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  CRON (4x/dia ── Pi501-117)                                         │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────┐            │
│  │ 00:00    │    │ 06/12/18     │    │ run_newsbot.sh   │            │
│  │ --podcast│    │ normal       │    │ nice -n 19       │            │
│  └────┬─────┘    └──────┬───────┘    │ ionice -c 2      │            │
│       │                 │            │ timeout 600s     │            │
│       └────────┬────────┘            └───────┬─────────┘            │
│                ▼                             │                      │
│  ┌──────────────────────────────┐            │                      │
│  │          main.py             │◄───────────┘                      │
│  │     News Collector v4.1      │                                   │
│  └──────────┬───────────────────┘                                   │
│             │                                                       │
│     ┌───────┼────────┬──────────┬──────────┬─────────────┐         │
│     ▼       ▼        ▼          ▼          ▼             ▼         │
│  collector  audio  processor  notifier  azuracast    sync_git       │
│  (feedparser)(TTS) (Sumy LSA)(Telegram) _news.py     .sh            │
│     │       │        │          │          │             │          │
│     │  ┌────┴────┐   │    ┌─────┴──┐  ┌────┴──────┐  ┌──┴───────┐ │
│     │  │Piper    │   │    │Telegram│  │AzuraCast  │  │robcarv   │ │
│     │  │offline  │   │    │sendAudio│  │API upload │  │.github.io│ │
│     │  │ARM NEON │   │    │sendMsg  │  │+ SCP Samba│  │portfolio │ │
│     │  └─────────┘   │    └────────┘  └───────────┘  └──────────┘ │
│     ▼                ▼                                             │
│  27 RSS feeds    normalizer.py                                      │
│  (5 PT + 22 EN)  (num2words)                                        │
│                                                                      │
│  SAÍDAS:                                                            │
│  ├── Telegram: áudio .wav + resumo texto (por feed)                 │
│  ├── AzuraCast: jingle MP3 → playlist "News Jingles" (30min)        │
│  ├── Samba: \\192.168.68.108\HDRadio\news_jingles\                  │
│  ├── Portfolio: news.json → robcarv.github.io                       │
│  └── GitHub: push automático (2 repositórios)                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Componentes — Ficha Técnica

### 2.1 Módulos Python

| Módulo | Linhas | Função | Dependências |
|--------|--------|--------|-------------|
| `main.py` | 362 | Orquestrador: coleta, áudio, jingle, git | todos os src/* |
| `src/config.py` | 71 | Config central: paths, env, limites | dotenv, pathlib |
| `src/collector.py` | 59 | Coleta RSS via feedparser | feedparser |
| `src/processor.py` | 68 | Resumo LSA (Sumy) + clean HTML | sumy, nltk |
| `src/audio.py` | 170 | TTS: Piper offline + Edge fallback | subprocess, edge-tts |
| `src/normalizer.py` | 218 | Converte números/datas/%/R$ p/ fala | num2words, re |
| `src/notifier.py` | 81 | Telegram: sendMessage + sendAudio | requests |
| `src/azuracast_news.py` | 198 | Upload jingle + SCP Samba + playlist | requests, scp, ffmpeg |
| `src/podcast.py` | — | Podcast diário (ffmpeg concat) | ffmpeg |
| `run_newsbot.sh` | ~110 | Wrapper: nice/ionice, sync git, health | bash |
| `sync_git.sh` | 99 | Push news_colletector + portfolio | git, ssh |
| `sync_portfolio.sh` | — | Push robcarv.github.io | git |

### 2.2 Configuração de Feeds (feeds_config.json)

| Categoria | Feeds | Idioma |
|-----------|-------|--------|
| Brasil | Folha de S.Paulo, Tenho Mais Discos, RockBizz, Rolling Stone Brasil | pt (4) |
| Irlanda | Irish Independent, Hot Press, GoldenPlec, Dublin Live, Irish News Ent. | en (5) |
| Reino Unido | BBC News, Guardian UK, NME Music, MusicRadar, NME News | en (5) |
| EUA | Pitchfork, Rolling Stone, Consequence, Billboard, Stereogum, BrooklynVegan, Loudwire, Spin, Metal Injection | en (9) |
| Tecnologia | IBM, Nintendo, Guardian Tech | en (3) |
| EUA/Extra | Guardian US | en (1) |
| **TOTAL** | **27 feeds** | **5 PT + 22 EN** |

### 2.3 Limites e Parâmetros

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| MAX_ITEMS_PER_FEED | 4 | Notícias coletadas por feed |
| MAX_AUDIO_CHARS | 2500 | Caracteres máx. por áudio |
| MAX_SUMMARY_SENTENCES | 3 | Sentenças no resumo Sumy |
| MAX_HISTORY | 200 | Títulos no histórico |
| RETENTION_DAYS | 3 | Retenção de áudios |
| DOWNLOAD_TIMEOUT | 15s | Timeout coleta RSS |
| TELEGRAM_TIMEOUT | 30s | Timeout API Telegram |
| GC_INTERVAL | 3 | GC a cada N feeds |
| JINGLE_MAX_CHARS | 4000 | Caracteres máx. do boletim |

### 2.4 TTS Pipeline

```
Texto bruto → normalizer (num2words) → Piper/Edge-TTS → .wav → ffmpeg → .mp3

PT-BR: Piper voz "faber" (ARM NEON, offline) → Edge-TTS "AntonioNeural" (fallback)
EN:    Piper voz "amy" (ARM NEON, offline)   → Edge-TTS "ChristopherNeural" (fallback)
```

---

## 3. Linha do Tempo de Desenvolvimento

| Data | Marco | Commit |
|------|-------|--------|
| 2026-06-16 | NewsBot v3 base — 17 feeds, Edge-TTS PT | `275e02a` |
| 2026-06-17 | Pipeline v4 iniciado — branch `v4` | `26c9ca4` |
| 2026-06-17 | Piper TTS offline (faber PT + amy EN) | `26c9ca4` |
| 2026-06-17 | Normalizador num2words (PT+EN) | `26c9ca4` |
| 2026-06-17 | Podcast diário via ffmpeg concat | `097f1bf` |
| 2026-06-18 | AzuraCast jingle — upload API REST | `30952d5` |
| 2026-06-19 | Alertas Telegram no início de cada run | `c4cfaf8` |
| 2026-06-19 | Expansão 17→27 feeds (música + Irlanda) | `dd0d8ca` |
| 2026-06-20 | **Boletim jornalístico** (estilo telejornal) | `4ef8ae9` |
| 2026-06-20 | Correção cache TTS (`force=True`) | `4ef8ae9` |
| 2026-06-20 | SCP backup para Samba HDRadio | `4ef8ae9` |
| 2026-06-20 | Documentação técnica + testes bateria | `4ef8ae9` |

---

## 4. Issues, Causas e Correções

### 4.1 Issues Resolvidas

| # | Severidade | Issue | Causa Raiz | Correção | Status |
|---|-----------|-------|-----------|----------|--------|
| 1 | 🔴 CRÍTICO | Jingle nunca atualizava — sempre o mesmo áudio | Cache em `generate_audio_file()` retornava arquivo existente sem regenerar | Parâmetro `force=True` ignora cache; jingle sempre fresco | ✅ |
| 2 | 🔴 CRÍTICO | Playlist "News Jingles" sempre vazia (0 arquivos) | AzuraCast API upload retorna 200 mas arquivo não persiste no filesystem; playlist perde vínculo após upload | SCP direto para Samba (`/mnt/radio_hdd/news_jingles/`); usuário adiciona via UI | ⚠️ Parcial |
| 3 | 🔴 CRÍTICO | Portfolio `health.json` VAZIO (0KB) | Pi5 não tinha script de coleta de saúde; cron de health inexistente | Criado `collect_health.sh` no Pi5 (cron */10 min); score=86/A | ✅ |
| 4 | 🔴 CRÍTICO | Portfolio rebase travado desde Jun 17 | `git rebase` interrompido deixou `.git/rebase-merge` pendente | `git rebase --abort` + `rm -rf .git/rebase-merge` + merge remote | ✅ |
| 5 | 🔴 CRÍTICO | `news.json` estagnado (último update Jun 17) | Consequência do rebase travado — push era rejeitado | Rebase resolvido → push OK → news.json fresco (15 itens) | ✅ |
| 6 | 🟡 MÉDIO | Piper EN `lessac` não disponível | Modelo `en_US-lessac-medium` requer AVX512 (x86); RPi é ARM64 | Substituído por `en_GB-amy-medium` (ARM NEON) | ✅ |
| 7 | 🟡 MÉDIO | AzuraCast `/files` endpoint timeout | Biblioteca de mídia enorme (+1000 arquivos); API lenta | Timeout reduzido para 5s na listagem; fallback SCP ignora API lenta | ✅ |
| 8 | 🟡 MÉDIO | AzuraCast `/media` search timeout | Mesma causa — biblioteca grande | Reduzido timeout; usa SCP como caminho primário | ✅ |
| 9 | 🟡 MÉDIO | `azuracast_news.py` não adicionava à playlist | Código original só fazia upload, não geria playlist | Adicionada função `_add_to_playlist()` (timeout causa fallback) | ⚠️ Parcial |
| 10 | 🟢 BAIXO | WAV→MP3 conversão desnecessária em cache hit | Cache retornava WAV sem converter; upload precisava de MP3 | `force=True` força regeneração completa | ✅ |
| 11 | 🟢 BAIXO | Saúde Pi5 offline no portfolio | Script de health collection não existia no Pi5 | `collect_health.sh` instalado: CPU, RAM, disco, Docker, temp | ✅ |
| 12 | 🟢 BAIXO | Spin Magazine RSS lento (3.176s) | Servidor do feed responde devagar | Aceitável — 1 de 27 feeds; timeout global de 15s cobre | ✅ |
| 13 | 🟢 BAIXO | Folha de S.Paulo charset warning | Feed declara `us-ascii` mas entrega `iso-8859-1` | feedparser ignora; funcionalidade preservada | ✅ |

### 4.2 Issues Pendentes

| # | Severidade | Issue | Bloqueio | Workaround Atual |
|---|-----------|-------|----------|-----------------|
| P1 | 🔴 CRÍTICO | Playlist "News Jingles" vazia — precisa adição manual | API AzuraCast não expõe endpoint funcional para gerenciar itens da playlist | Usuário adiciona `news_jingle.mp3` via UI (1 clique) |
| P2 | 🟡 MÉDIO | Arquivos multi-feed não implementados | Plano criado mas não executado (task #4 pendente) | Jingle único cobre todas as notícias (~65s) |
| P3 | 🟢 BAIXO | AzuraCast v0.23.1 → v0.23.6 update disponível | Atualização requer downtime da rádio | Não crítico — versão atual funcional |

---

## 5. Resultados da Bateria de Testes

### 5.1 Latência E2E (13 feeds)

| Métrica | Valor |
|---------|-------|
| Tempo total 13 feeds | **8.668s** |
| Média por feed | **0.667s** |
| +Rápido | Dublin Live (0.124s) |
| +Lento | Spin Magazine (3.176s) |
| Total de entries | 363 |
| Falhas | 0 (100% sucesso) |

### 5.2 Latência TTS (Piper offline)

| Teste | Chars | Tempo | Output | Velocidade |
|-------|-------|-------|--------|------------|
| PT curto | 35 | 0.797s | 107KB | 44 cps |
| PT longo | 211 | 3.410s | 587KB | 62 cps |
| EN curto | 33 | 0.945s | 172KB | 35 cps |
| EN longo | 210 | 2.873s | 761KB | 73 cps |
| Boletim (36 notícias) | 3956 | ~35s | 10530KB | ~113 cps |

### 5.3 Conversão WAV→MP3

| De | Para | Tempo | Compressão |
|----|------|-------|------------|
| 587KB WAV | 107KB MP3 | 0.286s | 18.2% |
| 10530KB WAV | 1911KB MP3 | 1.5s | 18.1% |

### 5.4 Pipeline Completo (dry-run)

| Métrica | Valor |
|---------|-------|
| 27 feeds dry-run | **12.985s** |
| Exit code | 0 |
| Notícias novas | 6 |

### 5.5 Perfil de Memória

| Estágio | RSS | Delta |
|---------|-----|-------|
| Baseline | 23MB | — |
| Config + feeds | 23MB | +0MB |
| Todos imports | 63MB | +40MB |
| 5 feeds RSS | 67MB | +4MB |
| TTS jingle | 67MB | +0MB |
| **Peak** | **67MB** | 0.8% da RAM (8GB) |

### 5.6 Integridade do Portfolio

| Verificação | Status |
|-------------|--------|
| news.json | ✅ 15 itens, fresco |
| health.json | ✅ 536B, Pi5 score=86/A |
| radio_metadata.json | ✅ 2KB |
| Site ao vivo | ✅ 200, 0.212s, 42KB |
| Seções (news/health/radio) | ✅ Todas presentes |

### 5.7 AzuraCast

| Verificação | Status |
|-------------|--------|
| Now Playing API | ✅ `John Peel 010927 128K — Niag` |
| Jingle na Samba | ✅ 1.9MB, atualizado 18:41 |
| Playlist "News Jingles" | ⚠️ Vazia (0 itens) |
| Histórico de jingles | ⚠️ Nunca tocou |

---

## 6. Diagrama de Fluxo do Jingle

```
Cron dispara (00:00, 06:00, 12:00, 18:00)
    │
    ▼
run_newsbot.sh
    │
    ├── nice -n 19 ionice -c 2 python main.py
    │       │
    │       ├── Coleta 27 feeds RSS (feedparser, ~9s)
    │       ├── Filtra duplicatas (histórico 200 itens)
    │       ├── Gera áudio por feed (Piper TTS, ~2s/feed)
    │       ├── Envia Telegram (áudio + resumo)
    │       │
    │       └── _generate_azuracast_jingle()
    │               │
    │               ├── Agrupa notícias por região
    │               ├── Monta texto estilo telejornal
    │               ├── TTS Piper PT (force=True, ~35s)
    │               ├── ffmpeg WAV→MP3 (64kbps, ~1.5s)
    │               ├── POST AzuraCast API (upload)
    │               └── SCP → /mnt/radio_hdd/news_jingles/
    │
    ├── sync_git.sh
    │       ├── Push news_colletector → GitHub
    │       └── sync_portfolio.sh → robcarv.github.io
    │
    └── Health check
            └── SSH pi5 → cat /home/robert/health_reports/health.json
```

---

## 7. Estrutura de Diretórios

```
news_colletector/
├── main.py                  # Orquestrador principal
├── run_newsbot.sh           # Wrapper de execução
├── sync_git.sh              # Push GitHub + portfolio
├── sync_portfolio.sh        # Push robcarv.github.io
├── feeds_config.json        # 27 feeds RSS
├── history.json             # Histórico de duplicatas (200 itens)
├── .env                     # Credenciais (BOT_TOKEN, AZURACAST_API_KEY, etc.)
├── TECHNICAL_DOCS.md        # Este documento
│
├── src/
│   ├── config.py            # Configuração central
│   ├── collector.py         # Coleta RSS (feedparser)
│   ├── processor.py         # Resumo LSA (Sumy)
│   ├── audio.py             # TTS (Piper/Edge-TTS)
│   ├── normalizer.py        # Normalização num2words
│   ├── notifier.py          # Telegram API
│   ├── azuracast_news.py    # Upload AzuraCast + SCP Samba
│   └── podcast.py           # Podcast diário (ffmpeg)
│
├── data/
│   └── audio/               # Áudios gerados (.wav)
│       ├── BBC_News_20260620.wav
│       ├── ... (69 arquivos, 39MB total)
│       └── news_jingle.wav  # Boletim atual
│
├── logs/
│   ├── app.log              # Log agregado
│   ├── cron.log             # Saída do crontab
│   └── newsbot_*.log        # Log por execução
│
├── piper/                   # Binário Piper TTS ARM64
├── piper_voices/            # Modelos de voz
│   ├── pt_BR-faber-medium.onnx
│   └── en_GB-amy-medium.onnx
│
└── venv/                    # Ambiente virtual Python 3.11
```

---

## 8. Comandos de Operação

### 8.1 Execução Manual

```bash
cd ~/Documents/vscode_projects/news_colletector

# Dry-run (todos os feeds, sem enviar nada)
venv/bin/python3 main.py --dry-run

# Feed específico
venv/bin/python3 main.py --feed 3

# Forçar regeneração do jingle
rm data/audio/news_jingle.wav data/audio/news_jingle.mp3
venv/bin/python3 main.py --dry-run  # simula sem enviar

# Pipeline completo
bash run_newsbot.sh
```

### 8.2 Verificação

```bash
# Verificar logs do último run
tail -50 logs/newsbot_$(date +%Y-%m-%d)_180001.log

# Verificar saúde do Pi5
ssh robert@pi5 "cat /home/robert/health_reports/health.json | python3 -m json.tool"

# Verificar arquivos na Samba
ssh robert@pi5 "ls -lh /mnt/radio_hdd/news_jingles/"

# Verificar playlist AzuraCast
curl -s -H "Authorization: Bearer $(grep AZURA .env | cut -d= -f2)" \
  "https://dublincalling.duckdns.org/api/station/2/playlist/34" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(f'items={len(d.get(\"media_items\",[]))}')"

# Verificar rádio ao vivo
curl -s "https://dublincalling.duckdns.org/api/nowplaying/2" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); s=d['now_playing']['song']; print(f'{s[\"title\"]} — {s[\"artist\"]}')"
```

### 8.3 Manutenção

```bash
# Limpar áudios antigos (>3 dias)
find data/audio -name "*.wav" -mtime +3 -delete

# Limpar logs antigos (>20 execuções)
ls -t logs/newsbot_*.log | tail -n +21 | xargs rm -f

# Recriar venv
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

---

## 9. Configuração do Ambiente

### 9.1 Pi501-117 (NewsBot host)

```
- Raspberry Pi 5 (ARM64, 8GB RAM)
- IP: 192.168.68.117
- Crontab:
    0 0 * * *      run_newsbot.sh --podcast
    0 6,12,18 * * * run_newsbot.sh
- SSH key para pi5 configurada (id_ed25519)
- Dependências: Python 3.11, ffmpeg, Piper TTS
```

### 9.2 Pi5-108 (AzuraCast + Rádio)

```
- Raspberry Pi 5 (ARM64)
- IP: 192.168.68.108
- AzuraCast Docker v0.23.1 (container único)
- Samba share: \\192.168.68.108\HDRadio → /mnt/radio_hdd/
- Health collection: /home/robert/health_reports/collect_health.sh (cron */10)
- Docker containers: azuracast, azuracast_updater (7 total)
```

### 9.3 Variáveis de Ambiente (.env)

```bash
BOT_TOKEN=***              # Token do bot Telegram @NewsCollectorBot
CHAT_ID=***                # Chat ID para entrega
AZURACAST_API_KEY=***      # API key com permissão de upload
SPOTIFY_CLIENT_SECRET=***  # (legado, não usado)
```

---

## 10. Playbook de Troubleshooting

| Sintoma | Diagnóstico | Solução |
|---------|-------------|---------|
| Jingle não toca na rádio | Playlist "News Jingles" vazia | Adicionar `news_jingle.mp3` via UI |
| Áudio sempre igual | Cache TTS ativo | `force=True` (já implementado) |
| `health.json` vazio | Pi5 offline ou script parou | `ssh robert@pi5 'bash /home/robert/health_reports/collect_health.sh'` |
| Portfolio não atualiza | Rebase travado ou push rejeitado | `cd ~/Documents/portfolio-html && git pull --rebase && git push` |
| Telegram não envia | Token ou Chat ID errado | Verificar `.env`; testar: `curl "https://api.telegram.org/bot$TOKEN/getMe"` |
| Feed sem notícias | Servidor offline ou RSS quebrado | Log mostra "0 notícias coletadas" — normal para feeds lentos |
| Piper TTS falha | Binário ou voz ausente | Verificar: `ls piper/piper piper_voices/pt_BR-faber-medium.onnx` |
| Conexão SSH pi5 falha | Key não configurada | `ssh-copy-id robert@pi5` |
| AzuraCast upload 200 mas sem arquivo | API não persiste no disco | SCP direto cobre (implementado) |

---

*Documento gerado por Hermes Agent — 2026-06-20 18:45 UTC*
*Branch: v4 | Commit: 4ef8ae9*
