@echo off
echo ============================================
echo PortClear - 打包为 EXE
echo ============================================
echo.

echo [1/3] 安装依赖...
pip install pyinstaller
pip install -r requirements-windows.txt
echo.

echo [2/3] 开始打包...
pyinstaller --clean portclear.spec
echo.

echo [3/3] 打包完成！
echo EXE 文件位于: dist\PortClear.exe
echo.
pause
