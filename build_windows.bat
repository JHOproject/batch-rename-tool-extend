@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 正在建立独立的 Python 环境（需要 Python 3.11 64 位）。
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo 请先安装 Python 3.11（64 位）。
        pause
        exit /b 1
    )
)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt "pyinstaller>=6.10,<7"
if errorlevel 1 (
    echo 安装依赖失败。
    pause
    exit /b 1
)
python -m PyInstaller --noconfirm --clean --onefile --windowed --name BatchRenameTool main.py
if errorlevel 1 (
    echo 打包失败，请查看上方错误信息。
    pause
    exit /b 1
)
echo.
echo Windows 程序已生成： dist\BatchRenameTool.exe
echo 正式处理文件前，请先在 Windows 上测试这个 exe。
pause
