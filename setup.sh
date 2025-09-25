#!/bin/bash

# AI工数見積もりツール GitHub/Codespace セットアップスクリプト

echo "🚀 AI工数見積もりツール GitHub/Codespace セットアップ開始"

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}📝 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Step 1: 基本ディレクトリ構造作成
print_step "基本ディレクトリ構造を作成中..."
mkdir -p static
mkdir -p data
mkdir -p logs
print_success "ディレクトリ構造を作成しました"

# Step 2: 必須ファイルの存在確認
print_step "必須ファイルの存在を確認中..."

required_files=(
    "enhanced_main.py"
    "hnavi_scraper.py"
    "hnavi_integration.py"
    "run_hnavi_poc.py"
    "validation_demo.py"
    "static/index.html"
    "requirements_enhanced.txt"
    "railway.toml"
    "Dockerfile"
    ".gitignore"
    "HNAVI_README.md"
)

missing_files=()

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        print_success "$file - 存在します"
    else
        print_warning "$file - 見つかりません"
        missing_files+=("$file")
    fi
done

if [ ${#missing_files[@]} -gt 0 ]; then
    print_error "以下のファイルが不足しています:"
    printf '%s\n' "${missing_files[@]}"
    echo "Claude Artifactsからファイルをコピーしてください"
    exit 1
fi

# Step 3: Python環境チェック
print_step "Python環境をチェック中..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    print_success "Python環境: $PYTHON_VERSION"
else
    print_error "Python3が見つかりません"
    exit 1
fi

# Step 4: 仮想環境セットアップ
print_step "仮想環境をセットアップ中..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "仮想環境を作成しました"
else
    print_success "仮想環境が既に存在します"
fi

# 仮想環境を有効化
source venv/bin/activate
print_success "仮想環境を有効化しました"

# Step 5: 拡張版依存関係インストール
print_step "拡張版依存関係をインストール中..."
pip install --upgrade pip
pip install -r requirements_enhanced.txt
print_success "依存関係のインストールが完了しました"

# Step 6: 設定ファイル作成
print_step "設定ファイルを作成中..."

# .env ファイル作成
if [ ! -f ".env" ]; then
    cat > .env << EOF
# AI工数見積もりツール 環境設定
PORT=8000
DEBUG=True
LOG_LEVEL=INFO
SCRAPING_MODE=test
MAX_COMPANIES=10
DELAY_SECONDS=2.0
EOF
    print_success ".env ファイルを作成しました"
else
    print_success ".env ファイルが既に存在します"
fi

# Step 7: テストデータ生成
print_step "テストデータを生成中..."
python run_hnavi_poc.py --test-mode
print_success "テストデータを生成しました"

# Step 8: アプリケーション動作テスト
print_step "アプリケーションの動作をテスト中..."

# バックグラウンドでサーバーを起動
python enhanced_main.py &
SERVER_PID=$!

# サーバーの起動を待つ
sleep 10

# ヘルスチェック
if curl -s http://localhost:8000/health > /dev/null; then
    print_success "アプリケーションが正常に動作しています"
else
    print_warning "アプリケーションの動作確認に失敗しました"
fi

# サーバーを停止
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

# Step 9: Git設定確認
print_step "Git設定を確認中..."

if [ -d ".git" ]; then
    print_success "Gitリポジトリが初期化されています"
    
    # Git設定の確認
    if git config user.name > /dev/null && git config user.email > /dev/null; then
        print_success "Git設定が完了しています"
    else
        print_warning "Git設定が不完全です。以下のコマンドで設定してください:"
        echo "git config --global user.name 'Your Name'"
        echo "git config --global user.email 'your.email@example.com'"
    fi
else
    print_warning "Gitリポジトリが初期化されていません"
    echo "git init でリポジトリを初期化してください"
fi

# Step 10: セットアップ完了サマリー
echo ""
echo "============================================="
print_success "セットアップが完了しました！"
echo "============================================="
echo ""
echo "🎯 次のステップ:"
echo "1. アプリケーションの起動:"
echo "   source venv/bin/activate"
echo "   python enhanced_main.py"
echo ""
echo "2. ブラウザでアクセス:"
echo "   http://localhost:8000"
echo ""
echo "3. 発注ナビデータ収集（テストモード）:"
echo "   python run_hnavi_poc.py --test-mode"
echo ""
echo "4. GitHubにプッシュ:"
echo "   git add ."
echo "   git commit -m 'Initial commit: AI工数見積もりツール（必須項目対応版）'"
echo "   git push origin main"
echo ""
echo "5. Railway デプロイ:"
echo "   - Railway ダッシュボードでリポジトリを選択"
echo "   - 自動デプロイが開始されます"
echo ""
echo "📊 プロジェクト統計:"
echo "- Pythonファイル数: $(find . -name "*.py" | wc -l)"
echo "- 総行数: $(find . -name "*.py" -exec wc -l {} + | tail -1)"
echo "- 機能: 必須項目対応、発注ナビ統合、高精度見積もり"
echo ""
print_success "セットアップスクリプト完了 🎉"
