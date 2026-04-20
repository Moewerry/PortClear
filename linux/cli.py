from __future__ import annotations

import argparse
from typing import Iterable, List

from core.actions import kill_record, record_action_hint
from core.inspector import inspect_ports
from core.privilege import get_privilege_info


def run_cli(argv: List[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    ports = _resolve_ports(args)

    privilege = get_privilege_info()
    print(f"当前权限: {privilege.label}")
    for limitation in privilege.limitations:
        print(f"- {limitation}")

    records = inspect_ports(ports if not args.all else None)
    if not records:
        print("未发现匹配的端口占用。")
        return 0

    for record in records:
        print("-" * 72)
        print(f"端口: {record.local_port}  协议: {record.protocol}  状态: {record.state}")
        print(f"本地地址: {record.local_address}:{record.local_port}")
        print(f"远端地址: {record.remote_address}:{record.remote_port or '*'}")
        print(f"PID: {record.pid or '-'}  进程: {record.process_name or '-'}")
        print(f"分类: {record.occupancy_type.value}")
        print(f"建议: {record.advice}")

        if args.kill and record.pid:
            ok, message = kill_record(record)
            print(f"操作: {message}")
        elif args.kill and not record.pid:
            print("操作: 当前记录没有可终止的 PID。")

        if args.verbose_hint:
            hint = record_action_hint(record)
            if hint:
                print("诊断:")
                print(hint)

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PortClear 端口占用诊断与清理工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--port", type=int, help="指定单个端口")
    group.add_argument("--ports", type=str, help="批量端口，逗号分隔")
    group.add_argument("--all", action="store_true", help="扫描所有端口")
    parser.add_argument("--kill", action="store_true", help="尝试终止占用端口的进程")
    parser.add_argument("--verbose-hint", action="store_true", help="输出更多诊断建议")
    return parser


def _resolve_ports(args: argparse.Namespace) -> List[int]:
    ports: List[int] = []
    if args.port is not None:
        ports = [args.port]
    elif args.ports:
        ports = [int(item.strip()) for item in args.ports.split(",") if item.strip()]

    for port in ports:
        if port < 1 or port > 65535:
            raise SystemExit(f"非法端口: {port}，端口范围必须在 1-65535。")
    return ports
