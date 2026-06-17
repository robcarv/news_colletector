# Homelab Cron Jobs — Full Scan & Unification Plan

> **Para Hermes:** Executar tarefa por tarefa sequencialmente. Nao precisa de subagents — o escopo e pequeno e cada fase depende da anterior.

**Goal:** Fazer full scan dos 4 nodes do homelab (3 Pis + TrueNAS), catalogar todos os cron jobs rodando, documentar o que cada um faz, identificar redundancias entre maquinas, e propor unificacao em um unico orquestrador centralizado no Pi501 (192.168.68.117).

**Architecture:** Cada node e acessado via SSH com credenciais conhecidas. O scan coleta crontabs de usuarios (robert, root), systemd timers, containers Docker com schedules internos, e cron jobs do Hermes Agent. O resultado e um inventario tabulado por maquina, seguido de analise de sobreposicao e proposta de consolidacao.

**Tech Stack:** SSH, crontab, systemctl, docker, hermes cron, grep/awk para parsing.

---

## Fase 0 — Pre-scan: Mapeamento dos nodes

**Objetivo:** Confirmar acesso SSH e coletar info basica de cada maquina.

### Maquinas

| Hostname | IP | User | Pass | Role |
|---|---|---|---|---|
| Pi501 (Pi5) | 192.168.68.117 | robert | Dhr1042@ | Hermes Agent, Dashy, Cron orquestrador |
| Pi5 | 192.168.68.108 | robert | Dhr1042@ | Gallery v3, AzuraCast, Uptime Kuma |
| Pi4 | 192.168.68.102 | robert | Dhr1042@ | Pi-hole, NPM, Wallos |
| TrueNAS | 192.168.68.124 | robert | Totvs@123#456 | Storage, Jellyfin, Komga |

### Task 1: Testar conectividade SSH

**Objetivo:** Verificar se todos os nodes respondem a SSH.

**Comandos:**
```bash
for ip in 192.168.68.117 192.168.68.108 192.168.68.102; do
  sshpass -p 'Dhr1042@' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 robert@$ip "hostname && uptime -p" 2>&1
done
```

**Verificacao:** Cada node retorna hostname + uptime sem erro.

### Task 2: Testar acesso TrueNAS

**Objetivo:** Verificar acesso ao TrueNAS (SSH ou API).

**Comando:**
```bash
sshpass -p 'Totvs@123#456' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 robert@192.168.68.124 "hostname && uname -a" 2>&1
```

**Nota:** TrueNAS Scale pode ou nao ter SSH habilitado. Se falhar, tentar via API REST:
```bash
curl -sk -X POST "https://192.168.68.124/api/v2.0/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"robert","password":"Totvs@123#456"}' 2>&1
```

---

## Fase 1 — Coleta de Cron Jobs por Maquina

### Task 3: Pi501 (192.168.68.117) — Coletar crons

**Objetivo:** Extrair cron jobs do usuario robert, root, systemd timers, Docker auto-restart policies, e cron jobs do Hermes Agent.

**Comando unico:**
```bash
sshpass -p 'Dhr1042@' ssh -o StrictHostKeyChecking=no robert@192.168.68.117 bash -s << 'EOF'
echo "=== HOSTNAME ==="
hostname
echo "=== CRONTAB USER ==="
crontab -l 2>&1
echo "=== CRONTAB ROOT (sudo) ==="
sudo crontab -l 2>&1
echo "=== SYSTEMD TIMERS ==="
systemctl list-timers --all --no-pager 2>&1
echo "=== DOCKER RESTART POLICIES ==="
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.RestartPolicy}}" 2>&1
echo "=== DOCKER AUTO-RESTART CONTAINERS ==="
docker ps -a --filter "status=exited" --filter "name=auto-restart" --format "{{.Names}}" 2>&1
echo "=== UPTIME ==="
uptime
EOF
```

**Extra — Hermes cron jobs (roda local):**
```bash
hermes cron list 2>&1
```

**Arquivos importantes para inspecionar:**
- `~/.hermes/scripts/` — scripts de cron do Hermes
- `~/.hermes/skills/` — skills que contem logicas de cron
- `~/Documents/vscode_projects/news_colletector/` — scripts do NewsBot e syncs

### Task 4: Pi5 (192.168.68.108) — Coletar crons

**Objetivo:** Extrair cron jobs do usuario robert, root, systemd timers, Docker containers.

**Comando:**
```bash
sshpass -p 'Dhr1042@' ssh -o StrictHostKeyChecking=no robert@192.168.68.108 bash -s << 'EOF'
echo "=== HOSTNAME ==="
hostname
echo "=== CRONTAB USER ==="
crontab -l 2>&1
echo "=== CRONTAB ROOT (sudo) ==="
sudo crontab -l 2>&1
echo "=== SYSTEMD TIMERS ==="
systemctl list-timers --all --no-pager 2>&1
echo "=== DOCKER CONTAINERS ==="
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.RestartPolicy}}" 2>&1
echo "=== DOCKER COMPOSE STACKS ==="
docker compose ls 2>&1
echo "=== GALLERY SCRIPTS ==="
ls -la /home/robert/gallery-v3/scrapers/*.py 2>&1
ls -la /home/robert/gallery-v3/scripts/*.sh 2>&1
echo "=== UPTIME ==="
uptime
EOF
```

### Task 5: Pi4 (192.168.68.102) — Coletar crons

**Objetivo:** Extrair cron jobs do usuario robert, root, systemd timers, Docker containers.

**Comando:**
```bash
sshpass -p 'Dhr1042@' ssh -o StrictHostKeyChecking=no robert@192.168.68.102 bash -s << 'EOF'
echo "=== HOSTNAME ==="
hostname
echo "=== CRONTAB USER ==="
crontab -l 2>&1
echo "=== CRONTAB ROOT (sudo) ==="
sudo crontab -l 2>&1
echo "=== SYSTEMD TIMERS ==="
systemctl list-timers --all --no-pager 2>&1
echo "=== DOCKER CONTAINERS ==="
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.RestartPolicy}}" 2>&1
echo "=== UPTIME ==="
uptime
EOF
```

### Task 6: TrueNAS (192.168.68.124) — Coletar crons

**Objetivo:** Extrair cron jobs do TrueNAS Scale — Cron Jobs, Cloud Sync Tasks, Periodic Snapshot Tasks, Rsync Tasks.

**Via SSH:**
```bash
sshpass -p 'Totvs@123#456' ssh -o StrictHostKeyChecking=no robert@192.168.68.124 bash -s << 'EOF'
echo "=== HOSTNAME ==="
hostname
echo "=== CRONTAB ==="
crontab -l 2>&1
echo "=== SYSTEMD TIMERS ==="
systemctl list-timers --all --no-pager 2>&1
EOF
```

**Via API REST (se SSH falhar):**
```bash
# Login pegar token
TOKEN=$(curl -sk -X POST "https://192.168.68.124/api/v2.0/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"robert","password":"Totvs@123#456"}' | python3 -c "import json,sys;print(json.load(sys.stdin))" 2>/dev/null)

# Listar Cron Jobs
curl -sk -H "Authorization: Bearer $TOKEN" \
  "https://192.168.68.124/api/v2.0/cronjob" 2>&1 | python3 -m json.tool 2>&1

# Cloud Sync Tasks
curl -sk -H "Authorization: Bearer $TOKEN" \
  "https://192.168.68.124/api/v2.0/cloudsync" 2>&1 | python3 -m json.tool 2>&1

# Periodic Snapshot Tasks
curl -sk -H "Authorization: Bearer $TOKEN" \
  "https://192.168.68.124/api/v2.0/periodicsnapshottask" 2>&1 | python3 -m json.tool 2>&1
```

---

## Fase 2 — Analise e Documentacao Individual

### Task 7: Catalogar cron jobs do Pi501

**Arquivo:** `docs/crons/PI501-CRONS.md`

Para cada cron encontrado:
- Nome / descricao
- Schedule (formato cron ou intervalo)
- Comando / script executado
- Dependencias (outros servicos, mounts, SSH para outras maquinas)
- Funcao no ecossistema
- Se roda local ou afeta outro node

**Crons esperados no Pi501:**
1. **NewsBot** — `/home/robert/Documents/vscode_projects/news_colletector/run_newsbot.sh` (0,6,12,18)
2. **sync_git.sh** — push automatico do news_colletector (0,6,12,18)
3. **sync_portfolio.sh** — push automatico do robcarv.github.io (0,6,12,18)
4. **homelab-health** — health check (cada 60min via Hermes cron)
5. **komga-sync** — sync de CBZ (cada 30min via Hermes cron)
6. **homelab-full-scan** — scan completo (cada 6h via Hermes cron)
7. **outros Hermes cron jobs** — listar todos

### Task 8: Catalogar cron jobs do Pi5 (108)

**Arquivo:** `docs/crons/PI5-CRONS.md`

**Crons esperados:**
1. **Gallery auto-repair** — reparo de CBZs faltantes (via script periodico)
2. **DuckDNS** — atualizacao de DNS dinamico (se via cron/sytemd)
3. **Speedtest** — pode ter cron de speedtest periodico
4. **Outros** — descobrir na Task 4

### Task 9: Catalogar cron jobs do Pi4 (102)

**Arquivo:** `docs/crons/PI4-CRONS.md`

**Crons esperados:**
1. **Pi-hole** — gravity update, log rotation (interno do Pi-hole)
2. **Pi.Alert** — scan periodico de rede (interno)
3. **Glances** — export de metricas (se configurado)
4. **Duplicati** — schedule de backup (pode ser systemd timer)
5. **Outros** — descobrir na Task 5

### Task 10: Catalogar cron jobs do TrueNAS (124)

**Arquivo:** `docs/crons/TRUENAS-CRONS.md`

**Crons esperados:**
1. **Cloud Sync Tasks** — backup para nuvem
2. **Periodic Snapshot Tasks** — snapshots ZFS
3. **Rsync Tasks** — sincronizacao entre pools
4. **SMART tests** — verificacao de saude dos discos
5. **Scrub tasks** — verificacao de integridade ZFS
6. **Outros** — descobrir na Task 6

---

## Fase 3 — Analise de Redundancia e Proposta de Unificacao

### Task 11: Mapear sobreposicoes entre maquinas

**Entregavel:** `docs/OVERLAP-ANALYSIS.md`

Identificar tarefas que:
- **Rodam em multiplas maquinas com mesma funcao** (ex: health check em todo lugar)
- **Dependem de resultados de outra maquina** (ex: sync de CBZ que precisa de scan)
- **Poderiam ser centralizadas** (ex: todos os git pushes num unico cron)
- **Sao dead/already replaced** (ex: scripts antigos que viraram cron do Hermes)

**Padroes comuns de redundancia:**
1. **Git syncs:** news_colletector + portfolio + possivelmente outros repos — poderiam ser um script unificado
2. **Health checks:** Hermes cron + Uptime Kuma + possivelmente scripts locais
3. **Log rotation:** Docker logs + systemd + paperspace
4. **Backups:** Duplicati + Cloud Sync + rsync manual

### Task 12: Propor arquitetura unificada

**Entregavel:** `docs/UNIFICATION-PROPOSAL.md`

Proposta de centralizar todos os crons no Pi501 via Hermes cron jobs:

```
Pi501 (Orquestrador)
  ├── NewsBot (0,6,12,18)           → roda local
  ├── Git Sync Unificado (0,6,12,18) → news + portfolio + docs
  ├── Homelab Health (60min)          → verifica todos os nodes
  ├── Gallery Sync (30min)            → trigger no Pi5 via SSH
  ├── TrueNAS Health (6h)             → verifica TrueNAS via API
  ├── Log Cleanup (24h)               → limpa logs antigos
  ├── Backup Trigger (24h)            → triggera backup no node certo
  └── DNS Update (5min)               → DuckDNS centralizado

Pi5 (Worker)
  ├── DuckDNS local (5min)            → manter se critical path
  └── Gallery operations              → trigger via SSH do Pi501

Pi4 (Worker)
  ├── Pi-hole gravity update           → interno do Pi-hole
  └── Pi.Alert scan                    → interno

TrueNAS (Storage)
  ├── Cloud Sync Tasks                → interno do TrueNAS
  ├── Snapshots ZFS                   → interno
  └── SMART / Scrub                   → interno
```

**Criterios de unificacao:**
1. Tarefas que _apenas disparam_ algo em outra maquina devem ser centralizadas
2. Tarefas que _coletam dados_ de multiplas fontes devem ser centralizadas
3. Tarefas criticas de infra local (DNS, DHCP, storage) ficam no node original
4. Tasks internas de containers (gravity update do Pi-hole) ficam onde estao

### Task 13: Estimar impacto e economia

**Entregavel:** `docs/IMPACT-ANALYSIS.md`

Para cada redundancia identificada:
- **O que muda** (pra onde vai, o que deixa de rodar)
- **Impacto em recursos** (CPU/RAM liberado, menos SSH calls)
- **Risco** (o que pode quebrar se o orquestrador cair)
- **Mitigacao** (fallback, retry, health check no orquestrador)
- **Complexidade** (facil/media/dificil)

---

## Fase 4 — Documentacao Final e Push

### Task 14: Gerar panorama consolidado

**Arquivo:** `docs/PANORAMA-CONSOLIDADO.md`

Documento final com:

1. **Resumo executivo** (1 paragrafo)
2. **Tabela de maquinas** com servicos e crons
3. **Tabela de cron jobs** — combinada de todas as maquinas
4. **Mapa de redundancias** — o que se sobrepoe
5. **Proposta de unificacao** — arquitetura final
6. **Roadmap de implementacao** — o que fazer em que ordem
7. **Riscos e rollback** — como desfazer se algo der errado

### Task 15: Push para repositorio privado

```bash
cd /home/robert/Documents/vscode_projects/news_colletector
git add .hermes/plans/ docs/
git commit -m "docs: homelab cron audit - full scan and unification plan"
git push origin main
```

---

## Resumo das Tarefas

| # | Fase | Tarefa | Tempo est. |
|---|---|---|---|
| 0 | Pre-scan | Testar SSH nos 4 nodes | 2min |
| 1 | Coleta | Pi501 crons + Hermes cron + scripts | 5min |
| 2 | Coleta | Pi5 (108) crons | 3min |
| 3 | Coleta | Pi4 (102) crons | 3min |
| 4 | Coleta | TrueNAS (124) crons (SSH ou API) | 5min |
| 5 | Analise | Catalogar Pi501 | 5min |
| 6 | Analise | Catalogar Pi5 | 5min |
| 7 | Analise | Catalogar Pi4 | 5min |
| 8 | Analise | Catalogar TrueNAS | 5min |
| 9 | Redundancia | Mapear sobreposicoes | 5min |
| 10 | Proposta | Arquitetura unificada | 5min |
| 11 | Impacto | Impacto e risco | 3min |
| 12 | Documentacao | Panorama consolidado | 5min |
| 13 | Push | Commit + push | 2min |
| | **Total** | | **~53min** |

---

## Diretorio de saída

```
.hermes/plans/
  2026-06-17_081500-homelab-cron-audit-unification.md  ← este plano

docs/
  crons/
    PI501-CRONS.md    — cron jobs do Pi501 (117)
    PI5-CRONS.md      — cron jobs do Pi5 (108)
    PI4-CRONS.md      — cron jobs do Pi4 (102)
    TRUENAS-CRONS.md  — cron jobs do TrueNAS (124)
  OVERLAP-ANALYSIS.md           — mapeamento de redundancias
  UNIFICATION-PROPOSAL.md       — proposta de arquitetura unificada
  IMPACT-ANALYSIS.md            — impacto, riscos, mitigacao
  PANORAMA-CONSOLIDADO.md       — documento final consolidado
```
