# TrueNAS (192.168.68.124) — Cron Jobs

**Hostname:** truenas
**Uptime:** 6d 23h
**ZFS Pools:** boot-pool (928G), nvme1 (10.9TB - 1.83TB used, 16% cap)
**SSH:** Funcionando (robert user)

---

## Cron Tabela

Nao ha crontab de usuario no TrueNAS. TrueNAS Scale gerencia tarefas agendadas
internamente via middleware e systemd timers.

### Systemd Timers padrao do TrueNAS

| Timer | Schedule | Descricao |
|-------|----------|-----------|
| sysstat-collect | a cada 10min | Coleta de metricas do sistema |
| certbot | 2x ao dia | Renovacao de certificados SSL |
| sysstat-summary | diario 00:07 | Sumario diario de metricas |
| sysstat-rotate | diario 00:00 | Rotacao de logs sysstat |
| logrotate | diario 00:30 | Rotacao de logs do sistema |
| man-db | diario ~06:00 | Atualizacao do banco de man pages |
| apt-daily | diario | Atualizacao de pacotes APT |
| apt-daily-upgrade | diario | Upgrade de pacotes APT |
| dpkg-db-backup | diario 00:00 | Backup do banco de dados dpkg |
| fstrim | semanal | TRIM dos SSDs |
| e2scrub_all | semanal | Scrub de filesystems ext4 |

### Tarefas Internas do TrueNAS (não expostas via SSH)

Tasks que sao gerenciadas pela UI do TrueNAS Scale e **nao aparecem em crontab**:

- **Cloud Sync Tasks** — Backup para nuvem (configurado na UI)
- **Periodic Snapshot Tasks** — Snapshots ZFS automaticos
- **Rsync Tasks** — Sincronizacao entre pools/servidores
- **SMART Tests** — Testes periodicos de saude dos discos
- **ZFS Scrub** — Verificacao de integridade do pool

> **Nota:** Para inspecionar estas tasks, seria necessario acessar a API REST
> do TrueNAS em `https://192.168.68.124/api/v2.0/` com token de autenticacao.
