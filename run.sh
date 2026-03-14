#!/bin/bash

set -e

echo "===== 代码运行测试平台启动 ====="

echo "检查 Docker..."
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

echo "安装 Python 依赖..."
pip install -r requirements.txt

echo "构建代码沙箱镜像..."
docker build -t code-sandbox:latest docker/sandbox/ || true

echo "启动 Flask 应用..."
cd "$(dirname "$0")"
python app.py
