# Impact Analysis — Risco e Retorno da Unificacao

> Analise de impacto de cada mudanca proposta na Fase 3.
> Ordem proposta de implementacao.

---

## Sumario Executivo

A unificacao proposta reduz o numero de cron jobs em ~33% e elimina ~75% das
conexoes SSH diarias. Nenhuma mudanca causa downtime critico — todas sao
aditivas primeiro, destrutivas depois.

---

## Mudanca 1: Criar git-sync-unified.sh

### O que muda

| Antes | Depois |
|-------|--------|
| sync_git.sh (Pi501, 4x/dia) | git-sync-unified.sh (Pi501, 4x/dia) |
| sync_portfolio.sh (Pi501, 4x/dia) | (incorporado) |
| Git push dentro do backup_rpi_v4.sh (Pi5, 3x/sem) | (mantido separado) |

### Impacto

- **Recursos:** Igual (mesma frequencia de execucao, mesmo numero de pushes)
- **Manutencao:** Menor (1 script ao inves de 2)
- **Risco:** BAIXO — script novo, o antigo continua ate confirmar que o novo funciona

### Rollback

Manter `sync_git.sh` e `sync_portfolio.sh` renomeados como `.old` por 1 semana.

### Complexidade: FACIL

---

## Mudanca 2: Eliminar update_health.py do Pi5

### O que muda

| Antes | Depois |
|-------|--------|
| update_health.py (Pi5, 30min) gera health.json e push GitHub | homelab-full-scan (Pi501, 360min) assume geracao de health.json |

### Impacto

- **Recursos:** -48 execucoes/dia de Python + SSH, -144 conexoes SSH/dia
- **Frequencia de atualizacao do GitHub Pages:** cai de 30min para 6h
- **Risco:** MEDIO — se o `homelab-full-scan` nao gerar health.json identico, o portfolio fica desatualizado

### Mitigacao

1. Primeiro expandir `homelab_full_scan.py` no Pi501 para gerar health.json identico
2. Rodar ambos em paralelo por 48h e comparar os JSONs
3. S0 depois desativar `update_health.py` no Pi5

### Complexidade: MEDIA

---

## Mudanca 3: Eliminar backup_rpi.sh do Pi4

### O que muda

| Antes | Depois |
|-------|--------|
| backup_rpi.sh (Pi4, Seg/Qua/Sex 03:00) | Eliminado |

### Impacto

- **Recursos:** Libera ~5min de CPU/RAM no Pi4 a cada execucao
- **Cobertura:** Zero — `backup_rpi_v4.sh` no Pi5 ja cobre todos os 3 Pis
- **Risco:** BAIXISSIMO — o script v4 e mais completo e testado

### Verificacao

Confirmar que `backup_rpi_v4.sh` inclui os mesmos diretorios que `backup_rpi.sh`.

### Complexidade: FACIL

---

## Mudanca 4: Reduzir mount_cifs.sh de 5min para 15min

### O que muda

| Antes | Depois |
|-------|--------|
| mount_cifs.sh a cada 5min (288x/dia) | mount_cifs.sh a cada 15min (96x/dia) |

### Impacto

- **Recursos:** -192 execucoes/dia de `mount | grep -q`
- **Disponibilidade:** Se o CIFS cair, leva no maximo 15min para remontar (vs 5min antes)
- **Risco:** BAIXO — o CIFS do TrueNAS e estavel (6d+ de uptime)

### Justificativa

O script verifica se ja esta montado e sai imediatamente se sim. 95% das 288
execucoes/dia sao NO-OP. Reduzir para 15min mantem margem segura sem sobrecarga.

### Complexidade: FACIL (so mudar o cron)

---

## Mudanca 5: Adicionar log-cleanup no Pi501

### O que muda

| Antes | Depois |
|-------|--------|
| Sem limpeza programada de logs | Hermes cron 1x/dia: `docker system prune --force` + `journalctl --vacuum-time=7d` |

### Impacto

- **Recursos:** Libera ~1-5GB de disco por execucao (dependendo do acumulo)
- **Risco:** BAIXO — comandos padrao de limpeza

### Complexidade: FACIL

---

## Roadmap de Implementacao

```
Semana 1-2: Preparacao
  ├── [1] Criar git-sync-unified.sh no Pi501
  ├── [1] Rodar sync_git.sh e sync-unified.sh em paralelo
  └── [1] Confirmar que ambos produzem resultado identico

Semana 2-3: Health
  ├── [2] Expandir homelab_full_scan.py para gerar health.json
  ├── [2] Rodar homelab-full-scan + update_health.py em paralelo 48h
  └── [2] Comparar JSONs, ajustar se necessario

Semana 3: Desativacao
  ├── [2] Desativar update_health.py no Pi5
  ├── [1] Desativar sync_git.sh + sync_portfolio.sh
  ├── [1] Ativar git-sync-unified.sh como cron do Hermes
  ├── [3] Desativar backup_rpi.sh no Pi4
  └── [4] Reduzir mount_cifs.sh para 15min

Semana 4: Finalizacao
  ├── [5] Adicionar log-cleanup como Hermes cron
  ├── [5] Verificar se todos os crons antigos foram desativados
  └── [5] Documentar estado final
```

---

## Matriz de Risco

| # | Mudanca | Risco | Impacto se falhar | Rollback |
|---|---------|-------|-------------------|----------|
| 1 | Git sync unificado | BAIXO | Git push nao acontece | Reativar scripts antigos |
| 2 | Eliminar update_health.py | MEDIO | Portfolio fica desatualizado | Reativar cron no Pi5 |
| 3 | Eliminar backup_rpi.sh | BAIXO | Perde backup do Pi4 (coberto pelo v5) | Reativar cron |
| 4 | CIFS 15min | BAIXO | Mount demora 15min para remontar | Voltar para 5min |
| 5 | Log cleanup | BAIXO | Pode limpar logs uteis | Ajustar retencao |

> Nenhuma mudanca tem risco ALTO. Todas sao reversiveis em <5min.
