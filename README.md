# Code-Server

在线代码执行平台 - 支持多种编程语言的在线运行

## 功能

- 在线编写和运行代码
- 支持 Python、JavaScript、Java、C++ 等多种语言
- Docker 隔离执行环境
- 用户认证系统
- 代码片段保存

## 技术栈

- Flask
- Docker
- SQLite

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python3 app.py
```

或使用快捷脚本：

```bash
./run.sh
```

访问 http://localhost:5000

## Docker 支持

需要安装 Docker 以支持沙箱执行：

```bash
sudo apt install docker.io
sudo systemctl enable docker
sudo systemctl start docker
```