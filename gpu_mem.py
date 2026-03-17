#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from typing import Any


def mib_from_bytes(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / 1024 / 1024, 2)


def decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def safe_read_process_name(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmd = f.read().replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
            if cmd:
                return cmd
    except Exception:
        pass

    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="replace") as f:
            name = f.read().strip()
            if name:
                return name
    except Exception:
        pass

    return "<unknown>"


def collect_with_nvml() -> dict[str, Any]:
    import pynvml  # package: nvidia-ml-py

    nvml_value_not_available = getattr(pynvml, "NVML_VALUE_NOT_AVAILABLE", None)

    def get_process_name(pid: int) -> str:
        fn = getattr(pynvml, "nvmlSystemGetProcessName", None)
        if fn:
            try:
                return decode(fn(pid))
            except Exception:
                pass
        return safe_read_process_name(pid)

    def get_running_processes(handle) -> list[dict[str, Any]]:
        families = [
            ("compute", [
                "nvmlDeviceGetComputeRunningProcesses_v3",
                "nvmlDeviceGetComputeRunningProcesses_v2",
                "nvmlDeviceGetComputeRunningProcesses",
            ]),
            ("graphics", [
                "nvmlDeviceGetGraphicsRunningProcesses_v3",
                "nvmlDeviceGetGraphicsRunningProcesses_v2",
                "nvmlDeviceGetGraphicsRunningProcesses",
            ]),
            ("mps", [
                "nvmlDeviceGetMPSComputeRunningProcesses_v3",
                "nvmlDeviceGetMPSComputeRunningProcesses_v2",
                "nvmlDeviceGetMPSComputeRunningProcesses",
            ]),
        ]

        processes: dict[int, dict[str, Any]] = {}

        for proc_type, candidate_names in families:
            getter = None
            for name in candidate_names:
                getter = getattr(pynvml, name, None)
                if getter:
                    break

            if not getter:
                continue

            try:
                items = getter(handle)
            except Exception:
                continue

            for item in items or []:
                pid = int(getattr(item, "pid", -1))
                if pid < 0:
                    continue

                raw_used = getattr(item, "usedGpuMemory", None)
                if raw_used == nvml_value_not_available:
                    used_bytes = None
                else:
                    used_bytes = int(raw_used) if raw_used is not None else None

                entry = processes.setdefault(
                    pid,
                    {
                        "pid": pid,
                        "name": get_process_name(pid),
                        "gpu_memory_used_bytes": 0,
                        "gpu_memory_used_mib": 0.0,
                        "types": [],
                    },
                )

                if used_bytes is None:
                    entry["gpu_memory_used_bytes"] = None
                    entry["gpu_memory_used_mib"] = None
                elif entry["gpu_memory_used_bytes"] is not None:
                    entry["gpu_memory_used_bytes"] += used_bytes
                    entry["gpu_memory_used_mib"] = mib_from_bytes(entry["gpu_memory_used_bytes"])

                if proc_type not in entry["types"]:
                    entry["types"].append(proc_type)

        return sorted(
            processes.values(),
            key=lambda x: (
                x["gpu_memory_used_bytes"] is None,
                -(x["gpu_memory_used_bytes"] or 0),
                x["pid"],
            ),
        )

    pynvml.nvmlInit()
    try:
        driver_version = decode(pynvml.nvmlSystemGetDriverVersion())
        gpu_count = pynvml.nvmlDeviceGetCount()

        gpus: list[dict[str, Any]] = []
        total_bytes = 0
        used_bytes = 0
        free_bytes = 0

        for index in range(gpu_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)

            gpu_total = int(mem.total)
            gpu_used = int(mem.used)
            gpu_free = int(mem.free)

            total_bytes += gpu_total
            used_bytes += gpu_used
            free_bytes += gpu_free

            gpus.append(
                {
                    "index": index,
                    "name": decode(pynvml.nvmlDeviceGetName(handle)),
                    "uuid": decode(pynvml.nvmlDeviceGetUUID(handle)),
                    "memory_total_bytes": gpu_total,
                    "memory_total_mib": mib_from_bytes(gpu_total),
                    "memory_used_bytes": gpu_used,
                    "memory_used_mib": mib_from_bytes(gpu_used),
                    "memory_free_bytes": gpu_free,
                    "memory_free_mib": mib_from_bytes(gpu_free),
                    "processes": get_running_processes(handle),
                }
            )

        return {
            "backend": "nvml",
            "driver_version": driver_version,
            "gpu_count": gpu_count,
            "summary": {
                "memory_total_bytes": total_bytes,
                "memory_total_mib": mib_from_bytes(total_bytes),
                "memory_used_bytes": used_bytes,
                "memory_used_mib": mib_from_bytes(used_bytes),
                "memory_free_bytes": free_bytes,
                "memory_free_mib": mib_from_bytes(free_bytes),
            },
            "gpus": gpus,
        }
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass


def run_cmd(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)


def collect_with_nvidia_smi() -> dict[str, Any]:
    gpu_csv = run_cmd([
        "nvidia-smi",
        "--query-gpu=index,name,uuid,memory.total,memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ])

    gpu_rows: list[dict[str, Any]] = []
    uuid_to_gpu: dict[str, dict[str, Any]] = {}

    total_mib = 0
    used_mib = 0
    free_mib = 0

    for line in gpu_csv.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue

        index = int(parts[0])
        name = parts[1]
        uuid = parts[2]
        mem_total_mib = float(parts[3])
        mem_used_mib = float(parts[4])
        mem_free_mib = float(parts[5])

        total_mib += mem_total_mib
        used_mib += mem_used_mib
        free_mib += mem_free_mib

        row = {
            "index": index,
            "name": name,
            "uuid": uuid,
            "memory_total_mib": mem_total_mib,
            "memory_used_mib": mem_used_mib,
            "memory_free_mib": mem_free_mib,
            "processes": [],
        }
        gpu_rows.append(row)
        uuid_to_gpu[uuid] = row

    try:
        proc_csv = run_cmd([
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ])

        for line in proc_csv.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue

            gpu_uuid = parts[0]
            pid = int(parts[1])
            process_name = parts[2] or safe_read_process_name(pid)

            try:
                used_proc_mib = float(parts[3])
            except ValueError:
                used_proc_mib = None

            gpu = uuid_to_gpu.get(gpu_uuid)
            if gpu is None:
                continue

            gpu["processes"].append(
                {
                    "pid": pid,
                    "name": process_name,
                    "gpu_memory_used_mib": used_proc_mib,
                    "types": ["compute"],
                }
            )

        for gpu in gpu_rows:
            gpu["processes"].sort(
                key=lambda x: (
                    x["gpu_memory_used_mib"] is None,
                    -(x["gpu_memory_used_mib"] or 0),
                    x["pid"],
                )
            )
    except Exception:
        pass

    return {
        "backend": "nvidia-smi",
        "gpu_count": len(gpu_rows),
        "summary": {
            "memory_total_mib": total_mib,
            "memory_used_mib": used_mib,
            "memory_free_mib": free_mib,
        },
        "gpus": gpu_rows,
    }


def print_human(data: dict[str, Any]) -> None:
    print(f"backend: {data['backend']}")
    if "driver_version" in data:
        print(f"driver:  {data['driver_version']}")
    print(f"gpus:    {data['gpu_count']}")

    summary = data["summary"]
    print()
    print("summary:")
    print(f"  total: {summary['memory_total_mib']} MiB")
    print(f"  used:  {summary['memory_used_mib']} MiB")
    print(f"  free:  {summary['memory_free_mib']} MiB")

    for gpu in data["gpus"]:
        print()
        print(f"GPU {gpu['index']}: {gpu['name']}")
        print(f"  uuid:  {gpu['uuid']}")
        print(f"  total: {gpu['memory_total_mib']} MiB")
        print(f"  used:  {gpu['memory_used_mib']} MiB")
        print(f"  free:  {gpu['memory_free_mib']} MiB")

        processes = gpu.get("processes", [])
        if not processes:
            print("  processes: none / not exposed by driver")
            continue

        print("  processes:")
        for p in processes:
            used = p.get("gpu_memory_used_mib")
            used_str = f"{used} MiB" if used is not None else "N/A"
            types = ",".join(p.get("types", [])) or "unknown"
            print(f"    PID {p['pid']:<8} {used_str:<12} {types:<10} {p['name']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print JSON instead of human-readable output")
    args = parser.parse_args()

    try:
        data = collect_with_nvml()
    except Exception as nvml_error:
        try:
            data = collect_with_nvidia_smi()
            data["warning"] = f"NVML path failed, fallback to nvidia-smi: {nvml_error}"
        except Exception as smi_error:
            print("Could not read GPU memory via NVML or nvidia-smi.", file=sys.stderr)
            print(f"NVML error: {nvml_error}", file=sys.stderr)
            print(f"nvidia-smi error: {smi_error}", file=sys.stderr)
            return 1

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_human(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())