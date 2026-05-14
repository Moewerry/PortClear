from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from core.privilege import get_privilege_info
from windows.gui import PortClearApp
from windows.quick_panel import QuickPanel

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    pystray = None
    Image = None
    ImageDraw = None


class TrayApp:
    def __init__(self, auto_open_quick_panel: bool = False) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("PortClear")
        self.icon = None
        self.main_window: tk.Toplevel | None = None
        self.auto_open_quick_panel = auto_open_quick_panel
        self.quick_panel = QuickPanel(
            self.root,
            open_main_window=self.open_main_window,
            elevate=self.elevate,
        )

    def run(self) -> int:
        if pystray is None:
            messagebox.showwarning(
                "缺少托盘依赖",
                "未安装 pystray/pillow，已回退到普通窗口模式。\n\n请执行: pip install pystray pillow",
            )
            self.root.destroy()
            from windows.gui import run_gui

            run_gui()
            return 0

        self.icon = pystray.Icon("PortClear", self._create_icon(), "PortClear", self._build_menu())
        threading.Thread(target=self.icon.run, daemon=True).start()
        if self.auto_open_quick_panel:
            self.root.after(250, self.open_quick_panel)
        self.root.mainloop()
        return 0

    def open_quick_panel(self) -> None:
        self.root.after(0, self.quick_panel.show)

    def open_main_window(self) -> None:
        def _open() -> None:
            if self.main_window is not None and self.main_window.winfo_exists():
                self.main_window.deiconify()
                self.main_window.lift()
                self.main_window.focus_force()
                return

            self.main_window = tk.Toplevel(self.root)
            self.main_window.protocol("WM_DELETE_WINDOW", self.main_window.withdraw)
            PortClearApp(self.main_window)

        self.root.after(0, _open)

    def elevate(self) -> None:
        try:
            executable, parameters, workdir = _build_elevated_command()
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                executable,
                parameters,
                workdir,
                1,
            )
            if result > 32:
                self.quit()
        except Exception as exc:  # pragma: no cover
            self.root.after(0, lambda: messagebox.showerror("提权失败", str(exc)))

    def quit(self) -> None:
        if self.icon is not None:
            self.icon.stop()
        self.root.after(0, self.root.quit)

    def _build_menu(self):
        privilege = get_privilege_info()
        return pystray.Menu(
            pystray.MenuItem(f"当前权限: {privilege.label}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("快速查询端口", lambda _icon, _item: self.open_quick_panel(), default=True),
            pystray.MenuItem("打开主窗口", lambda _icon, _item: self.open_main_window()),
            pystray.MenuItem("以管理员身份运行", lambda _icon, _item: self.elevate(), enabled=not privilege.is_elevated),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda _icon, _item: self.quit()),
        )

    def _create_icon(self):
        image = Image.new("RGBA", (64, 64), (18, 92, 120, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((7, 7, 57, 57), radius=14, fill=(15, 118, 110, 255))
        draw.rectangle((19, 16, 45, 23), fill=(236, 253, 245, 255))
        draw.rectangle((19, 29, 45, 36), fill=(236, 253, 245, 255))
        draw.rectangle((19, 42, 45, 49), fill=(236, 253, 245, 255))
        return image


def run_tray(auto_open_quick_panel: bool = False) -> int:
    app = TrayApp(auto_open_quick_panel=auto_open_quick_panel)
    return app.run()


def _build_elevated_command() -> tuple[str, str, str]:
    """Build a UAC command that works in both source and packaged modes."""
    if getattr(sys, "frozen", False):
        args = [arg for arg in sys.argv[1:] if arg != "--gui"]
        if "--tray" not in args:
            args.append("--tray")
        if "--open-quick-panel" not in args:
            args.append("--open-quick-panel")
        return sys.executable, subprocess.list2cmdline(args), str(Path(sys.executable).parent)

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = str(pythonw if pythonw.exists() else Path(sys.executable))
    project_root = Path(__file__).resolve().parents[1]
    main_script = project_root / "main.py"
    args = [str(main_script), "--tray", "--open-quick-panel"]
    return executable, subprocess.list2cmdline(args), str(project_root)
