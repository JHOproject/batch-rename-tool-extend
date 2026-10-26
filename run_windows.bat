@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 正在建立独立的 Python 环境（需要 Python 3.11 64 位）。
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo 找不到 Python 3.11（64 位），请先安装再试。
        pause
        exit /b 1
    )
)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo 安装依赖失败，请检查网络及 Python 环境。
    pause
    exit /b 1
)
python main.py
if errorlevel 1 (
    echo 程序运行时发生错误。
    pause
)
