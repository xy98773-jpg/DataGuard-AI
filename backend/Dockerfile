# DataGuard AI backend 镜像
FROM python:3.12-slim

WORKDIR /app

# 1) Python 依赖（清华源加速；pandas/polars/lxml/openpyxl 均有预编译 wheel）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2) 系统依赖：chromium（PDF 报告导出用；找不到时后端自动降级为仅 HTML）
#    换清华 Debian 源 + 自动重试，避免官方源超时断线
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends -o Acquire::Retries=5 chromium fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 3) 应用代码（不含 storage/.env/tests —— 见 .dockerignore）
COPY app/ ./app/
COPY prompts/ ./prompts/

# 4) 非 root 运行（安全）
RUN useradd -m appuser
USER appuser

# 数据默认落在 /app/storage（config 默认路径），由 compose 挂载 docker-storage 卷持久化
VOLUME ["/app/storage"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
