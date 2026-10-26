#!/bin/bash
# 仅用于 macOS 测试 Python 源码；正式版本仍是 Windows .exe。
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3.11 >/dev/null 2>&1; then
    PYTHON=python3.11
elif command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
else
    echo "找不到 Python 3，请先安装 Python 3.11 再试。"
    exit 1
fi

if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' ; then
    echo "目前的 $PYTHON 版本太旧，请安装 Python 3.11 或更新版本。"
    exit 1
fi

if [ ! -f .venv-mac/bin/python ]; then
    echo '第一次运行：建立独立的 Python 环境...'
    "$PYTHON" -m venv .venv-mac
fi

if ! .venv-mac/bin/python -c 'import PySide6, openpyxl, xlrd' >/dev/null 2>&1; then
    echo '安装 GUI 和 Excel/CSV 依赖（第一次需要网络）...'
    .venv-mac/bin/python -m pip install -r requirements.txt
fi

echo '正在启动批量文件重命名工具（macOS 测试模式）...'
.venv-mac/bin/python main.py
