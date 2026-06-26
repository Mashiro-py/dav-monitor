FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# 先装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install -r requirements.txt

# 再拷源码
COPY . .

EXPOSE 8000

# 监听 0.0.0.0:8000，供宿主机与同机其它容器访问
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
