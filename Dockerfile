FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Non-interactive install + set timezone to Asia/Shanghai
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# Use Aliyun apt mirror
RUN sed -i 's@archive.ubuntu.com@mirrors.aliyun.com@g' /etc/apt/sources.list

# System dependencies
RUN apt-get update && apt-get install -y \
    tzdata \
    software-properties-common \
    && ln -fs /usr/share/zoneinfo/$TZ /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    ffmpeg libsndfile1 libsndfile1-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Use Tsinghua pip mirror with official PyPI as fallback
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip3 config set global.extra-index-url https://pypi.org/simple

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY app /app/app
COPY static /app/static

WORKDIR /app

# Use HF mirror for model downloads
ENV HF_ENDPOINT=https://hf-mirror.com

# Create necessary directories
RUN mkdir -p /app/output /app/data

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
