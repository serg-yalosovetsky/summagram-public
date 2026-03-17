"""
system_stats.py

Fetches container CPU/RAM usage via docker API if available and matches it with
GPU VRAM usage via nvidia-smi.
"""

import re
import os
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Optional

from loguru import logger


@dataclass
class ContainerMetrics:
    name: str
    cpu_perc: float
    mem_used_b: int
    mem_limit_b: int
    mem_perc: float
    vram_used_mib: int
    gpu_proc_count: int


def _run_cmd(cmd: List[str], timeout: int = 15, quiet: bool = False) -> str:
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        if p.returncode != 0:
            if not quiet:
                logger.warning(
                    f"Command failed: {' '.join(cmd)}\nSTDERR:\n{p.stderr.strip()}"
                )
            return ""
        return p.stdout.strip()
    except Exception as e:
        if not quiet:
            logger.warning(f"Exception running {' '.join(cmd)}: {e}")
        return ""


def _parse_size_to_bytes(s: str) -> int:
    s = s.strip()
    if not s:
        return 0
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*([A-Za-z]+)?\s*$", s)
    if not m:
        return 0

    val = float(m.group(1))
    unit = (m.group(2) or "B").strip().upper()

    bin_units = {"B": 1, "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3, "TIB": 1024**4}
    dec_units = {"B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}

    if unit in bin_units:
        return int(val * bin_units[unit])
    if unit in dec_units:
        return int(val * dec_units[unit])

    # Rare variants
    if unit in {"K", "KB"}:
        return int(val * 1000)
    if unit in {"M", "MB"}:
        return int(val * 1000**2)
    if unit in {"G", "GB"}:
        return int(val * 1000**3)

    return 0


def _nvidia_procs(kind: str) -> List[tuple[int, int]]:
    """Returns list of (pid, used_mib)"""
    field = "compute-apps" if kind == "compute" else "graphics-apps"
    cmd = [
        "nvidia-smi",
        f"--query-{field}=pid,used_memory",
        "--format=csv,noheader,nounits",
    ]
    out = _run_cmd(cmd, timeout=10, quiet=(kind == "graphics"))
    res = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            try:
                mem_str = parts[1]
                mem_val = 0 if mem_str == "[N/A]" else int(float(mem_str))
                res.append((int(parts[0]), mem_val))
            except ValueError:
                pass
    return res


def _container_id_from_cgroup(pid: int) -> Optional[str]:
    """Tries to extract 64-hex container id from /proc/<pid>/cgroup."""
    # Since we might be inside a docker container, we need to map via mounted host /proc if possible.
    # Note: If /host/proc is not mounted, we can only read /proc of our own container.
    path = f"/host/proc/{pid}/cgroup"
    if not os.path.exists(path):
        # Fallback to local proc (if host network/pid namespaces are shared, this would work)
        path = f"/proc/{pid}/cgroup"
        if not os.path.exists(path):
            return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except Exception:
        return None

    patterns = [
        r"/docker/([0-9a-f]{64})",
        r"docker-([0-9a-f]{64})\.scope",
        r"/containerd/([0-9a-f]{64})",
        r"cri-containerd-([0-9a-f]{64})\.scope",
    ]
    for pat in patterns:
        m = re.search(pat, txt)
        if m:
            return m.group(1)

    m = re.search(r"([0-9a-f]{64})", txt)
    return m.group(1) if m else None


def get_container_metrics(prefix: str = "summagram_") -> List[ContainerMetrics]:
    """
    Combines 'docker stats' with container VRAM usage mapped from host PID to container.
    Only works if Docker CLI is available inside the container and /var/run/docker.sock is mounted.
    """
    import shutil

    if not shutil.which("docker"):
        logger.debug(
            "docker CLI not found in backend container. Returning empty metrics."
        )
        return []

    if not os.path.exists("/var/run/docker.sock"):
        logger.debug(
            "/var/run/docker.sock not found. Returning empty metrics without warning logs."
        )
        return []

    # Get id to name mappings
    ps_out = _run_cmd(["docker", "ps", "--no-trunc", "--format", "{{.ID}}\t{{.Names}}"])
    id_to_name: Dict[str, str] = {}
    for line in ps_out.splitlines():
        if line.strip():
            try:
                cid, name = line.split("\t", 1)
                id_to_name[cid.strip()] = name.strip()
            except ValueError:
                pass

    # Get gpu procs (if nvidia-smi is available)
    vram_by_name: Dict[str, int] = {}
    gpu_count_by_name: Dict[str, int] = {}

    if shutil.which("nvidia-smi"):
        try:
            raw = _nvidia_procs("compute") + _nvidia_procs("graphics")
            for pid, used_mib in raw:
                cid = _container_id_from_cgroup(pid)
                cname = id_to_name.get(cid) if cid else None
                if cname:
                    vram_by_name[cname] = vram_by_name.get(cname, 0) + used_mib
                    gpu_count_by_name[cname] = gpu_count_by_name.get(cname, 0) + 1
        except Exception as e:
            logger.warning(f"Failed to collect gpu procs: {e}")

    # Get docker stats
    fmt = "{{.Container}}\t{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
    stats_out = _run_cmd(
        ["docker", "stats", "--no-stream", "--no-trunc", "--format", fmt], timeout=20
    )

    aggs: List[ContainerMetrics] = []
    for line in stats_out.splitlines():
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        cid, name, cpu_s, mem_usage_s, memp_s = parts
        name = name.strip()

        if prefix and not name.startswith(prefix):
            continue

        cpu = float(cpu_s.strip().replace("%", "") or 0.0)

        # "12.34MiB / 15.62GiB"
        if " / " in mem_usage_s:
            used_s, limit_s = mem_usage_s.split(" / ", 1)
        else:
            used_s, limit_s = mem_usage_s, "0B"
        used_b = _parse_size_to_bytes(used_s)
        limit_b = _parse_size_to_bytes(limit_s)

        memp = float(memp_s.strip().replace("%", "") or 0.0)

        aggs.append(
            ContainerMetrics(
                name=name,
                cpu_perc=cpu,
                mem_used_b=used_b,
                mem_limit_b=limit_b,
                mem_perc=memp,
                vram_used_mib=vram_by_name.get(name, 0),
                gpu_proc_count=gpu_count_by_name.get(name, 0),
            )
        )

    # sort by (vram, mem, cpu) descending
    aggs.sort(key=lambda x: (x.vram_used_mib, x.mem_used_b, x.cpu_perc), reverse=True)
    return aggs
