# NewsBot v4 — Documentação Técnica Completa

> **Repositório:** `git@github.com:robcarv/news_colletector.git`
> **Branch:** `v4`
> **Diretório:** `~/Documents/vscode_projects/news_colletector/`
> **Host:** Raspberry Pi 5 (ARM64, Linux 6.12.87+rpt-rpi-2712)
> **Data do Documento:** 2026-06-20
> **Versão do Pipeline:** v4.0

---

## 1. Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                     NewsBot v4 Pipeline                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CRON (4x/dia)                                               │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐       │
│  │ 00:00 UTC│    │ 06/12/18 UTC │    │ run_newsbot.sh │       │
│  │ --podcast│    │     normal    │    │ nice/ionice   │       │
│  └────┬─────┘    └──────┬───────┘    │ timeout 600s   │       │
│       │                 │            └───────┬───────┘       │
│       └────────┬────────┘                    │               │
│                ▼                             │               │
│  ┌─────────────────────────────┐             │               │
│  │         main.py             │◄────────────┘               │
│  │  News Collector v4          │                             │
│  └──────────┬──────────────────┘                             │
│             │                                                │
│     ┌───────┼───────┬──────────┬──────────┐                 │
│     ▼       ▼       ▼          ▼          ▼                 │
│  collector audio  processor  notifier  azuracast_news        │
│  (RSS)   (TTS)   (Sumy)    (Telegram)  (upload MP3)         │
│     │       │       │          │          │                  │
│     │  ┌────┴────┐  │          │    ┌─────┴──────┐          │
│     │  │Piper    │  │    ┌─────┴──┐ │AzuraCast   │          │
│     │  │(offline)│  │    │Telegram│ │Dublin      │          │
│     │  │Edge-TTS │  │    │  API   │ │Calling FM  │          │
│     │  │(online) │  │    └────────┘ └────────────┘          │
│     │  └─────────┘  │                                       │
│  ┌──┴──┐         ┌──┴────┐                                  │
│  │feed │         │normal │                                  │
│  │parser│        │izer   │                                  │
│  │      │        │num2w  │                                  │
│  └─────┘         │ords   │                                  │
│                  └───────┘                                  │
│                                                              │
│  SAÍDAS:                                                    │
│  ├── Telegram: áudio .wav + mensagem texto/resumo           │
│  ├── AzuraCast: jingle MP3 (playlist "News Jingles")        │
│  ├── Portfolio: news.json → robcarv.github.io               │
│  └── GitHub: push automático (news_colletector + portfolio) │
└──────────────────────────────────────────────────────────────┘
```

## 2. Componentes

### 2.1 Módulos Python

| Módulo | Função | Dependências |
|--------|--------|-------------|
| `main.py` | Orquestrador: coleta, processa, envia, gera jingle | Todos os src/* |
| `src/config.py` | Config central: paths, env, limites (MAX_ITEMS=4, MAX_AUDIO=2500) | dotenv, pathlib |
| `src/collector.py` | Coleta RSS via feedparser (timeout 15s, 4 itens/feed) | feedparser |
| `src/processor.py` | Resumo LSA via Sumy (3 sentenças) + clean HTML | sumy, nltk |
| `src/audio.py` | TTS: Piper offline (PT/EN) + Edge-TTS fallback | subprocess, edge-tts |
| `src/normalizer.py` | Converte números/datas/%/R$ para fala natural | num2words, re |
| `src/notifier.py` | Telegram: sendMessage e sendAudio (Markdown, timeout 30s) | requests |
| `src/azuracast_news.py` | Upload jingle MP3 via REST API AzuraCast | requests, ffmpeg |
| `src/podcast.py` | Gera podcast diário (intro + notícias + outro via ffmpeg) | ffmpeg |
| `run_newsbot.sh` | Wrapper shell: nice/ionice, timeout, sync git, logs | bash |

### 2.2 Configuração (`feeds_config.json`)

| # | Feed | Idioma | Categoria |
|---|------|--------|-----------|
| 1 | Folha de S.Paulo | pt | Notícias BR |
| 2 | Nintendo | en | Games |
| 3 | IBM | en | Tech corporativo |
| 4 | BBC News | en | Notícias UK |
| 5 | Pitchfork | en | Música indie |
| 6 | Metal Injection | en | Metal |
| 7 | Irish Independent | en | Notícias Irlanda |
| 8 | Hot Press (Ireland) | en | Música Irlanda |
| 9 | The Guardian UK | en | Notícias UK |
| 10 | The Guardian US | en | Notícias US |
| 11 | The Guardian Tech | en | Tecnologia |
| 12 | Tenho Mais Discos | pt | Música BR |
| 13 | MusicRadar (UK) | en | Música/equipamento |
| 14 | NME Music (UK) | en | Música UK |
| 15 | Rolling Stone Music | en | Música US |
| 16 | GoldenPlec (Ireland) | en | Música Irlanda |
| 17 | Consequence of Sound | en | Música US |
| 18 | RockBizz (Brasil) | pt | Rock BR |
| 19 | Rolling Stone Brasil | pt | Música BR |
| 20 | Irish News Entertainment| en | Entretenimento IE |
| 21 | Dublin Live News | en | Notícias Dublin |
| 22 | Billboard (US) | en | Música mainstream |
| 23 | Stereogum (US) | en | Música indie |
| 24 | BrooklynVegan (US) | en | Música indie |
| 25 | Loudwire (US) | en | Rock/Metal |
| 26 | Spin Magazine (US) | en | Música |
| 27 | NME News (UK) | en | Música UK |

**Total: 27 feeds** (5 PT-BR, 22 EN)

### 2.3 Limites e Constraints

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| MAX_ITEMS_PER_FEED | 4 | Notícias coletadas por feed |
| MAX_AUDIO_CHARS | 2500 | Caracteres máx por áudio TTS |
| MAX_SUMMARY_SENTENCES | 3 | Sentenças no resumo Sumy |
| MAX_HISTORY | 200 | Títulos no histórico de duplicatas |
| RETENTION_DAYS | 3 | Dias para manter áudios |
| DOWNLOAD_TIMEOUT | 15s | Timeout coleta RSS |
| TELEGRAM_TIMEOUT | 30s | Timeout API Telegram |
| GC_INTERVAL | 3 | Garbage collection a cada N feeds |

### 2.4 TTS Pipeline

```
Texto bruto
    │
    ▼
normalize_pt() / normalize_en()
    │  • 2026 → "dois mil e vinte e seis"
    │  • 15:30 → "três e meia"
    │  • 85%  → "oitenta e cinco por cento"
    │  • R$ 50 → "cinquenta reais"
    │
    ▼
generate_audio_file()
    ├── PT: Piper (faber, offline) → Edge-TTS (AntonioNeural, fallback)
    └── EN: Piper (amy, offline) → Edge-TTS (ChristopherNeural, fallback)
    │
    ▼
Arquivo .wav (~500KB-1MB por feed)
```

### 2.5 AzuraCast Integration

```
main.py → _generate_azuracast_jingle()
    │
    ├── 1. Separa PT/EN com fontes
    ├── 2. Monta jingle profissional:
    │      "Dublin Calling. Seu resumo de notícias.
    │       Do Brasil: [3 headlines com fonte].
    │       Internacional: [5 headlines com fonte].
    │       Notícias atualizadas a cada seis horas.
    │       Dublin Calling — a sua rádio."
    ├── 3. TTS via Piper (PT, faber) → .wav
    ├── 4. ffmpeg WAV→MP3 (64kbps mono)
    └── 5. POST /api/station/2/files/upload → AzuraCast
         Playlist: "News Jingles" (Once per 30 min, AutoDJ)
```

### 2.6 Cron Jobs

```
# crontab
0 0 * * * cd ~/Documents/vscode_projects/news_colletector && bash run_newsbot.sh --podcast
0 6,12,18 * * * cd ~/Documents/vscode_projects/news_colletector && bash run_newsbot.sh
```

- **00:00 UTC** → Modo podcast (jingle + podcast diário)
- **06:00, 12:00, 18:00 UTC** → Modo normal (jingle + áudios + Telegram)

### 2.7 Portfolio Sync

O `run_newsbot.sh` também:
1. Gera `news.json` a partir do `history.json` (últimos 15 itens)
2. Atualiza `radio_metadata.json` via `azura_metadata.py`
3. Roda `sync_git.sh` → push para `robcarv/robcarv.github.io`

## 3. Problemas Conhecidos e Soluções

### 3.1 Histórico de Issues

| # | Problema | Causa | Solução | Status |
|---|----------|-------|---------|--------|
| 1 | Piper EN `lessac` não disponível | ARM64 sem AVX512 | Trocar para `en_GB-amy-medium` (ARM NEON) | ✅ |
| 2 | TTS Edge-TTS requer internet | Modo offline RPi | Piper offline como primário, Edge-TTS fallback | ✅ |
| 3 | Números lidos "dois zero dois seis" | TTS lê dígitos | `normalizer.py`: num2words converte tudo | ✅ |
| 4 | ffmpeg concat: Path object | Path vs string | Converter Path → str + arquivo list temp | ✅ |
| 5 | STATION_ID=1 errado | Dublin Calling é ID 2 | Corrigido: GET /api/stations → ID=2 | ✅ |
| 6 | Endpoint upload `/files` errado | API v2 usa `/files/upload` | Corrigido para POST /files/upload | ✅ |
| 7 | Portfolio push diverged | Remote tem commits de outra máquina | `git fetch + rebase` (mas falha se rebase pendente) | ⚠️ |
| 8 | Pi5 health.json offline | Pi5 desligado ou cron falhou | Log registra mas não bloqueia pipeline | ⚠️ |
| 9 | history.json > 100KB | Muitos títulos acumulados | MAX_HISTORY=200 com truncate | ✅ |
| 10 | Telegram caption > 1024 chars | Limitação API Telegram | Trunca caption, envia texto completo separado | ✅ |

### 3.2 Issue Ativo: Portfolio Rebase Travado

```
fatal: It seems that there is already a rebase-merge directory
```

**Causa:** O `robcarv.github.io` tem um rebase interrompido (provavelmente de uma execução anterior que conflitou com push de outra máquina).

**Impacto:** `news.json` não está sendo enviado para o portfolio (último push rejeitado).

**Solução necessária:**
```bash
cd ~/Documents/portfolio-html
rm -rf .git/rebase-merge
git rebase --abort
git pull --rebase origin main
git push origin main
```

## 4. Logs e Monitoramento

### Estrutura de Logs
```
logs/
├── app.log                          # Log agregado (rotacionado via Python logging)
├── cron.log                         # Saída do crontab
└── newsbot_YYYY-MM-DD_HHMMSS.log    # Log por execução
```

### Métricas da Última Execução (18:00 UTC)

| Métrica | Valor |
|---------|-------|
| Feeds carregados | 27 |
| Feeds com notícias novas | 4 |
| Total notícias novas | 7 |
| Tempo total | ~30s |
| Tempo coleta RSS (27 feeds) | ~17s |
| Tempo TTS jingle (Piper) | ~6s |
| Tempo upload AzuraCast | ~2s |
| Tempo sync git | ~3s |
| Código de saída | 0 |
| Portfolio push | ❌ (rebase travado) |

## 5. Testes

### 5.1 Comandos de Teste

```bash
# Dry-run (todos os feeds, sem enviar)
python main.py --dry-run

# Feed específico
python main.py --feed 0 --dry-run

# Modo podcast
python main.py --podcast --dry-run

# Normalizador
python src/normalizer.py

# Teste manual completo (sem dry-run)
python main.py --feed 0
```

### 5.2 Verificação AzuraCast

```bash
# Listar estações
curl -s -H "Authorization: Bearer $AZURACAST_API_KEY" \
  https://dublincalling.duckdns.org/api/stations | jq

# Ver arquivos na pasta news_jingles
curl -s -H "Authorization: Bearer $AZURACAST_API_KEY" \
  "https://dublincalling.duckdns.org/api/station/2/files?path=news_jingles" | jq

# Status do AutoDJ
curl -s -H "Authorization: Bearer $AZURACAST_API_KEY" \
  https://dublincalling.duckdns.org/api/nowplaying/2 | jq '.now_playing'
```

---

*Documento gerado por Hermes Agent — 2026-06-20*
