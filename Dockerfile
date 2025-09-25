# ベースイメージ
FROM python:3.11-slim

# 作業ディレクトリ作成
WORKDIR /app

# 必要ファイルをコピー
COPY . /app

# pipアップグレード & 依存パッケージインストール
RUN pip install --upgrade pip \
    && pip install -r requirements_enhanced.txt

# ポート設定
EXPOSE 8000

# FastAPIアプリ起動（例: uvicorn使用）
CMD ["uvicorn", "enhanced_main:app", "--host", "0.0.0.0", "--port", "8000"]
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pythonの依存関係をコピーしてインストール
COPY requirements_enhanced.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements_enhanced.txt

# アプリケーションのコードをコピー
COPY . .

# 必要なディレクトリを作成
RUN mkdir -p static data logs

# ポートを公開
EXPOSE $PORT

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# アプリケーションを起動
CMD uvicorn enhanced_main:app --host 0.0.0.0 --port $PORT

