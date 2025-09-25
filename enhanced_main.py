import logging
import os
import re
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# --- AI Integration ---
import google.generativeai as genai

# --- Local Modules Integration ---
# hnavi_scraper.py と hnavi_integration.py をインポート
from hnavi_scraper import run_hnavi_scraping_poc
from hnavi_integration import HnaviDataProcessor

# --- 標準設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Gemini APIのセットアップ ---
try:
    load_dotenv()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini APIキーの設定が完了しました。")
    else:
        logger.error("環境変数 `GEMINI_API_KEY` が見つかりませんでした。AI機能は無効化されます。")
except Exception as e:
    logger.error(f"Gemini APIの初期化中にエラーが発生しました: {e}")
    GEMINI_API_KEY = None
# --- End Gemini API Setup ---

app = FastAPI(title="AI工数見積もりツール (RAG + Gemini Powered)", version="4.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- データモデル ---
class ProjectRequest(BaseModel):
    description: str
    category: Optional[str] = None
    platform: Optional[str] = "web"
    duration: str
    users: str

class EstimationResult(BaseModel):
    project_description: str
    estimated_features: List[str]
    total_hours: int
    total_cost: int
    phases: Dict[str, Dict[str, int]]
    similar_projects: List[Dict[str, str]]
    confidence_score: float
    data_source: str

# --- グローバル変数 & データ管理 ---
# HnaviDataProcessorのインスタンスをグローバルで保持
data_processor = HnaviDataProcessor()
last_data_refresh = None
DATA_FILE = 'processed_hnavi_data.pkl'

def data_refresh_logic():
    """データ更新のメインロジック"""
    global last_data_refresh
    try:
        logger.info("--- 発注ナビのデータ更新を開始します ---")
        # 1. スクレイピング実行
        run_hnavi_scraping_poc()
        # 2. データ処理と保存
        data_processor.load_and_process_data()
        data_processor.save_processed_data(DATA_FILE)
        last_data_refresh = datetime.now()
        logger.info(f"--- データ更新完了: {len(data_processor.processed_projects)}件のプロジェクトをロード ---")
    except Exception as e:
        logger.error(f"データ更新中にエラーが発生しました: {e}", exc_info=True)

# --- AIコンサルタント機能 ---
async def call_gemini_consultant(request: ProjectRequest, num_projects: int) -> Optional[Dict]:
    """Gemini APIを呼び出し、プロジェクトの総合的な分析を依頼する"""
    if not GEMINI_API_KEY:
        return None

    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
あなたは、NTTデータCCS社に所属する経験豊富なITコンサルタントです。
現在、{num_projects}件の類似案件データベースを参照できます。
以下の顧客からの要求を分析し、開発プロジェクトの初期提案に必要な情報を構造化されたJSON形式で出力してください。

# 顧客要求
- **アイディア**: {request.description}
- **希望開発期間**: {request.duration}
- **想定ユーザー規模**: {request.users}
- **指定カテゴリ**: {request.category or '未指定'}
- **プラットフォーム**: {request.platform}

# 出力形式 (JSON)
{{
  "project_summary": "（このプロジェクトを2-3文で要約）",
  "estimated_category": "（EC・通販, 業務システム, 予約・管理, モバイルアプリ, その他 の中から最も適切と思われるカテゴリを1つ選択）",
  "recommended_technologies": ["（推奨される技術や言語を3-5個リストアップ）"],
  "functional_requirements": ["（想定される機能要件を5-8個リストアップ）"],
  "non_functional_requirements": ["（想定される非機能要件を3-5個リストアップ）"],
  "potential_risks": ["（考えられる技術的リスクやプロジェクト進行上のリスクを2-3個リストアップ）"],
  "complexity": "（プロジェクト全体の複雑度を '高', '中', '低' のいずれかで評価）"
}}
"""
    try:
        logger.info("Geminiにプロジェクト分析を依頼しています...")
        response = await model.generate_content_async(prompt)
        json_text_match = re.search(r'```json\s*(\{.*?\})\s*```', response.text, re.DOTALL)
        if json_text_match:
            return json.loads(json_text_match.group(1))
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Gemini APIの処理中にエラーが発生しました: {e}")
        return None

# --- 見積もりロジック ---
def get_complexity_multiplier(complexity: str) -> float:
    return {"高": 1.5, "中": 1.1, "低": 0.8}.get(complexity, 1.0)

def calculate_duration_impact(duration: str, base_hours: int) -> int:
    multipliers = {"1month": 1.8, "2months": 1.4, "3months": 1.1, "4-6months": 1.0, "6-12months": 1.2, "1year+": 1.5}
    return int(base_hours * multipliers.get(duration, 1.0))

def calculate_user_scale_impact(users: str, base_cost: int) -> int:
    multipliers = {"small": 1.0, "medium": 1.3, "large": 1.8, "enterprise": 2.5, "public": 2.2}
    return int(base_cost * multipliers.get(users, 1.3))

def calculate_phases(total_hours: int, category: str) -> Dict[str, Dict[str, int]]:
    ratios = {
        "EC・通販": {"要件定義・設計": 0.25, "開発": 0.45, "テスト": 0.20, "デザイン": 0.10},
        "業務システム": {"要件定義・設計": 0.30, "開発": 0.50, "テスト": 0.15, "デザイン": 0.05},
        "default": {"要件定義・設計": 0.20, "開発": 0.50, "テスト": 0.20, "デザイン": 0.10}
    }.get(category, "default")
    
    phases = {}
    for phase, ratio in ratios.items():
        hours = int(total_hours * ratio)
        cost_ph = {"デザイン": 6000, "要件定義・設計": 7000}.get(phase, 5000)
        phases[phase] = {"hours": hours, "cost": hours * cost_ph}
    return phases

# --- 定期タスク ---
async def schedule_data_refresh(background_tasks: BackgroundTasks):
    global last_data_refresh
    if last_data_refresh is None or datetime.now() - last_data_refresh > timedelta(hours=24):
        logger.info("24時間以上経過したため、バックグラウンドでデータ更新タスクを開始します。")
        background_tasks.add_task(data_refresh_logic)
    else:
        logger.info("前回のデータ更新から24時間経過していないため、更新をスキップします。")

# --- APIエンドポイント ---
@app.on_event("startup")
async def startup_event():
    logger.info("--- アプリケーション起動プロセス開始 ---")
    if not data_processor.load_processed_data(DATA_FILE):
        logger.warning(f"{DATA_FILE}が見つかりません。初回のデータ生成タスクを実行します。")
        data_refresh_logic()
    else:
        global last_data_refresh
        last_data_refresh = datetime.fromtimestamp(os.path.getmtime(DATA_FILE))
        logger.info(f"既存データをロード完了: {len(data_processor.processed_projects)}件 (最終更新: {last_data_refresh})")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return FileResponse('static/index.html')

@app.post("/api/estimate", response_model=EstimationResult)
async def estimate_project(request: ProjectRequest, background_tasks: BackgroundTasks):
    # 見積もり実行時に定期更新をチェック
    await schedule_data_refresh(background_tasks)
    
    try:
        logger.info(f"--- 新規見積もりリクエスト --- \n概要: {request.description}")
        
        # ステップ1: AIによるプロジェクト分析
        ai_analysis = await call_gemini_consultant(request, len(data_processor.processed_projects))
        
        if not ai_analysis:
            raise HTTPException(status_code=503, detail="AIコンサルタントの分析に失敗しました。")

        logger.info(f"AI分析結果: {ai_analysis}")
        
        # ステップ2: AIの分析を基に類似案件をRAG検索
        query_text = f"{ai_analysis['project_summary']} {' '.join(ai_analysis['functional_requirements'])}"
        similar_projects = data_processor.find_similar_projects(query_text, top_k=5)
        
        # ステップ3: 基本工数・コストを算出
        if similar_projects:
            total_weight = sum(s[1] for s in similar_projects)
            base_hours = sum(s[0].estimated_hours * s[1] for s in similar_projects) / total_weight
            base_cost = sum(s[0].avg_price * s[1] for s in similar_projects) / total_weight
            confidence = sum(s[0].confidence * s[1] for s in similar_projects) / total_weight
            data_source = "発注ナビDB (AI-RAG検索)"
        else:
            base_hours, base_cost, confidence, data_source = 500, 2500000, 0.4, "デフォルト値 (類似案件なし)"

        # ステップ4: 各種係数で調整
        adjusted_hours = calculate_duration_impact(request.duration, base_hours)
        adjusted_cost = calculate_user_scale_impact(request.users, base_cost)
        complexity_multiplier = get_complexity_multiplier(ai_analysis.get("complexity", "中"))

        final_hours = int(adjusted_hours * complexity_multiplier)
        final_cost = int(adjusted_cost * complexity_multiplier)

        # ステップ5: 最終的なアウトプットを生成
        features = [f"【推奨技術】{f}" for f in ai_analysis.get("recommended_technologies", [])] + \
                   ai_analysis.get("functional_requirements", []) + \
                   [f"【非機能】{f}" for f in ai_analysis.get("non_functional_requirements", [])] + \
                   [f"【リスク】{f}" for f in ai_analysis.get("potential_risks", [])]

        phases = calculate_phases(final_hours, ai_analysis.get("estimated_category", "default"))
        
        similar_projects_output = [{
            "title": p.title, "description": p.description, "hours": str(p.estimated_hours),
            "cost": f"{int(p.avg_price):,}円", "similarity": f"{sim*100:.1f}%", "company": p.company_name
        } for p, sim in similar_projects]

        result = EstimationResult(
            project_description=ai_analysis.get("project_summary", request.description),
            estimated_features=list(set(features)), total_hours=final_hours, total_cost=final_cost,
            phases=phases, similar_projects=similar_projects_output,
            confidence_score=min(confidence * 1.1, 0.95),
            data_source=f"{data_source} | 複雑度:{ai_analysis.get('complexity', '中')}"
        )

        logger.info(f"--- 見積もり完了 --- \n工数: {result.total_hours}h, 費用: {result.total_cost:,}円, 信頼度: {result.confidence_score:.2f}")
        return result

    except Exception as e:
        logger.error(f"見積もりAPIで致命的なエラー: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="サーバー内部で予期せぬエラーが発生しました。")

@app.get("/health")
async def health_check():
    return {
        "status": "OK", "timestamp": datetime.now().isoformat(), "version": "4.0.0",
        "gemini_api_configured": bool(GEMINI_API_KEY),
        "data_projects": len(data_processor.processed_projects),
        "last_data_refresh": last_data_refresh.isoformat() if last_data_refresh else "N/A"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)