#!/usr/bin/env python3
"""
collect_all_health.py — Coleta health de todos os 3 Pis via Glances API.
Roda no Pi5 via cron a cada 10 min.
Output: /home/robert/health_reports/health.json
Formato: { updated, nodes: { Pi4: {...}, Pi5: {...}, Pi501: {...} } }
"""
import json, subprocess, sys, time, os
from datetime import datetime, timezone

PIS = {
    "Pi4":   "192.168.68.102",
    "Pi5":   "192.168.68.108",
    "Pi501": "192.168.68.117",
}
GLANCES_PORT = 61208
TIMEOUT = 5


def fetch(endpoint: str, host: str) -> dict | None:
    """Fetch JSON from Glances API endpoint."""
    url = f"http://{host}:{GLANCES_PORT}/api/4/{endpoint}"
    try:
        r = subprocess.run(
            ["curl", "-s", "--connect-timeout", str(TIMEOUT), url],
            capture_output=True, text=True, timeout=TIMEOUT + 2
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def collect_pi(name: str, host: str) -> dict:
    """Collect all metrics for one Pi."""
    cpu_d = fetch("cpu", host)
    mem_d = fetch("mem", host)
    load_d = fetch("load", host)
    sensors = fetch("sensors", host)
    fs_d = fetch("fs", host)
    net_d = fetch("network", host)
    docker_d = fetch("containers", host)
    quick_d = fetch("quicklook", host)

    if cpu_d is None and mem_d is None:
        return {"hostname": f"raspberrypi{name.lower().replace('pi','')}", "offline": True}

    # CPU
    cpu_total = round(cpu_d.get("total", 0), 1) if cpu_d else 0
    cpu_user = round(cpu_d.get("user", 0), 1) if cpu_d else 0
    cpu_sys = round(cpu_d.get("system", 0), 1) if cpu_d else 0

    # RAM
    mem_total = mem_d.get("total", 0) if mem_d else 0
    mem_used = mem_d.get("used", 0) if mem_d else 0
    mem_pct = round(mem_d.get("percent", 0), 1) if mem_d else 0
    ram_total_gb = round(mem_total / (1024**3), 1) if mem_total else 0
    ram_used_gb = round(mem_used / (1024**3), 1) if mem_used else 0

    # Swap
    swap_total = mem_d.get("swap_total", 0) if mem_d else 0
    swap_used = mem_d.get("swap_used", 0) if mem_d else 0
    swap_free = swap_total - swap_used
    swap_pct = round((swap_used / swap_total) * 100, 1) if swap_total > 0 else 0

    # Temperature
    temp_c = 0
    if sensors:
        for s in sensors:
            if "temp" in s.get("type", "").lower() or "thermal" in s.get("label", "").lower():
                temp_c = s.get("value", 0)
                break
        if not temp_c and sensors:
            temp_c = sensors[0].get("value", 0)

    # Load
    load_1 = 0; load_5 = 0; load_15 = 0
    if load_d:
        load_1 = round(load_d.get("min1", 0), 2)
        load_5 = round(load_d.get("min5", 0), 2)
        load_15 = round(load_d.get("min15", 0), 2)
    cores = load_d.get("cpucore", 4) if load_d else 4

    # Disks
    disks = []
    if fs_d:
        for fs in fs_d:
            if fs.get("device_name", "").startswith("/dev/") and not fs.get("device_name", "").startswith("/dev/loop"):
                size_gb = round(fs.get("size", 0) / (1024**3), 1)
                used_gb = round(fs.get("used", 0) / (1024**3), 1)
                disks.append({
                    "device": fs.get("device_name", "?"),
                    "size_gb": size_gb,
                    "used_gb": used_gb,
                    "percent": round(fs.get("percent", 0), 1)
                })

    # Network
    network = {}
    if net_d:
        for iface in net_d[:3]:
            name = iface.get("interface_name", "?")
            network[name] = {
                "recv_mb": round(iface.get("bytes_recv", 0) / (1024**2)),
                "sent_mb": round(iface.get("bytes_sent", 0) / (1024**2))
            }

    # Docker containers
    containers = []
    if docker_d and isinstance(docker_d, list):
        for c in docker_d[:15]:
            containers.append({
                "name": c.get("name", "?"),
                "status": c.get("status", "?")
            })

    # Score
    score = 100
    if quick_d:
        cpu_pct = quick_d.get("cpu", 0)
        ram_pct_val = quick_d.get("ram", 0)
        score = 100 - int((cpu_pct + ram_pct_val) / 2)

    return {
        "hostname": f"raspberrypi{name.lower().replace('pi','')}",
        "cpu": {"total": cpu_total, "user": cpu_user, "system": cpu_sys},
        "ram": {"total_gb": ram_total_gb, "used_gb": ram_used_gb, "percent": mem_pct},
        "swap": {"total_mb": round(swap_total / (1024**2)), "used_mb": round(swap_used / (1024**2)),
                 "free_mb": round(swap_free / (1024**2)), "percent": swap_pct},
        "temperature_c": temp_c,
        "load": {"1min": load_1, "5min": load_5, "15min": load_15, "cores": cores},
        "disks": disks,
        "network": network,
        "containers": containers,
        "score": score,
        "services": f"{len(containers)} containers"
    }


def main():
    output_path = "/home/robert/health_reports/health.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    now = datetime.now(timezone.utc).astimezone().isoformat()

    nodes = {}
    for name, host in PIS.items():
        try:
            nodes[name] = collect_pi(name, host)
            online = "offline" if nodes[name].get("offline") else f'score={nodes[name].get("score",0)}'
            print(f"  {name} ({host}): {online}")
        except Exception as e:
            print(f"  {name} ({host}): ERROR — {e}")
            nodes[name] = {"hostname": f"raspberrypi{name.lower().replace('pi','')}", "offline": True}

    result = {"updated": now, "nodes": nodes}

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"  JSON ok -> {output_path}")


if __name__ == "__main__":
    main()
