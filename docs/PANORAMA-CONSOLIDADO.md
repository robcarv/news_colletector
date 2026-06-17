# Panorama Consolidado — Homelab Cron Jobs

> Documento final do full scan de cron jobs (Jun 2026).
> Inclui inventario, analise de redundancias, proposta de unificacao e roadmap.

---

## 1. Maquinas

| Hostname | IP | Role | Uptime | RAM | Disk | Docker |
|----------|----|------|--------|-----|------|--------|
| raspberrypi501 | 192.168.68.117 | ORQUESTRADOR | 6d 23h | 7.9GB | 117GB (39%) | 14 containers |
| raspberrypi5 | 192.168.68.108 | WORKER midia | 2d 21h | 7.9GB | 117GB (66%) | 7 containers |
| raspberrypi4 | 192.168.68.102 | WORKER rede | 6d 23h | 7.6GB | 116GB (19%) | varios |
| truenas | 192.168.68.124 | STORAGE | 6d 23h | - | 10.9TB (16%) | - |

---

## 2. Inventario de Cron Jobs

### Pi501 — 6 crons atuais

| # | Nome | Schedule | Tipo | Funcao |
|---|------|----------|------|--------|
| 1 | NewsBot | 0,6,12,18 | crontab | RSS + TTS + Telegram + git push |
| 2 | komga-sync | 30min | Hermes cron | Cria CBZ + scan Komga |
| 3 | homelab-health | 60min | Hermes cron | Ping servicos |
| 4 | homelab-full-scan | 360min | Hermes cron | Scan profundo + push health.json |
| 5 | gallery-precache | ~6h | systemd | Pre-cache metadados |
| 6 | Pi.Alert | interno | container | Scan rede |

### Pi5 — 7 crons atuais

| # | Nome | Schedule | Tipo | Funcao |
|---|------|----------|------|--------|
| 1 | binfmt | @reboot | crontab | Emulacao x86_64 |
| 2 | torrent_health | 6h | crontab | Health qBittorrent |
| 3 | torrent_antivirus | 03:00 | crontab | ClamAV scan |
| 4 | guardian.sh | 5min | crontab | Load/RAM/swap corretivo |
| 5 | mount_cifs.sh | 5min | crontab | Monta CIFS TrueNAS |
| 6 | backup_rpi_v4 | Seg/Qua/Sex 03:30 | crontab | Backup completo 3 Pis |
| 7 | update_health.py | 30min | crontab | Gera health.json + push |

### Pi4 — 2 crons atuais

| # | Nome | Schedule | Tipo | Funcao |
|---|------|----------|------|--------|
| 1 | binfmt | @reboot | crontab | Emulacao x86_64 |
| 2 | backup_rpi.sh | Seg/Qua/Sex 03:00 | crontab | Backup so Pi4 |

### TrueNAS — 0 crons de usuario

Tasks internas: Cloud Sync, Snapshots ZFS, SMART, Scrub.

**Total de crons gerenciados: 15**

---

## 3. Redundancias Identificadas

| Tipo | Severidade | Envolvidos | Solucao |
|------|-----------|------------|---------|
| Health checks triplicados | ALTA | homelab-health, homelab-full-scan, update_health.py | Eliminar update_health.py, expandir full-scan |
| Git syncs duplicados | MEDIA | sync_git.sh, sync_portfolio.sh, backup_rpi_v4.sh | Criar git-sync-unified, eliminar 2 |
| Backup cruzado | BAIXA | backup_rpi.sh (Pi4) + backup_rpi_v4.sh (Pi5) | Eliminar backup_rpi.sh (coberto pelo v4) |
| binfmt duplicado | NENHUMA | Pi4 + Pi5 | Manter (necessario local) |

---

## 4. Proposta Final — Estado Unificado

### Pi501 — 7 crons finais (+1, -0)

| Cron | Schedule | Origem |
|------|----------|--------|
| NewsBot | 0,6,12,18 | Mantido |
| git-sync-unified | 0,6,12,18 | NOVO (substitui 2) |
| homelab-health | 60min | Mantido |
| homelab-full-scan | 360min | Expandido (health.json) |
| komga-sync | 30min | Mantido |
| log-cleanup | 24h | NOVO |
| backup-trigger | Seg/Qua/Sex 03:00 | NOVO (opcional) |

### Pi5 — 5 crons finais (-2)

| Cron | Schedule | Origem |
|------|----------|--------|
| guardian.sh | 5min | Mantido |
| mount_cifs.sh | 15min | REDUZIDO |
| torrent_health | 6h | Mantido |
| torrent_antivirus | 03:00 | Mantido |
| backup_rpi_v4 | Seg/Qua/Sex 03:30 | Mantido |

**Eliminados:** `update_health.py` (substituido por full-scan)

### Pi4 — 1 cron final (-1)

| Cron | Schedule | Origem |
|------|----------|--------|
| binfmt | @reboot | Mantido |

**Eliminados:** `backup_rpi.sh` (coberto pelo v4 do Pi5)

### TrueNAS — sem mudancas

### Total de crons finais: 10 (-33%)

---

## 5. Impacto

| Metrica | Antes | Depois | Diferenca |
|---------|-------|--------|-----------|
| Crons totais | 15 | 10 | -33% |
| Scripts de sync | 3 | 1 | -67% |
| SSH calls/dia | ~200 | ~50 | -75% |
| Execucoes CIFS/dia | 288 | 96 | -67% |
| Maquinas com cron user | 3 | 2 | -33% |
| Hermes cron jobs | 3 | 6 | +100% |

---

## 6. Roadmap

### Semana 1-2: Preparacao
- Criar `git-sync-unified.sh` no Pi501
- Rodar em paralelo com scripts antigos por 48h
- Expandir `homelab_full_scan.py` para gerar health.json

### Semana 2-3: Validacao
- Comparar health.json do full-scan vs update_health.py por 48h
- Desativar `update_health.py` no Pi5
- Criar `log-cleanup` como Hermes cron

### Semana 3-4: Finalizacao
- Desativar `sync_git.sh` e `sync_portfolio.sh`
- Ativar `git-sync-unified` como Hermes cron
- Desativar `backup_rpi.sh` no Pi4
- Reduzir `mount_cifs.sh` para 15min
- Opcional: criar `backup-trigger` no Pi501

---

## 7. Riscos e Rollback

| Mudanca | Risco | Rollback |
|---------|-------|----------|
| Eliminar update_health.py | MEDIO (portfolio desatualizado) | Reativar cron no Pi5 |
| Git sync unificado | BAIXO | Reativar scripts antigos |
| Eliminar backup_rpi.sh | BAIXO (coberto pelo v5) | Reativar cron |
| CIFS 15min | BAIXO | Voltar para 5min |
| Log cleanup | BAIXO | Ajustar retencao |

> Rollback de qualquer mudanca: menos de 5 minutos.
> Nenhuma mudanca causa downtime de servico critico.

---

## 8. Arquivos Gerados

```
docs/
  crons/
    PI501-CRONS.md            — Cron jobs do Pi501
    PI5-CRONS.md              — Cron jobs do Pi5
    PI4-CRONS.md              — Cron jobs do Pi4
    TRUENAS-CRONS.md          — Cron jobs do TrueNAS
  OVERLAP-ANALYSIS.md         — Redundancias identificadas
  UNIFICATION-PROPOSAL.md     — Arquitetura final proposta
  IMPACT-ANALYSIS.md          — Risco e retorno
  PANORAMA-CONSOLIDADO.md     — Este documento
```
