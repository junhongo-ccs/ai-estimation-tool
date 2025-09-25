FROM python:3.11-slim

WORKDIR /app

# システム依存パッケージ
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python依存パッケージ
COPY requirements_enhanced.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements_enhanced.txt

# アプリケーションコード
COPY . .

# 必要なディレクトリ
RUN mkdir -p static data logs

EXPOSE 8000

CMD ["uvicorn", "enhanced_main:app", "--host", "0.0.0.0", "--port", "8000"]