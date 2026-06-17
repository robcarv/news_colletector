# Unification Proposal — Arquitetura Final de Cron Jobs

> Proposta de centralizacao dos cron jobs do homelab.
> Orquestrador: Pi501 (192.168.68.117) via Hermes Agent cron.

---

## Arquitetura Final

```
                    ┌─────────────────────────┐
                    │     Pi501 (.117)        │
                    │    ORQUESTRADOR         │
                    │                         │
                    │  Hermes Agent Cron      │
                    │  ┌──────────────────┐   │
                    │  │ NewsBot (6/12/18)│   │
                    │  │ Git Sync (6/12/18)│   │
                    │  │ Health Check(60m) │   │
                    │  │ Full Scan (360m) │   │
                    │  │ Gallery Sync(30m)│   │
                    │  │ Log Cleanup(24h) │   │
                    │  │ Backup Trigger   │   │
                    │  └──────────────────┘   │
                    │                         │
                    │  14 containers (local)  │
                    └──────────┬──────────────┘
                               │ SSH
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
 ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
 │ Pi5 (.108)   │   │ Pi4 (.102)   │   │ TrueNAS (.124)   │
 │ WORKER       │   │ WORKER       │   │ STORAGE          │
 │              │   │              │   │                  │
 │ Guardian(5m) │   │ Pi-hole auto │   │ Cloud Sync       │
 │ CIFS (15m)   │   │ Pi.Alert auto│   │ Snapshots ZFS    │
 │ Torrent(6h)  │   │              │   │ SMART / Scrub    │
 │ Antivirus(3h)│   │              │   │                  │
 │ Backup(3x/s) │   │              │   │                  │
 └──────────────┘   └──────────────┘   └──────────────────┘
```

---

## Cron Jobs — Estado Final Proposto

### Pi501 (.117) — Orquestrador

| # | Nome | Schedule | Tipo | Descricao |
|---|------|----------|------|-----------|
| 1 | NewsBot | 0,6,12,18 | crontab (local) | RSS + TTS + Telegram |
| 2 | git-sync-unified | 0,6,12,18 | Hermes cron | Push news_colletector + portfolio + health.json |
| 3 | homelab-health | 60min | Hermes cron no_agent | Ping servicos (leve) |
| 4 | homelab-full-scan | 360min | Hermes cron no_agent | Scan profundo + gera health.json + push |
| 5 | komga-sync | 30min | Hermes cron no_agent | Cria CBZ + scan Komga |
| 6 | log-cleanup | 24h | Hermes cron no_agent | Limpa logs Docker e systemd |
| 7 | backup-trigger | Seg/Qua/Sex 03:00 | Hermes cron | SSH no Pi5, executa backup_rpi_v4 |

### Pi5 (.108) — Worker

| # | Nome | Schedule | Tipo | Descricao |
|---|------|----------|------|-----------|
| 1 | guardian.sh | 5min | crontab local | Monitora load/RAM/swap, acao corretiva |
| 2 | mount_cifs.sh | 15min | crontab local | Monta CIFS (reduzido de 5 para 15min) |
| 3 | torrent_health | 6h | crontab local | Health check qBittorrent |
| 4 | torrent_antivirus | 03:00 | crontab local | ClamAV scan (mantido diario) |
| 5 | backup_rpi_v4 | Seg/Qua/Sex 03:30 | crontab local | Backup completo (trigger opcional do Pi501) |

### Pi4 (.102) — Worker

| # | Nome | Schedule | Tipo | Descricao |
|---|------|----------|------|-----------|
| 1 | binfmt | @reboot | crontab local | Emulacao x86_64 |
| 2 | Pi-hole gravity | interno | container | Update listas de bloqueio |
| 3 | Pi.Alert scan | interno | container | Scan de rede |

### TrueNAS (.124) — Storage

| # | Nome | Schedule | Tipo | Descricao |
|---|------|----------|------|-----------|
| 1 | Cloud Sync | configurado UI | interno | Backup para nuvem |
| 2 | Snapshots ZFS | configurado UI | interno | Snapshots periodicos |
| 3 | SMART Tests | configurado UI | interno | Saude dos discos |
| 4 | ZFS Scrub | configurado UI | interno | Integridade do pool |

---

## Mudancas Especificas

### ELIMINAR (5 itens)

| Item | Maquina | Motivo |
|------|---------|--------|
| update_health.py (.30min) | Pi5 | Substituido por homelab-full-scan no Pi501 |
| sync_git.sh | Pi501 | Substituido por git-sync-unified |
| sync_portfolio.sh | Pi501 | Substituido por git-sync-unified |
| backup_rpi.sh | Pi4 | Ja coberto pelo backup_rpi_v4.sh no Pi5 |
| mount_cifs.sh (5min) | Pi5 | Reduzir para 15min (nao eliminar) |

### CRIAR (2 itens)

| Item | Maquina | Descricao |
|------|---------|-----------|
| git-sync-unified | Pi501 | Script unico que faz push de news_colletector + portfolio + backup_raspberry |
| log-cleanup | Pi501 | Limpa logs antigos do Docker e systemd (1x/dia) |

### MANTER (8 itens)

| Item | Maquina | Justificativa |
|------|---------|---------------|
| NewsBot | Pi501 | Core, depende de RSS feeds locais |
| homelab-health | Pi501 | Ping leve a cada 60min |
| homelab-full-scan | Pi501 | Scan profundo a cada 6h (expandido) |
| komga-sync | Pi501 | Necessario para integracao Komga |
| guardian.sh | Pi5 | Unico com acao corretiva local |
| torrent_health | Pi5 | So Pi5 tem qBittorrent |
| torrent_antivirus | Pi5 | So Pi5 tem ClamAV |
| backup_rpi_v4 | Pi5 | Pipeline completo de backup |

### MODIFICAR (1 item)

| Item | Mudanca | Impacto |
|------|---------|---------|
| homelab-full-scan | Adicionar geracao de health.json igual ao update_health.py | Substitui o script do Pi5 |
| mount_cifs.sh | 5min -> 15min | -192 execucoes/dia |
| backup-trigger | Opcional: Pi501 pode triggerar backup no Pi5 via SSH | Centraliza o schedule |

---

## Contagem Final

| Metrica | Antes | Depois | Diferenca |
|---------|-------|--------|-----------|
| Crons ativos totais | 15 | 10 | -33% |
| Hermes cron jobs | 3 | 6 | +3 (centralizados) |
| Scripts de sync | 3 | 1 | -67% |
| SSH calls/dia | ~200+ | ~50 | -75% |
| Maquinas com cron user | 3 | 3 | Mesmo (roles diferentes) |

---

## Dependencias e Riscos

### Se Pi501 cair (orquestrador offline)

- NewsBot para de rodar (OK, nao critico)
- Komga sync para (OK, manual possivel)
- Git syncs nao acontecem (OK, push manual possivel)
- Health check nao roda (Uptime Kuma continua monitorando)
- **CRITICO:** Nada cai por causa disso — mas voce nao e notificado de falhas

### Se Pi5 cair (worker de midia)

- Torrents param de baixar
- Antivirus nao escaneia
- Backup nao roda
- Komga sync nao consegue criar CBZ (depende do CIFS e scripts no Pi5)
- **CRITICO:** Midia pipeline inteira para

### Mitigacoes recomendadas

1. **Health check paternal:** homelab-health notifica se Pi5 ou Pi4 estao offline
2. **Backup alternativo:** backup_rpi.sh do Pi4 pode ser mantido como fallback (desabilitado por padrao)
3. **Logs centralizados:** todos os scripts escrevem logs que podem ser verificados pelo homelab-health
