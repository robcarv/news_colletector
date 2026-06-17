# Pi4 (192.168.68.102) — Cron Jobs

**Hostname:** raspberrypi4
**Uptime:** 6d 23h
**RAM:** 7.6GB (878MB used)
**Disk:** 116GB (21GB used - 19%)
**Docker:** Provavelmente Pi-hole, NPM, Wallos, outros

---

## Cron Tabela

| # | Schedule | Comando | Descricao |
|---|----------|---------|-----------|
| 1 | @reboot | docker run binfmt --install x86_64 | Habilita emulacao x86_64 no boot |
| 2 | 0 3 * * 1,3,5 | backup_rpi.sh | Backup deste Pi (Seg/Qua/Sex 03:00) |

### Notas

- **Pi-hole** — usa systemd timer interno para gravity update
- **Pi.Alert** — scan periodico de rede (autogerenciado)
- **NPM (Nginx Proxy Manager)** — sem cron, gerenciado via web UI
- **Glances** — se ativo, exporta metricas continuamente

O cron `backup_rpi.sh` esta comentado com `#` no inicio da linha original,
mas ha outro ativo `0 3 * * 1,3,5` com mesmo caminho — possivel duplicidade.
