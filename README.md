# PortClear

PortClear 是一个跨平台端口占用诊断与清理工具：

- Windows 提供 GUI，区分管理员与普通用户能力
- Linux 提供 CLI，区分 root 与普通用户能力
- 能区分普通进程占用、Windows PID 4/HTTP.sys、TIME_WAIT、CLOSE_WAIT

## 项目结构

- `core/`：权限检测、端口查询、分类、终止、诊断建议
- `windows/`：Windows GUI
- `linux/`：Linux CLI
- `main.py`：自动按平台分发入口

## 运行

### Windows

```bash
python main.py
```

如果安装了 `customtkinter`，会使用更现代的 GUI；未安装时自动回退到原生 `tkinter`。

建议安装：

```bash
pip install customtkinter
```

### Linux

```bash
python3 main.py --port 8080
python3 main.py --ports 8080,3306,6379
python3 main.py --all
python3 main.py --port 8080 --kill
python3 main.py --port 8080 --verbose-hint
```

## 权限说明

- Windows 普通用户：
  - 不能直接终止受限进程
  - 不能执行 HTTP.sys 深度诊断
  - 不能修改 TIME_WAIT 相关系统参数
- Linux 普通用户：
  - 可能看不到其他用户进程的 PID/命令
  - 只能终止自己的进程
  - 不能调整 TIME_WAIT 内核参数

## 行为说明

- `TIME_WAIT`：不能强制删除，只能等待自动回收或调整系统参数
- `CLOSE_WAIT`：通常意味着应用未正常关闭连接，优先终止对应进程
- `PID 4`：Windows 下表示 HTTP.sys/System 占用，不能直接结束，需执行 `netsh http show servicestate` 继续排查

## 打包建议

Windows 可用 PyInstaller 打包：

```bash
pip install pyinstaller
pyinstaller -F -w main.py -n PortClear
```
