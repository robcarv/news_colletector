# News Collector v3.2

Coleta RSS feeds de notícias, sumariza com LSA, gera áudio com TTS (Edge-TTS para PT, Piper para EN) e envia para Telegram. Otimizado para Raspberry Pi.

---

## Funcionalidades

- **17 feeds RSS** de notícias e música (BR, IE, UK, US)
- **Áudio por idioma**: PT → Edge-TTS AntonioNeural (voz natural), EN → Piper Amy (offline)
- **Resumo consolidado**: 1 áudio (headlines) + 1 mensagem (resumo completo com links) por feed
- **Cache**: Evita reenviar a mesma notícia (history.json)
- **Metadados da rádio** (AzuraCast): integração opcional que enriquece a música tocando com Last.fm/MusicBrainz
- **Cron**: 08:00 e 20:00 todos os dias
- **Git push automático**: logs e histórico enviados para o GitHub

---

## Dependências

### Runtime
- Python 3.11+
- `feedparser` — parsing de RSS
- `sumy` + `nltk` — sumarização LSA
- `requests` — API Telegram e HTTP
- `python-dotenv` — variáveis de ambiente
- `edge-tts` — TTS natural para português (online)
- `Piper` — TTS offline para inglês (binário ARM64 incluso)

### Sistema
- `pigz` — compressão paralela (opcional, para performance)
- `ffmpeg` — manipulação de áudio (se necessário)

### Instalação
```bash
cd news_colletector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install edge-tts
```

---

## Como Executar

```bash
# Execução completa (todos os feeds)
./run_newsbot.sh

# Apenas simular (não envia nada)
./run_newsbot.sh --dry-run

# Feed específico (0 = Folha, 3 = BBC, etc.)
./run_newsbot.sh --feed 3

# Envio de metadados da música atual da rádio
./venv/bin/python azura_telegram_metadata.py --once

# Modo teste dos metadados
./venv/bin/python azura_telegram_metadata.py --test
```

---

## Estrutura

```
news_colletector/
├── main.py                    # Orquestrador principal
├── run_newsbot.sh             # Wrapper para cron (nice, timeout, git push)
├── sync_git.sh                # Git push automático
├── azura_telegram_metadata.py # Metadados enriquecidos da rádio
├── feeds_config.json          # Lista de feeds RSS
├── history.json               # Histórico de notícias já enviadas
├── .env                       # Tokens (BOT_TOKEN, CHAT_ID) — não comitar
├── .gitignore
├── src/
│   ├── audio.py               # TTS: Edge-TTS (PT) + Piper (EN)
│   ├── collector.py           # Coleta RSS via feedparser
│   ├── config.py              # Config centralizada
│   ├── notifier.py            # Envio Telegram (sessão HTTP reutilizável)
│   └── processor.py           # Sumarização LSA (sumy + nltk)
├── piper/                     # Piper TTS binário ARM64
│   └── piper
├── piper_voices/              # Modelos de voz
│   └── en_US-amy.onnx
├── data/audio/                # Áudios gerados
└── logs/                      # Logs de execução
```

---

## Feeds Configurados

| Feed | País | Idioma |
|------|------|--------|
| Folha de S.Paulo | 🇧🇷 | PT |
| Tenho Mais Discos Que Amigos | 🇧🇷 | PT |
| Irish Independent | 🇮🇪 | EN |
| Hot Press (Ireland) | 🇮🇪 | EN |
| GoldenPlec (Ireland Music) | 🇮🇪 | EN |
| BBC News | 🇬🇧 | EN |
| The Guardian UK | 🇬🇧 | EN |
| MusicRadar (UK) | 🇬🇧 | EN |
| NME Music (UK) | 🇬🇧 | EN |
| The Guardian US | 🇺🇸 | EN |
| The Guardian Tech | 🇺🇸 | EN |
| Pitchfork | 🇺🇸 | EN |
| Rolling Stone Music (US) | 🇺🇸 | EN |
| Consequence of Sound (US) | 🇺🇸 | EN |
| Metal Injection | 🇺🇸 | EN |
| IBM | 🇺🇸 | EN |
| Nintendo | 🇯🇵 | EN |

---

## Cron

O NewsBot roda 2x ao dia via crontab do usuário:

```
0 8,20 * * * cd /home/robert/Documents/vscode_projects/news_colletector && bash run_newsbot.sh >> logs/cron.log 2>&1
```

Para editar: `crontab -e`

---

## Otimizações Raspberry Pi

- `nice -n 19` + `ionice -c 2 -n 7` — prioridade baixa
- `gc.collect()` a cada 3 feeds — garbage collection periódico
- Timeout de 15s por feed RSS (não trava em feeds lentos)
- Sessão HTTP reutilizável (`requests.Session`)
- `MAX_ITEMS_PER_FEED = 2` — apenas 2 notícias por feed
- `MAX_AUDIO_CHARS = 1200` — áudio curto (~20s)
- Timeout global de 10 minutos no script wrapper

---

## GitHub

```bash
git remote -v
origin  git@github.com:robcarv/news_colletector.git (fetch)
origin  git@github.com:robcarv/news_colletector.git (push)
```
