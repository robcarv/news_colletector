# Pi5 (192.168.68.108) — Cron Jobs

**Hostname:** raspberrypi5
**Uptime:** 2d 21h
**RAM:** 7.9GB (1.9GB used)
**Disk:** 117GB (73GB used - 66%)
**Docker:** 7 containers rodando

---

## Cron Tabela

| # | Schedule | Comando | Descricao |
|---|----------|---------|-----------|
| 1 | @reboot | docker run binfmt --install x86_64 | Habilita emulacao x86_64 no boot |
| 2 | 0 */6 * * * | torrent_health_cron.sh | Health check do qBittorrent (a cada 6h) |
| 3 | 0 3 * * * | torrent_antivirus.sh | Scan ClamAV nos downloads as 03:00 |
| 4 | */5 * * * * | guardian.sh | Health guardian do Pi5 (load, RAM, swap - a cada 5min) |
| 5 | */5 * * * * | mount_cifs.sh | Verifica/monta CIFS do TrueNAS (a cada 5min) |
| 6 | 30 3 * * 1,3,5 | backup_rpi_v4.sh | Backup completo dos 3 Pis (Seg/Qua/Sex 03:30) |
| 7 | */30 * * * * | update_health.py | Gera health.json com metricas de todos os Pis (a cada 30min) |

### Scripts detalhados

**torrent_health_cron.sh** — Executa `torrent_health.py` dentro do container qBittorrent.
Verifica integridade dos torrents (trackers, seeds, peers).

**torrent_antivirus.sh** — Scan ClamAV nos downloads completos em `/mnt/truenas_media/downloads/complete/`. Log em `/home/robert/scripts/clamav_scan.log`. Alerta se encontrar virus.

**guardian.sh** — Monitora LOAD (>8.0), RAM (>85%), SWAP (>50%). Toma acao corretiva se thresholds excedidos. Log a cada 30min.

**mount_cifs.sh** — Monta CIFS `//192.168.68.124/Media` em `/mnt/truenas_media`. Usa credentials em `/etc/smbcredentials/truenas`. So executa se nao estiver montado. Tolerante a falhas de rede.

**backup_rpi_v4.sh** — Pipeline completo: (1) ClamAV scan, (2) backup configs de todos os Pis, (3) rsync para TrueNAS, (4) rclone para OneDrive, (5) health report, (6) git push para GitHub, (7) limpeza de backups antigos.

**update_health.py** — Scan profundo: Docker containers, cron jobs, systemd services, metricas (RAM/Disk/Temp/Load/Uptime), TrueNAS CIFS. Gera health.json e faz push para GitHub Pages (robcarv.github.io).

### Docker Compose Stacks

azuracast (2 containers), duckdns, glances, iproyal, qbittorrent
