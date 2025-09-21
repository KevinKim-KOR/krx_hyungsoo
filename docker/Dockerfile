FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul

RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata ca-certificates build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 설치
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 소스는 런타임에 볼륨 마운트 (compose에서)
CMD ["sleep", "infinity"]
