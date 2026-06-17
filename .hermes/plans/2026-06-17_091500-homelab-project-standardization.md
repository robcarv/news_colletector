# Homelab Project Standardization Plan

> **Para Hermes:** Plan-only. Nao executar. Validar com Robert antes de qualquer mudanca.

**Goal:** Padronizar todos os projetos do homelab em `~/Documents/docker/<projeto>/` por maquina, eliminando orfaos em `~/`, duplicatas case-sensitive (`Docker` vs `docker`), e lixo (gallery_logs duplicados, test.zip de 1.3GB, diretorios obsoletos).

**Architecture:** Scan completo das 4 maquinas, mapeamento de todos os projetos com docker-compose.yml, plano de migracao por maquina com rollback seguro (mv, nao rm), limpeza de logs duplicados, e documentacao final.

**Tech Stack:** SSH, mv, docker compose, git.

---

## Cenario Atual (Descoberto no Scan)

### Pi501 (.117) — PIOR SITUACAO

```
Documents/
  docker/        ← lowercase (3 projetos)
    backup_raspberry/
    dashy/
    nginx_pm/
  Docker/        ← uppercase (8 projetos) — DUPLICATE CASE!
    comdown-test/
    dashy/               ← DUPLICADO com Documents/docker/dashy/
    gallery-v3/
    glances/
    kemono-test/
    nhentai-downloader-v2-archive/
    passive-income/
    wallos/
  portfolio-html/
  vscode_projects/
    azura-cast-customizations/
    news_colletector/
    whisparr/
    data/
    test.zip               ← 1.3GB LIXO!

~/ (orfaos)
  changedetection/   ← docker-compose.yml ativo
  prowlarr/          ← docker-compose.yml ativo
  speedtest/         ← docker-compose.yml ativo
  uptime-kuma/       ← docker-compose.yml ativo
  whisparr/          ← docker-compose.yml ativo
  qbittorrent/       ← docker-compose.yml ativo
  gallery-v3/        ← codigo (nao compose)
  gallery-cache/     ← cache data
  gallery-logs/      ← logs (possivel duplicado)
  gallery_logs/      ← logs (possivel duplicado)
  repo/              ← repositorio obsoleto?
  robcarv_repo_tmp/  ← temporario
  absminitowerkit/   ← projeto extra
```

**Total: 6 orfaos com compose ativo + 3 dirs de gallery duplicados + case conflict + 1.3GB lixo**

### Pi5 (.108) — SEMI-ORGANIZADO

```
Documents/docker/
  changedetection/
  dashy/
  DuckDns/
  duplicati/
  earnapp/
  gallery-downloader-v2/    ← arquivado? v2 vs v3
  ghostfolio/
  keycloack/
  uptime-kuma/
  whisparr/
  portfolio-html/

~/ (orfaos)
  gallery-v3/        ← ATIVO (app.py + scrapers/)
  qbittorrent/       ← docker-compose ativo
  clamav/            ← dados
  gallery-logs/      ← logs (possivel duplicado)
  gallery_logs/      ← logs (possivel duplicado)
  health_reports/    ← reports
  prowlarr/          ← verificar se tem compose
  speedtest/         ← verificar se tem compose
  whisparr/          ← verificar se tem compose
```

**Total: ~4 orfaos com compose + gallery-v3 ativo fora do padrao + gallery_logs duplicado**

### Pi4 (.102) — MAIS ORGANIZADO

```
Documents/docker/
  backup_raspberry/
  duplicati/
  nginx_pm/
  speedtest/
Documents/Docker/           ← DUPLICATE CASE!
  dashy/
  duplicati/                ← DUPLICADO com Documents/docker/duplicati/
  passive-income/
Documents/
  backup_raspberry_repo/
  backup_repo/
  vscode_projects_dev/
```

**Total: Case conflict + duplicati duplicado + 3 dirs extras**

### TrueNAS (.124)

OK — storage apenas. Nenhum projeto de codigo. `/mnt/nvme1/robert/` para dados pessoais.

---

## Plano de Padronizacao

### REGRA GERAL

```
~/Documents/docker/<projeto>/
  docker-compose.yml
  .env
  data/           (opcional — volumes)
  README.md       (opcional)
```

- TUDO em lowercase: `Documents/docker/`
- Nada de projeto solto em `~/`
- Nada de `Documents/Docker/` (case errado)
- Projetos de codigo sem compose (ex: news_colletector) ficam em `~/Documents/vscode_projects/`
- Portainer stacks em `/data/compose/N/` sao gerenciados pelo Portainer — documentar, nao mexer

---

## Fase 1 — Pi4 (.102) [MAIS SIMPLES — comecar por aqui]

### Task 1.1: Consolidar case conflict (Docker -> docker)

**Objetivo:** Mover conteudo de `Documents/Docker/` para `Documents/docker/`, resolver duplicatas.

**Situacao:**
| docker/ | Docker/ | Acao |
|---------|---------|------|
| backup_raspberry | — | Manter |
| duplicati | duplicati | Resolver qual e o ativo |
| nginx_pm | — | Manter |
| speedtest | — | Manter |
| — | dashy | Mover para docker/dashy |
| — | passive-income | Mover para docker/passive-income |

**Comando (read-only primeiro):**
```bash
# 1. Verificar qual duplicati esta ativo
ssh pi4 "docker compose -f ~/Documents/docker/duplicati/compose.yml ps 2>&1"
ssh pi4 "docker compose -f ~/Documents/Docker/duplicati/compose.yml ps 2>&1"

# 2. Mover projetos que so existem em Docker/
ssh pi4 "mv ~/Documents/Docker/dashy ~/Documents/docker/dashy"
ssh pi4 "mv ~/Documents/Docker/passive-income ~/Documents/docker/passive-income"

# 3. Resolver duplicati (assumindo docker/ ativo, arquivar Docker/)
ssh pi4 "mv ~/Documents/Docker/duplicati ~/Documents/docker/duplicati.OLD_$(date +%Y%m%d)"

# 4. Remover dir vazio
ssh pi4 "rmdir ~/Documents/Docker/ 2>/dev/null || echo 'ainda tem arquivos'"
```

**Verificacao:** `docker compose ls` mostra todos os stacks no caminho `~/Documents/docker/...`

### Task 1.2: Mover dirs extras para dentro de Documents/

**Objetivo:** Consolidar `backup_raspberry_repo`, `backup_repo`, `vscode_projects_dev`.

```bash
ssh pi4 "mv ~/Documents/backup_raspberry_repo ~/Documents/docker/backup_raspberry/docs 2>&1 || mv ~/Documents/backup_raspberry_repo ~/Documents/docker/backup_raspberry_repo"
ssh pi4 "mv ~/Documents/backup_repo ~/Documents/docker/backup_repo"
ssh pi4 "mv ~/Documents/vscode_projects_dev ~/Documents/vscode_projects"
```

---

## Fase 2 — Pi5 (.108) [MEDIO — gallery-v3 e orfaos]

### Task 2.1: Mover orfaos com docker-compose para Documents/docker/

**Orfaos identificados:** qbittorrent, e verificar prowlarr/speedtest/whisparr

```bash
# Verificar quais tem docker-compose
for d in qbittorrent prowlarr speedtest whisparr; do
  ssh pi5 "ls ~/$d/docker-compose.yml ~/$d/compose.yml 2>&1"
done

# Mover os que tem compose
ssh pi5 "docker compose -f ~/qbittorrent/docker-compose.yml down && mv ~/qbittorrent ~/Documents/docker/qbittorrent && docker compose -f ~/Documents/docker/qbittorrent/docker-compose.yml up -d"
```

**CUIDADO:** Fazer um de cada vez, com `down` antes do `mv` e `up -d` depois.

### Task 2.2: Consolidar gallery (v2 vs v3)

**Situacao:**
- `~/gallery-v3/` — ATIVO (app.py, scrapers/, frontend/)
- `~/Documents/docker/gallery-downloader-v2/` — v2 (arquivado? ou ainda usado?)

```bash
# Verificar se v2 esta rodando
ssh pi5 "docker compose -f ~/Documents/docker/gallery-downloader-v2/docker-compose.v2.yml ps 2>&1"

# Padronizar: gallery-v3 vai para Documents/docker/gallery-v3
ssh pi5 "systemctl stop gallery-v3.service 2>/dev/null; mv ~/gallery-v3 ~/Documents/docker/gallery-v3"

# Atualizar caminhos no systemd service e scripts
```

### Task 2.3: Limpar gallery-logs duplicados

**Situacao:** `~/gallery-logs/` e `~/gallery_logs/` — duplicados.

```bash
# Verificar quais sao usados
ssh pi5 "diff -r ~/gallery-logs ~/gallery_logs 2>&1 | head -20"

# Se identicos, remover um
ssh pi5 "rm -rf ~/gallery_logs"  # manter ~/gallery-logs
```

### Task 2.4: Mover dirs de dados para lugares logicos

```bash
ssh pi5 "mv ~/health_reports ~/Documents/docker/gallery-v3/health_reports 2>/dev/null"
ssh pi5 "mv ~/clamav ~/Documents/docker/clamav 2>/dev/null"
ssh pi5 "mv ~/portfolio-html ~/Documents/portfolio-html 2>/dev/null"
```

---

## Fase 3 — Pi501 (.117) [COMPLEXO — 6 orfaos com compose ativo + case conflict]

### Task 3.1: Consolidar case conflict (Docker -> docker)

**Situacao:**
| docker/ | Docker/ | Acao |
|---------|---------|------|
| backup_raspberry | — | Manter |
| dashy | dashy | Resolver — manter o ATIVO em docker/dashy |
| nginx_pm | — | Manter |
| — | comdown-test | Mover para docker/ |
| — | gallery-v3 | Mover para docker/ |
| — | glances | Mover para docker/ |
| — | kemono-test | Mover para docker/ |
| — | nhentai-downloader-v2-archive | Mover para docker/ |
| — | passive-income | Mover para docker/ |
| — | wallos | Mover para docker/ |

```bash
# 1. Identificar qual dashy esta rodando
ssh pi501 "docker compose -f ~/Documents/docker/dashy/compose.yml ps 2>&1"
ssh pi501 "docker compose -f ~/Documents/Docker/dashy/compose.yml ps 2>&1"

# 2. Mover tudo de Documents/Docker/ para Documents/docker/
# Exceto dashy se docker/dashy for o ativo
ssh pi501 bash << 'SCRIPT'
cd ~/Documents/Docker/
for d in */; do
  d=${d%/}
  if [ -d ~/Documents/docker/$d ]; then
    echo "CONFLITO: $d existe em ambos — verificar"
  else
    echo "MOVENDO: $d"
    mv $d ~/Documents/docker/
  fi
done
SCRIPT
```

### Task 3.2: Migrar orfaos com docker-compose ativo (CRITICO — 6 containers rodando)

**Orfaos ativos em ~/:**
- changedetection (compose running)
- prowlarr (compose running)
- speedtest (compose running)
- uptime-kuma (compose running)
- whisparr (compose running)
- qbittorrent (compose running)

**PRECAUCAO:** Downtime de <30 segundos por servico.

```bash
# Para cada servico:
ssh pi501 "cd ~/changedetection && docker compose down && cd && mv changedetection ~/Documents/docker/changedetection && cd ~/Documents/docker/changedetection && docker compose up -d"
```

**Ordem recomendada (menos critico primeiro):**
1. speedtest (ninguem nota se cair)
2. qbittorrent (se nao tiver download ativo)
3. changedetection (web scraping, pode esperar)
4. prowlarr (indexer, pode esperar)
5. uptime-kuma (monitoring — breve downtime)
6. whisparr (midia pipeline — ultimo)

### Task 3.3: Padronizar gallery-v3

```bash
# gallery-v3 em ~/ vs Documents/Docker/gallery-v3
# Verificar qual e o ativo
ssh pi501 "ls -la ~/gallery-v3/app.py ~/Documents/Docker/gallery-v3/app.py 2>&1"

# Se o ativo for ~/gallery-v3, mover para Documents/docker/gallery-v3
```

### Task 3.4: Mover vscode_projects para padrao

**Situacao:** vscode_projects em `~/Documents/vscode_projects/` — OK, e onde projetos de codigo ficam. Mas limpar lixo.

```bash
# Remover test.zip (1.3GB!)
ssh pi501 "rm ~/Documents/vscode_projects/test.zip"

# Mover diretorios extra:
ssh pi501 "mv ~/Documents/portfolio-html ~/Documents/vscode_projects/portfolio-html"
```

### Task 3.5: Limpar diretorios obsoletos/redundantes

```bash
# gallery-logs e gallery_logs (verificar se duplicados)
ssh pi501 "diff -r ~/gallery-logs ~/gallery_logs 2>&1 | head"

# gallery-cache (pode ser regenerado? verificar)
ssh pi501 "ls -la ~/gallery-cache/ 2>&1 | head"

# robcarv_repo_tmp (temporario, remover)
ssh pi501 "rm -rf ~/robcarv_repo_tmp"

# repo/ (verificar o que e)
ssh pi501 "ls -la ~/repo/ 2>&1"
```

---

## Fase 4 — TrueNAS (.124)

Nenhuma acao necessaria. Apenas documentar.

---

## Fase 5 — Verificacao e Documentacao Final

### Task 5.1: Validar todos os docker compose stacks

```bash
# Em cada maquina, verificar se todos os stacks estao UP e no caminho correto
for ip in 117 108 102; do
  echo "=== $ip ==="
  ssh pi$ip "docker compose ls"
done
```

### Task 5.2: Gerar inventario final

Estrutura esperada apos padronizacao:

```
Pi501 (.117):
  ~/Documents/docker/
    backup_raspberry/
    changedetection/
    comdown-test/
    dashy/
    gallery-v3/
    glances/
    kemono-test/
    nhentai-downloader-v2-archive/
    nginx_pm/
    passive-income/
    prowlarr/
    qbittorrent/
    speedtest/
    uptime-kuma/
    wallos/
    whisparr/

Pi5 (.108):
  ~/Documents/docker/
    changedetection/
    clamav/
    dashy/
    DuckDns/
    duplicati/
    earnapp/
    gallery-downloader-v2/    (arquivado)
    gallery-v3/               (ativo)
    ghostfolio/
    keycloack/
    qbittorrent/
    uptime-kuma/
    whisparr/

Pi4 (.102):
  ~/Documents/docker/
    backup_raspberry/
    backup_repo/
    dashy/
    duplicati/
    nginx_pm/
    passive-income/
    speedtest/
```

### Task 5.3: Commit e push

```bash
cd ~/Documents/vscode_projects/news_colletector
git add docs/
git commit -m "docs: project standardization plan - homelab workspace cleanup"
git push origin main
```

---

## Resumo

| Metrica | Antes | Depois | Diferenca |
|---------|-------|--------|-----------|
| Case conflicts (Docker/docker) | 2 maquinas | 0 | -100% |
| Orfaos em ~/ com compose | 10 | 0 | -100% |
| Diretorios gallery duplicados | 4 pares | 0 | -100% |
| Lixo (test.zip 1.3GB) | 1 | 0 | -1.3GB |
| Portainer /data/compose/N/ | documentado | documentado | mesmo |
| Docker compose stacks em ~/ | 10 | 0 | todos em Documents/docker/ |

---

## Riscos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| Container nao sobe apos mv | BAIXA | MEDIO | `down` antes de `mv`, `up -d` depois. Se falhar: `mv` de volta |
| Dois dashy diferentes conflitam | MEDIA | BAIXO | Verificar qual compose e o ativo, arquivar o outro |
| Perda de dados em gallery_logs | BAIXA | BAIXO | `diff` antes de remover |
| Pi501 instavel (historico de travamentos) | MEDIA | ALTO | Fazer fora do horario critico. Deixar menos containers para o final |
| AzuraCast em /var/azuracast | NENHUMA | NENHUM | NAO MEXER — fora do escopo |

---

## Ordem de Execucao (por seguranca)

1. Pi4 (.102) — mais simples, impacto minimo
2. Pi5 (.108) — medio, gallery-v3 e alguns orfaos
3. Pi501 (.117) — complexo, 6 containers rodando, downtime coordenado
