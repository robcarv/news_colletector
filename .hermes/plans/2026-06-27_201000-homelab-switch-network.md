# Plano: Otimizacao Rede Homelab com Switch SODOLA 2.5GbE

> **For Hermes:** Use subagent-driven-development para implementar este plano task-by-task.

**Goal:** Conectar todos os 3 Pis ao switch SODOLA via Ethernet, unificar subnet, eliminar Wi-Fi como rota primaria entre dispositivos do homelab.

**Architecture:** 3 Pis → Switch SODOLA 2.5GbE → TP-Link Mesh (internet). Subnet unica 192.168.68.0/24. Switch em modo bridge (sem DHCP proprio).

**Tech Stack:** ethtool, ip route, dhcpcd, /etc/hosts, iperf3

---

## Diagnostico Atual

| Host | Ethernet | Wi-Fi | Rota Default | Issue |
|------|----------|-------|-------------|-------|
| Pi501 (117) | eth0 **DOWN** | wlan0 (192.168.68.117) | 192.168.68.1 via wlan0 | Cabo nao conectado ao switch |
| Pi5 (108) | eth0 UP | wlan0 (192.168.68.108) | **192.168.0.1** (eth0) + 192.168.68.1 (wlan0) | Switch tem subnet propria (192.168.0.x)! |
| Pi4 (102) | eth0 **DOWN** | wlan0 (192.168.68.102) | 192.168.68.1 via wlan0 | Cabo nao conectado ao switch |

### Topologia Atual (problematica)

```
Internet → TP-Link Mesh (192.168.68.1)
              │
              ├── Wi-Fi ── Pi501 (192.168.68.117) ─┐
              ├── Wi-Fi ── Pi5   (192.168.68.108) ─┤  latency + inconsistente
              └── Wi-Fi ── Pi4   (192.168.68.102) ─┘
                             │
              Switch SODOLA (192.168.0.1 — SUBNET DIFERENTE!)
                             │
                             └── Pi5 eth0 (192.168.0.x) — conflito de rota
```

### Topologia Desejada

```
Internet → TP-Link Mesh (192.168.68.1)
              │
              └── Switch SODOLA (bridge mode, sem DHCP)
                    │
                    ├── Pi501 eth0 (192.168.68.117) — cabeado
                    ├── Pi5   eth0 (192.168.68.108) — cabeado
                    └── Pi4   eth0 (192.168.68.102) — cabeado
```

---

## Fase 1: Infraestrutura Fisica (Tasks 1-2)

### Task 1: Conectar cabos Ethernet dos 3 Pis ao switch SODOLA

**Objetivo:** Eliminar Wi-Fi como meio de comunicacao entre dispositivos.

**Steps:**

1. Conectar Pi501 eth0 → porta 1 do switch SODOLA
2. Conectar Pi4 eth0 → porta 2 do switch SODOLA
3. Pi5 eth0 ja esta conectado (porta 3)
4. Conectar switch SODOLA → TP-Link Mesh (porta LAN)

**Verificacao:**
```bash
# Em cada Pi, verificar link
ethtool eth0 | grep "Link detected"
# Esperado: Link detected: yes
```

---

### Task 2: Desabilitar DHCP do switch SODOLA (modo bridge)

**Objetivo:** Eliminar subnet 192.168.0.x — usar APENAS 192.168.68.x do TP-Link.

**Problema:** O switch SODOLA parece ter DHCP proprio servindo 192.168.0.0/24.

**Steps:**

1. Acessar interface web do switch (verificar IP: provavelmente 192.168.0.1)
2. Desabilitar servidor DHCP
3. Configurar como switch bridge/pass-through
4. Verificar que nao ha mais leases 192.168.0.x

**Verificacao:**
```bash
# No Pi5, apos reconectar eth0
ip addr show eth0 | grep inet
# Esperado: 192.168.68.x (do TP-Link), NAO 192.168.0.x
```

---

## Fase 2: Configuracao de Rede nos Pis (Tasks 3-5)

### Task 3: Forcar eth0 como rota primaria no Pi501

**Objetivo:** Pi501 usa Ethernet para tudo, Wi-Fi apenas fallback.

**Files:**
- Modify: `/etc/dhcpcd.conf` no Pi501

**Steps:**

1. Editar `/etc/dhcpcd.conf`:
```bash
interface eth0
metric 100
interface wlan0
metric 600
fallback wlan0
```

2. Reiniciar dhcpcd:
```bash
sudo systemctl restart dhcpcd
```

3. Verificar rota:
```bash
ip route show default
# Esperado: default via 192.168.68.1 dev eth0 metric 100
```

---

### Task 4: Corrigir Pi5 — remover rota 192.168.0.x

**Objetivo:** Pi5 usa APENAS 192.168.68.x, sem subnet dupla.

**Steps:**

1. Remover IP 192.168.0.x do eth0:
```bash
sudo ip addr flush dev eth0
sudo dhclient -r eth0
sudo dhclient eth0
```

2. Verificar que eth0 recebeu IP 192.168.68.x:
```bash
ip addr show eth0 | grep inet
```

3. Editar `/etc/dhcpcd.conf`:
```bash
interface eth0
metric 100
interface wlan0
metric 600
nofallback wlan0
```

4. Reiniciar dhcpcd e verificar:
```bash
sudo systemctl restart dhcpcd
ip route show default
# Esperado: default via 192.168.68.1 dev eth0 metric 100
```

---

### Task 5: Forcar eth0 como rota primaria no Pi4

**Objetivo:** Igual ao Pi501.

**Steps:** Identicos ao Task 3, no Pi4.

---

## Fase 3: Verificacao e Benchmark (Tasks 6-7)

### Task 6: Teste de latencia e throughput entre Pis

**Objetivo:** Medir melhoria apos migracao para Ethernet.

**Steps:**

1. Instalar iperf3 em todos os Pis:
```bash
sudo apt install -y iperf3
```

2. Antes (Wi-Fi) — medir baseline:
```bash
# Pi501 → Pi5 (Wi-Fi)
iperf3 -c 192.168.68.108 -t 10
```

3. Depois (Ethernet) — medir novo:
```bash
# Pi501 → Pi5 (Ethernet via switch)
iperf3 -c 192.168.68.108 -t 10
```

4. Latencia:
```bash
ping -c 10 192.168.68.108
```

**Resultado esperado:**
```
Metrica         Wi-Fi (antes)    Ethernet (depois)
Latencia        2-15ms           0.3-0.8ms
Throughput      30-80 Mbps       900+ Mbps
Jitter          Alta             Baixa
```

---

### Task 7: Verificar servicos do homelab

**Objetivo:** Garantir que nada quebrou com a mudanca de rede.

**Steps:**

1. Samba/CIFS mounts:
```bash
# No Pi5
mount | grep cifs
ls /mnt/radio_hdd/
```

2. Docker containers:
```bash
# No Pi501 e Pi5
docker ps --format "table {{.Names}}\t{{.Status}}"
```

3. NewsBot dry-run:
```bash
cd ~/Documents/vscode_projects/news_colletector
source venv/bin/activate
python main.py --dry-run
```

4. Grafana/Prometheus:
```bash
curl -s http://192.168.68.102:3030 | head -5
```

---

## Resumo de Impacto

| Metrica | Antes (Wi-Fi) | Depois (Ethernet) |
|---------|--------------|-------------------|
| Latencia Pi→Pi | 2-15ms | <1ms |
| Throughput | 30-80 Mbps | 900+ Mbps |
| Jitter | Alta | Baixa |
| Confiabilidade | Interferencia Wi-Fi | 100% cabeada |
| Subnets | 2 conflitantes | 1 unificada |
| Samba/SCP | Via Wi-Fi lento | Via switch rapido |
| AzuraCast Samba | Instavel | Estavel |

---

## Riscos

- Switch DHCP pode resetar apos power cycle — verificar persistencia
- Pi5 com IP duplo pode perder conectividade durante transicao
- CIFS mounts podem precisar de remount
- DNS local (/etc/hosts) ja usa IPs fixos — sem impacto
