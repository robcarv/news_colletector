# Pi501 (192.168.68.117) — Cron Jobs

**Hostname:** raspberrypi501
**Uptime:** 6d 23h
**RAM:** 7.9GB (3.7GB used)
**Disk:** 117GB (43GB used - 39%)
**Docker:** 14 containers rodando

---

## Cron Tabela

| # | Nome | Schedule | Tipo | Origem | Descricao |
|---|------|----------|------|--------|-----------|
| 1 | NewsBot | 0,6,12,18 * * * | crontab user | news_colletector | Coleta RSS de 17 feeds, gera audio TTS, envia Telegram |
| 2 | komga-sync | every 30m | Hermes cron | no_agent script | Verifica downloads concluidos, cria CBZ, aciona scan Komga |
| 3 | homelab-health | every 60m | Hermes cron | no_agent script | Health check de todos os servicos do homelab |
| 4 | homelab-full-scan | every 360m (6h) | Hermes cron | no_agent script | Scan profundo + push health.json para GitHub Pages |
| 5 | gallery-precache | a cada ~6h | systemd timer | gallery-precache.service | Pre-cache de metadados do gallery |
| 6 | Pi.Alert | interno | interno | Pi.Alert container | Scan de dispositivos na rede local |

### Scripts associados

- `sync_git.sh` — chamado pelo NewsBot, faz git push do news_colletector
- `sync_portfolio.sh` — chamado pelo sync_git, faz push do robcarv.github.io
- `run_newsbot.sh` — wrapper do NewsBot com nice/ionice, timeout 10min, git push apos execucao

### Docker Containers

nhentai-frontend, nhentai-backend, uptime-kuma, changedetection (+2 browsers),
whisparr, prowlarr, speedtest-tracker, Dashy, portainer_agent, wallos,
glances, nginx-proxy-manager
