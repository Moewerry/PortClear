from __future__ import annotations

import platform
import sys


def main() -> int:
    system = platform.system()
    if system == "Windows":
        from windows.gui import run_gui

        run_gui()
        return 0

    from linux.cli import run_cli

    return run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
