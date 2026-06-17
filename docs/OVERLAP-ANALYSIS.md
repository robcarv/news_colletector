# Overlap Analysis — Redundancias entre Maquinas

> Analise detalhada de cada sobreposicao de cron jobs no homelab.
> Identificado durante o full scan (Jun 2026).

---

## Resumo

| Tipo | Maquinas envolvidas | Severidade | Economia potencial |
|------|--------------------|------------|--------------------|
| Health checks triplicados | Pi501, Pi5 | ALTA | 3 crons -> 1 cron |
| Git syncs em 2 maquinas | Pi501, Pi5 | MEDIA | 2 scripts -> 1 script |
| Backup cruzado | Pi4, Pi5 | BAIXA | 1 cron eliminado |
| binfmt duplicado | Pi4, Pi5 | NENHUMA | Mantido (necessario local) |

---

## 1. Health Checks — TRIPLICADO (Severidade: ALTA)

### Crons envolvidos

| Cron | Maquina | Schedule | O que faz | Consome |
|------|---------|----------|-----------|---------|
| homelab-health | Pi501 | 60min | Ping servicos + discos | ~15 req HTTP, leve |
| homelab-full-scan | Pi501 | 360min | Scan profundo + push health.json | SSH nos 3 Pis + API TrueNAS, medio |
| update_health.py | Pi5 | 30min | Scan profundo em TODOS os Pis + push | SSH nos 3 Pis + Docker inspect, ALTO (48x/dia) |
| guardian.sh | Pi5 | 5min | So monitora Pi5 local | Local (load/mem/swap), leve |

### Sobreposicao

- `homelab-health` + `homelab-full-scan` rodam no Pi501 (mesma maquina, schedules diferentes)
- `update_health.py` no Pi5 faz EXATAMENTE o que `homelab-full-scan` faz: SSH nos 3 Pis, coleta metricas, gera health.json, push GitHub
- `guardian.sh` e o unico que nao se sobrepoe: e local, age corretivamente

### Impacto

- `update_health.py` faz 48 SSH calls/dia nos 3 Pis + TrueNAS = 144 conexoes SSH/dia
- `homelab-health` faz 24 chamadas HTTP/dia
- `homelab-full-scan` faz 4 scans profundos/dia

### Proposta

1. **Eliminar** `update_health.py` do Pi5 (substituido por `homelab-full-scan`)
2. **Expandir** `homelab-full-scan` para gerar health.json igual ao `update_health.py`
3. **Manter** `homelab-health` a cada 60min (ping rapido)
4. **Manter** `guardian.sh` no Pi5 (acao corretiva local)
5. **Nova contagem:** 3 crons -> 2 crons (elimina 1)

---

## 2. Git Syncs — DUPLICADO (Severidade: MEDIA)

### Crons envolvidos

| Cron/Script | Maquina | Schedule | Repos | Mecanica |
|------------|---------|----------|-------|----------|
| sync_git.sh + sync_portfolio.sh | Pi501 | 0,6,12,18 | news_colletector, robcarv.github.io | git add/commit/push |
| backup_rpi_v4.sh | Pi5 | Seg/Qua/Sex 03:30 | backup_raspberry | git add/commit/push |
| update_health.py | Pi5 | 30min | robcarv.github.io (health.json) | git add/commit/push |

### Sobreposicao

Cada script implementa git push manualmente com `GIT_SSH_COMMAND`, `GIT_AUTHOR_NAME`, etc. A mecanica e identica:
```bash
export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no"
git add .
git commit -m "mensagem"
git push origin main
```

### Impacto

- 3 scripts implementando a mesma logica = risco de divergencia
- Se a chave SSH rodar, todos quebram juntos (bom ponto de falha unico)
- Script do Pi5 escreve health.json que o Pi501 tambem escreve

### Proposta

1. **Criar** `git_sync_unified.sh` no Pi501 que:
   - news_colletector (0,6,12,18 — apos NewsBot)
   - robcarv.github.io (quando health.json mudar)
   - backup_raspberry (1x/dia)
2. **Eliminar** `sync_git.sh` e `sync_portfolio.sh` (substituidos)
3. **Manter** git push dentro do `backup_rpi_v4.sh` no Pi5 (e parte de um pipeline maior, nao so git)
4. **Nova contagem:** 3 scripts de sync -> 2 scripts (1 novo + 1 mantido)

---

## 3. Backup — CRUZADO (Severidade: BAIXA)

### Crons envolvidos

| Script | Maquina | Schedule | O que cobre |
|--------|---------|----------|-------------|
| backup_rpi.sh | Pi4 | Seg/Qua/Sex 03:00 | So Pi4 |
| backup_rpi_v4.sh | Pi5 | Seg/Qua/Sex 03:30 | Todos os 3 Pis + ClamAV + rsync + rclone + git |

### Sobreposicao

`backup_rpi_v4.sh` (Pi5) ja faz backup de TODOS os Pis, inclusive do Pi4.
`backup_rpi.sh` (Pi4) e um script mais antigo que so copia o Pi4 local para o TrueNAS.

### Risco

Se `backup_rpi_v4.sh` falhar, `backup_rpi.sh` do Pi4 nao e suficiente como fallback
porque ele nao cobre os outros Pis. Mas se ambos rodam, eles competem por recursos
de rede/IO no TrueNAS no mesmo horario (03:00 vs 03:30 — muito proximo).

### Proposta

1. **Eliminar** `backup_rpi.sh` do Pi4 (ja coberto pelo v4 do Pi5)
2. **Adicionar** verificacao de redundancia no v4: se o Pi4 executar backup ha menos de 12h, pular
3. **Nova contagem:** 2 backups -> 1 backup

---

## 4. binfmt — DUPLICADO (Severidade: NENHUMA)

### Crons envolvidos

| Maquina | Schedule | Comando |
|---------|----------|---------|
| Pi4 | @reboot | docker run --privileged --rm tonistiigi/binfmt --install x86_64 |
| Pi5 | @reboot | docker run --privileged --rm tonistiigi/binfmt --install x86_64 |

### Analise

Cada Pi precisa de emulacao x86_64 no seu proprio kernel para rodar containers
amd64. Nao ha como centralizar — e necessario em cada maquina.

### Proposta

**Manter** em ambos. Sem alteracao.

---

## 5. CIFS Mount (Severidade: BAIXA)

### Crons envolvidos

| Maquina | Script | Schedule |
|---------|--------|----------|
| Pi5 | mount_cifs.sh | 5min |

### Analise

So o Pi5 monta CIFS do TrueNAS (`/mnt/truenas_media`). O Pi501 nao monta CIFS.
Nao ha redundancia real, mas o schedule de 5min e agressivo.

### Proposta

1. **Reduzir** `mount_cifs.sh` de 5min para 15min (o CIFS dificilmente cai 12x/hora)
2. **Adicionar** log apenas quando realmente monta (nao quando ja esta montado)
3. **Nova contagem:** 288 execucoes/dia -> 96 execucoes/dia

---

## Resumo das Economias

| Item | Antes | Depois | Economia |
|------|-------|--------|----------|
| Health checks | 3 crons (2 maquinas) | 2 crons (1 maquina) | -1 cron, -48 SSH calls/dia |
| Git syncs | 3 scripts | 2 scripts | -1 script, logica centralizada |
| Backups | 2 scripts (2 maquinas) | 1 script (1 maquina) | -1 cron |
| CIFS mount | 288x/dia | 96x/dia | -192 mounts desnecessarios |
| **Total** | **10 crons/scripts** | **6 crons/scripts** | **-40% reducao** |
