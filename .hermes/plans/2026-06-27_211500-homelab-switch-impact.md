# Plano: Estudo de Impacto — Switch SODOLA 2.5GbE no Homelab

> **For Hermes:** Use subagent-driven-development para implementar este plano task-by-task.

**Goal:** Documento completo de analise tecnica do impacto da migracao Wi-Fi → Ethernet no homelab, com metricas comparativas, graficos, e conclusoes de alto nivel.

**Architecture:** Coletar dados do Prometheus (30d) + testes manuais → compilar em markdown com tabelas ASCII e diagramas → publicar no homelab-docs.

**Tech Stack:** Prometheus, Grafana, iperf3, ping, Python, Markdown

---

## Contexto

Antes (Wi-Fi): 3 Pis conectados via Wi-Fi 5GHz ao TP-Link Mesh.  
Depois (Ethernet): 3 Pis conectados via cabo ao switch SODOLA 2.5GbE, TP-Link como uplink.

| Pi | IP Wi-Fi (antes) | IP eth0 (depois) |
|----|-----------------|-------------------|
| Pi501 | 192.168.68.117 | 192.168.68.119 |
| Pi5 | 192.168.68.108 | 192.168.68.122 |
| Pi4 | 192.168.68.102 | 192.168.68.123 |
| TrueNAS | 192.168.68.124 | 192.168.68.124 |

---

## Task 1: Coletar metricas de latencia (manual + Prometheus)

**Objetivo:** Tabela comparativa completa de latencia Pi→Pi, Pi→TrueNAS, Pi→Internet.

**Files:**
- Create: `/tmp/homelab-docs/homelab/switch-impact-analysis.md`

**Metricas a coletar:**

```
Latencia Interna (ping 20 pacotes):
  Pi501 → Pi5:    eth0 vs wlan0
  Pi501 → Pi4:    eth0 vs wlan0
  Pi501 → TrueNAS: eth0 vs wlan0
  Pi5 → Pi4:      eth0 vs wlan0
  Pi5 → Pi501:    eth0 vs wlan0
  Pi4 → Pi5:      eth0 vs wlan0

Latencia Internet:
  Pi501 → 8.8.8.8: eth0 vs wlan0
  Pi5 → 8.8.8.8:   eth0 vs wlan0
  Pi4 → 8.8.8.8:   eth0 vs wlan0

Perda de pacotes: % loss em cada rota
Jitter: mdev em cada rota
```

**Comando:**
```bash
# Exemplo — Pi501 → Pi5 via eth0
ping -c 20 -I eth0 192.168.68.122

# Pi501 → Pi5 via wlan0 (IP antigo)
ping -c 20 -I wlan0 192.168.68.108
```

---

## Task 2: Teste de throughput (iperf3)

**Objetivo:** Medir banda maxima entre Pis antes e depois.

**Comando:**
```bash
# No Pi5 (servidor)
iperf3 -s

# No Pi501 (cliente) — Ethernet
iperf3 -c 192.168.68.122 -t 15 -P 4

# No Pi501 (cliente) — Wi-Fi (usando IP antigo)
iperf3 -c 192.168.68.108 -t 15 -P 4
```

**Metricas esperadas:**

| Par | Wi-Fi | Ethernet | Ganho |
|-----|-------|----------|-------|
| Pi501→Pi5 | ~80 Mbps | ~940 Mbps | 12x |
| Pi501→Pi4 | ~60 Mbps | ~940 Mbps | 16x |

---

## Task 3: Impacto em servicos (tempo de execucao)

**Objetivo:** Medir se servicos ficaram mais rapidos com Ethernet.

**Metricas a coletar:**

1. **NewsBot dry-run** (41 feeds RSS):
```bash
time python main.py --dry-run
```

2. **SCP transferencia** (arquivo 1MB):
```bash
dd if=/dev/zero of=/tmp/test.bin bs=1M count=1
time scp /tmp/test.bin robert@pi5:/tmp/
```

3. **Samba leitura** (no Pi5):
```bash
time cp /mnt/radio_hdd/news_jingles/G1__Brasil_.mp3 /tmp/
```

---

## Task 4: Graficos do Prometheus (se dados disponiveis)

**Objetivo:** Extrair series temporais para mostrar tendencia.

**Queries:**
```promql
# Latencia media interna ao longo do tempo
avg(network_latency_ms{type="internal"})

# Latencia por interface (se houver dados antigos)
avg by(iface) (network_latency_ms{type="internal"})
```

**Exportar como:** tabela CSV → grafico ASCII no documento.

---

## Task 5: Compilar documento final

**Objetivo:** Escrever o markdown completo com todas as analises.

**Estrutura do documento:**

```markdown
# Homelab Network Upgrade — Impact Analysis

## 1. Resumo Executivo (High Level)
- O que mudou
- Resultado principal (1 paragrafo)

## 2. Topologia
- Diagrama ASCII antes
- Diagrama ASCII depois

## 3. Metricas de Latencia
- Tabela comparativa completa
- Grafico ASCII de barras

## 4. Throughput
- Tabela iperf3 antes/depois

## 5. Impacto em Servicos
- NewsBot dry-run time
- SCP/Samba speed

## 6. Estabilidade
- Packet loss antes/depois
- Jitter antes/depois

## 7. Conclusoes Tecnicas
- Por que melhorou
- O que ainda pode melhorar
- Recomendacoes
```

**Files:**
- Create: `homelab/switch-impact-analysis.md`
- Modify: `README.md` (adicionar link)

---

## Task 6: Push para homelab-docs

```bash
cd /tmp/homelab-docs
git add homelab/switch-impact-analysis.md README.md
git commit -m "docs: switch SODOLA impact analysis — WiFi vs Ethernet metrics"
git push origin main
```

---

## Resumo de Esforco

| Task | Tempo estimado |
|------|---------------|
| Coletar latencia | 5 min |
| Teste iperf3 | 5 min |
| Impacto servicos | 5 min |
| Graficos Prometheus | 5 min |
| Compilar documento | 10 min |
| Push | 2 min |
| **Total** | **~32 min** |
