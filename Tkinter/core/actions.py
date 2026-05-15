from __future__ import annotations

import os
import platform
import subprocess

from core.inspector import diagnose_http_sys
from core.models import OccupancyType, PortRecord
from core.privilege import current_uid, get_privilege_info


def kill_record(record: PortRecord) -> tuple[bool, str]:
    if not record.pid:
        return False, "当前记录没有可终止的 PID。"
    if platform.system() == "Windows" and record.pid == 4:
        return False, "PID 4(System) 不能直接终止，请使用 HTTP.sys 诊断。"
    allowed, message = can_kill_pid(record.pid)
    if not allowed:
        return False, message
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/PID", str(record.pid), "/F"], check=True, capture_output=True, text=True)
        else:
            subprocess.run(["kill", "-9", str(record.pid)], check=True, capture_output=True, text=True)
        return True, f"已终止 PID {record.pid}。"
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return False, f"终止失败: {detail}"


def can_kill_pid(pid: int) -> tuple[bool, str]:
    privilege = get_privilege_info()
    if privilege.is_elevated:
        return True, ""
    if platform.system() == "Windows":
        return False, "当前不是管理员，无法强制终止其他进程。请以管理员身份重新运行。"

    owner_uid = _get_linux_pid_uid(pid)
    uid = current_uid()
    if owner_uid is None or uid is None:
        return False, "无法确认进程归属，请使用 sudo 运行。"
    if owner_uid != uid:
        return False, "当前只能终止属于自己的进程，请使用 sudo 运行。"
    return True, ""


def time_wait_tuning_advice() -> str:
    privilege = get_privilege_info()
    system = platform.system()
    if system == "Windows":
        if not privilege.is_elevated:
            return (
                "当前不是管理员，无法修改 Windows TIME_WAIT 参数。\n"
                '建议以管理员身份运行后执行:\n'
                'Get-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters" -Name "TcpTimedWaitDelay"\n'
                'Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters" -Name "TcpTimedWaitDelay" -Value 30'
            )
        return (
            "可调整 Windows TIME_WAIT 等待时间。\n"
            '查看当前值:\n'
            'Get-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters" -Name "TcpTimedWaitDelay"\n'
            '设置为 30 秒:\n'
            'Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters" -Name "TcpTimedWaitDelay" -Value 30\n'
            "注意: 该调整需要管理员权限，且对 CLOSE_WAIT 无效。"
        )

    if not privilege.is_elevated:
        return (
            "当前不是 root，无法调整 Linux TIME_WAIT 参数。\n"
            "建议使用 sudo 执行:\n"
            "sysctl -w net.ipv4.tcp_tw_reuse=1\n"
            "sysctl -w net.ipv4.tcp_fin_timeout=30\n"
            "注意: 该调整仅影响 TIME_WAIT，对 CLOSE_WAIT 无效。"
        )
    return (
        "可临时调优 Linux TIME_WAIT 回收。\n"
        "sysctl -w net.ipv4.tcp_tw_reuse=1\n"
        "sysctl -w net.ipv4.tcp_fin_timeout=30\n"
        "注意: 该调整仅影响 TIME_WAIT，对 CLOSE_WAIT 无效。"
    )


def record_action_hint(record: PortRecord) -> str:
    if record.occupancy_type == OccupancyType.HTTP_SYS:
        return diagnose_http_sys(record.local_port)
    if record.occupancy_type == OccupancyType.TIME_WAIT:
        return time_wait_tuning_advice()
    if record.occupancy_type == OccupancyType.CLOSE_WAIT:
        return "检测到 CLOSE_WAIT，这通常是应用未正确关闭连接。建议结束对应进程。"
    return record.advice


def _get_linux_pid_uid(pid: int) -> int | None:
    path = f"/proc/{pid}/status"
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.startswith("Uid:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1])
    except (OSError, ValueError):
        return None
    return None
