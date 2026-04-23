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
        args = parser.parse_args(sys.argv[1:])

        if args.gui:
            from windows.gui import run_gui

            run_gui()
            return 0

        from windows.tray import run_tray

        return run_tray()

    from linux.cli import run_cli

    return run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
