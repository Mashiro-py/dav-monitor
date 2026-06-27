FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# 先装依赖（利用层缓存）。国内网络用清华 PyPI 镜像 + 超时/重试，避免从国外源拉取超时。
COPY requirements.txt .
RUN pip install --upgrade pip \
        -i https://pypi.tuna.tsinghua.edu.cn/simple \
        --trusted-host pypi.tuna.tsinghua.edu.cn \
    && pip install -r requirements.txt \
        -i https://pypi.tuna.tsinghua.edu.cn/simple \
        --trusted-host pypi.tuna.tsinghua.edu.cn \
        --timeout 120 --retries 10

# 再拷源码
COPY . .

EXPOSE 8000

# 监听 0.0.0.0:8000，供宿主机与同机其它容器访问
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
