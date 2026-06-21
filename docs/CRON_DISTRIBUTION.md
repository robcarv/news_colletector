# Cron Distribution — Homelab 3 Pis

## Visão Geral

Distribuição otimizada para evitar picos de CPU sobrepostos.
Todos os jobs estão em `nice -n 19 ionice -c 2 -n 7`.

## Distribuição por Minuto (hora típica)

```
:00  ▓░░░░░░░░░  idle
:03  ▓▓▓░░░░░░░  Pi501 news-sync-push (Hermes)
:07  ▓▓▓░░░░░░░  Pi501 homelab-health (Hermes)
:12  ▓▓▓▓▓▓▓░░░  Pi5 guardian + Pi501 portfolio-health (Hermes)
:15  ▓▓▓▓▓▓▓▓▓░  Pi501 NewsBot (4x/dia)
:24  ▓▓▓░░░░░░░  Pi5 guardian.sh
:33  ▓▓▓░░░░░░░  Pi501 news-sync-push (Hermes)
:36  ▓▓▓░░░░░░░  Pi5 guardian.sh
:48  ▓▓▓░░░░░░░  Pi5 guardian.sh
```

## Jobs por Máquina

### Pi501 (192.168.68.102) — Orquestrador

| Job | Ferramenta | Schedule | Script | Descrição |
|-----|-----------|----------|--------|-----------|
| news-sync-push | Hermes Cron | `3,33 * * * *` | `~/.hermes/scripts/news_sync_push.sh` | Sincroniza notícias com GitHub Pages |
| homelab-health | Hermes Cron | `7 * * * *` | `~/.hermes/scripts/health_all_nodes.py` | Coleta métricas dos 3 Pis via Glances API v4 |
| portfolio-health | Hermes Cron | `12 * * * *` | `~/.hermes/scripts/portfolio_health_push.sh` | Gera health.json e push para robcarv.github.io |
| cve-scan | Hermes Cron | `0 2,8,14,20 * * *` | `~/.hermes/scripts/cve_scan_trigger.sh` | Scan de vulnerabilidades no Pi4 (4x/dia) |
| backup-all | Hermes Cron | `0 1 * * *` | `~/.hermes/scripts/backup_pipeline.sh` | Backup completo (1x/dia às 01:00) |
| cleanup | Hermes Cron | `0 4 * * *` | `~/.hermes/scripts/cleanup_all_nodes.sh` | Limpeza de logs/temp (1x/dia às 04:00) |
| NewsBot | crontab | `15 0,6,12,18 * * *` | `run_newsbot.sh` | Coleta + exporta notícias (4x/dia) |
| NewsBot+podcast | crontab | `15 0 * * *` | `run_newsbot.sh --podcast` | Podcast diário (1x/dia) |

### Pi5 (192.168.68.117) — Serviços

| Job | Ferramenta | Schedule | Script | Descrição |
|-----|-----------|----------|--------|-----------|
| guardian | crontab | `*/12 * * * *` | `guardian.sh` | Health check dos containers Docker |
| ~~collect_all_health~~ | ~~crontab~~ | ~~`*/10 * * * *`~~ | ~~`collect_all_health.py`~~ | ❌ Removido (redundante — Hermes cobre) |

### Pi4 (192.168.68.108) — Storage

Sem jobs de cron dedicados. Glances expõe métricas passivamente na API v4.

## Mudanças Recentes (v4 — Jun 2026)

| Data | Mudança | Impacto |
|------|---------|---------|
| 2026-06-21 | guardian.sh: `*/5` → `*/12` | -58% execuções/dia (288→120) |
| 2026-06-21 | collect_all_health.py removido do Pi5 | -144 execuções/dia |
| 2026-06-21 | NewsBot: `:00` → `:15` | Evita conflito com news-sync-push `:03` |
| 2026-06-21 | Hermes jobs espaçados: `:03`, `:07`, `:12` | Sem overlap entre health/news/portfolio |
| 2026-06-21 | Todos scripts Hermes migrados para Glances API v4 | `/api/4/cpu`, `/api/4/mem`, etc |

## Regras de Ouro

1. **Nunca sobrepor jobs no mesmo minuto** — diferencial mínimo de 2 min
2. **Novos jobs sempre em `nice -n 19`** — baixa prioridade de CPU e I/O
3. **Sempre verificar espaço em disco** antes de jobs pesados (`df /`)
4. **Cron jobs do sistema são independentes** do Hermes — coordenar via horários
5. **Glances API v4** em todos os endpoints — `/api/3/` foi deprecado

## Repositórios Afetados

| Repo | Branch | Arquivo | Papel |
|------|--------|---------|-------|
| `robcarv/news_colletector` | v4 | `run_newsbot.sh` | Executado pelo crontab Pi501 |
| `robcarv/robcarv.github.io` | main | `health.json` | Gerado por `portfolio_health_push.sh` |
| `~/.hermes/scripts/` | — | `*.sh`, `*.py` | Scripts orquestrados pelo Hermes Cron |
