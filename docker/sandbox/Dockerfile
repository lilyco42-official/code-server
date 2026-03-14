# 代码沙箱 Docker 镜像构建
FROM python:3.11-slim

RUN pip install --no-cache-dir docker==6.0.0

WORKDIR /code

CMD ["python", "-c", "while True: import time; time.sleep(60)"]
