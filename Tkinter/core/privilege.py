from __future__ import annotations

import ctypes
import os
import platform

from core.models import PrivilegeInfo


def get_privilege_info() -> PrivilegeInfo:
    system = platform.system()

    if system == "Windows":
        try:
            elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            elevated = False
        label = "管理员" if elevated else "普通用户"
        limitations = [] if elevated else [
            "无法终止其他用户的进程",
            "无法执行 HTTP.sys 深度诊断",
            "无法调整 TIME_WAIT 相关系统参数",
        ]
        return PrivilegeInfo(system, elevated, label, limitations)

    elevated = hasattr(os, "geteuid") and os.geteuid() == 0
    label = "root" if elevated else "普通用户"
    limitations = [] if elevated else [
        "无法查看其他用户进程的完整 PID/命令信息",
        "无法终止其他用户的进程",
        "无法调整 TIME_WAIT 相关内核参数",
    ]
    return PrivilegeInfo(system, elevated, label, limitations)


def current_uid() -> int | None:
    if hasattr(os, "geteuid"):
        return os.geteuid()
    return None
