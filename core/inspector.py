from __future__ import annotations

import platform
import re
import subprocess
from functools import lru_cache
from itertools import islice
from typing import Iterable, List, Optional

from core.models import OccupancyType, PortRecord
from core.privilege import get_privilege_info


def inspect_ports(ports: Optional[Iterable[int]] = None) -> List[PortRecord]:
    requested = set(ports or [])
    system = platform.system()
    if system == "Windows":
        records = _inspect_windows(requested or None)
    else:
        records = _inspect_linux(requested or None)

    _attach_process_names(records)

    for record in records:
        record.occupancy_type = classify_record(record)
        record.advice = build_advice(record)
    return records


def diagnose_http_sys(port: Optional[int] = None) -> str:
    if platform.system() != "Windows":
        return "当前平台不支持 HTTP.sys 诊断。"

    privilege = get_privilege_info()
    if not privilege.is_elevated:
        return "需要管理员权限才能执行 netsh http show servicestate。"

    command = ["netsh", "http", "show", "servicestate"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    if port is None:
        return output.strip() or "未获取到 HTTP.sys 诊断结果。"

    matched_lines = [line for line in output.splitlines() if f":{port}/" in line or f":{port} " in line or f":{port}" in line]
    if matched_lines:
        return "\n".join(matched_lines)
    return output.strip() or "未获取到 HTTP.sys 诊断结果。"


def classify_record(record: PortRecord) -> OccupancyType:
    state = record.state.upper()
    system = platform.system()
    if state == "TIME_WAIT":
        return OccupancyType.TIME_WAIT
    if state == "CLOSE_WAIT":
        return OccupancyType.CLOSE_WAIT
    if system == "Windows" and record.pid == 4:
        return OccupancyType.HTTP_SYS
    if record.pid:
        return OccupancyType.USER_PROCESS
    if system != "Windows":
        privilege = get_privilege_info()
        if not privilege.is_elevated:
            return OccupancyType.PERMISSION_LIMITED
    return OccupancyType.UNKNOWN


def build_advice(record: PortRecord) -> str:
    kind = record.occupancy_type
    if kind == OccupancyType.USER_PROCESS:
        return "可终止对应进程释放端口；普通用户只能处理自己的进程。"
    if kind == OccupancyType.HTTP_SYS:
        return "该端口由 PID 4(System)/HTTP.sys 持有，不能直接结束，请用 netsh 定位具体服务。"
    if kind == OccupancyType.TIME_WAIT:
        return "这是 TCP 正常回收状态，不能强制删除。可等待自动过期，或以管理员权限调整 TIME_WAIT 参数。"
    if kind == OccupancyType.CLOSE_WAIT:
        return "这通常是应用未正确 close() 导致的泄漏，需结束对应进程或修复应用。"
    if kind == OccupancyType.PERMISSION_LIMITED:
        return "当前权限不足，可能无法看到真实 PID。请尝试使用管理员/root 权限重新查询。"
    return "未能准确分类，请结合原始输出继续诊断。"


def _inspect_windows(requested_ports: Optional[set[int]] = None) -> List[PortRecord]:
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    records: List[PortRecord] = []
    for line in result.stdout.splitlines():
        parsed = _parse_windows_netstat_line(line)
        if parsed and (not requested_ports or parsed.local_port in requested_ports):
            records.append(parsed)
    return records


def _inspect_linux(requested_ports: Optional[set[int]] = None) -> List[PortRecord]:
    result = subprocess.run(
        ["ss", "-tulnp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    records: List[PortRecord] = []
    for line in result.stdout.splitlines():
        parsed = _parse_linux_ss_line(line)
        if parsed and (not requested_ports or parsed.local_port in requested_ports):
            records.append(parsed)
    return records


def _parse_windows_netstat_line(line: str) -> Optional[PortRecord]:
    line = line.strip()
    if not line or (not line.startswith("TCP") and not line.startswith("UDP")):
        return None

    parts = re.split(r"\s+", line)
    protocol = parts[0]
    if protocol == "TCP" and len(parts) >= 5:
        local, remote, state, pid_str = parts[1], parts[2], parts[3], parts[4]
    elif protocol == "UDP" and len(parts) >= 4:
        local, remote, state, pid_str = parts[1], parts[2], "", parts[3]
    else:
        return None

    local_host, local_port = _split_endpoint(local)
    remote_host, remote_port = _split_endpoint(remote)
    pid = int(pid_str) if pid_str.isdigit() else None
    return PortRecord(
        protocol=protocol,
        local_address=local_host,
        local_port=local_port,
        remote_address=remote_host,
        remote_port=remote_port,
        state=state or "BOUND",
        pid=pid,
        process_name="",
        command="",
        raw_line=line,
    )


def _parse_linux_ss_line(line: str) -> Optional[PortRecord]:
    line = line.strip()
    if not line or line.startswith("Netid") or line.startswith("State"):
        return None

    parts = re.split(r"\s+", line, maxsplit=6)
    if len(parts) < 5:
        return None

    if parts[0] in {"tcp", "udp"}:
        protocol = parts[0].upper()
        state = parts[1]
        local = parts[4] if len(parts) > 4 else ""
        remote = parts[5] if len(parts) > 5 else "*:*"
        process_info = parts[6] if len(parts) > 6 else ""
    else:
        protocol = parts[0].upper()
        state = parts[1]
        local = parts[3] if len(parts) > 3 else ""
        remote = parts[4] if len(parts) > 4 else "*:*"
        process_info = parts[5] if len(parts) > 5 else ""

    local_host, local_port = _split_endpoint(local)
    remote_host, remote_port = _split_endpoint(remote)
    pid, process_name = _extract_linux_process(process_info)
    return PortRecord(
        protocol=protocol,
        local_address=local_host,
        local_port=local_port,
        remote_address=remote_host,
        remote_port=remote_port,
        state=state,
        pid=pid,
        process_name=process_name,
        command=process_info,
        raw_line=line,
    )


def _split_endpoint(endpoint: str) -> tuple[str, Optional[int]]:
    endpoint = endpoint.strip("[]")
    if endpoint in {"*", "*:*"}:
        return "*", None
    if endpoint.count(":") == 0:
        return endpoint, None

    host, _, port_str = endpoint.rpartition(":")
    if port_str == "*" or not port_str:
        return host or "*", None
    try:
        return host or "*", int(port_str)
    except ValueError:
        return endpoint, None


def _extract_linux_process(process_info: str) -> tuple[Optional[int], str]:
    if not process_info:
        return None, ""
    pid_match = re.search(r"pid=(\d+)", process_info)
    name_match = re.search(r'"([^"]+)"', process_info)
    pid = int(pid_match.group(1)) if pid_match else None
    process_name = name_match.group(1) if name_match else ""
    return pid, process_name


def _attach_process_names(records: List[PortRecord]) -> None:
    if not records or platform.system() != "Windows":
        return

    pid_to_name = _get_windows_process_names({record.pid for record in records if record.pid})
    for record in records:
        if record.pid:
            record.process_name = pid_to_name.get(record.pid, "")
            record.command = record.process_name


def _get_windows_process_names(pids: set[int]) -> dict[int, str]:
    if not pids:
        return {}

    names: dict[int, str] = {}
    missing = set(pids)

    for chunk in _chunked(sorted(pids), 50):
        filters = []
        for pid in chunk:
            filters.extend(["/FI", f"PID eq {pid}"])

        result = subprocess.run(
            ["tasklist", *filters, "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        for line in result.stdout.splitlines():
            csv_line = line.strip()
            if not csv_line or csv_line.startswith("INFO:"):
                continue
            match = re.match(r'"([^"]+)","(\d+)"', csv_line)
            if not match:
                continue
            name = match.group(1)
            pid = int(match.group(2))
            names[pid] = name
            missing.discard(pid)

    for pid in list(missing):
        fallback_name = _get_windows_process_name(pid)
        if fallback_name:
            names[pid] = fallback_name

    return names


def _chunked(values: List[int], size: int):
    iterator = iter(values)
    while True:
        chunk = list(islice(iterator, size))
        if not chunk:
            return
        yield chunk


@lru_cache(maxsize=512)
def _get_windows_process_name(pid: Optional[int]) -> str:
    if not pid:
        return ""
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    line = result.stdout.strip()
    if line and not line.startswith("INFO:"):
        match = re.match(r'"([^"]+)"', line)
        if match:
            return match.group(1)
    fallback = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).ProcessName",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    return fallback.stdout.strip()
