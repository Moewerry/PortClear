from __future__ import annotations

import argparse
import platform
import sys


def main() -> int:
    system = platform.system()
    if system == "Windows":
        parser = argparse.ArgumentParser(description="PortClear Windows")
        parser.add_argument("--gui", action="store_true", help="打开完整窗口")
        parser.add_argument("--tray", action="store_true", help="启动任务栏托盘模式")
        parser.add_argument("--open-quick-panel", action="store_true", help="启动后自动打开快速查询面板")
        args = parser.parse_args(sys.argv[1:])

        if args.tray:
            from windows.tray import run_tray

            return run_tray(auto_open_quick_panel=args.open_quick_panel)

        from windows.gui import run_gui

        run_gui()
        return 0

    from linux.cli import run_cli

    return run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
