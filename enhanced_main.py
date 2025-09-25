from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import pandas as pd
import re
import json
from typing import List, Dict, Optional, Tuple
import logging
import os
from datetime import datetime
import asyncio

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI工数見積もりツール（必須項目対応版）", version="2.1.0")

# 静的ファイルをマウント
app.mount("/static", StaticFiles(directory="static"), name="static")

# データモデル
class ProjectRequest(BaseModel):
    description: str
    category: Optional[str] = None
    platform: Optional[str] = "web"
    duration: str  # 必須項目
    users: str     # 必須項目

class EstimationResult(BaseModel):
    project_description: str
    estimated_features: List[str]
    total_hours: int
    total_cost: int
    phases: Dict[str, Dict[str, int]]
    similar_projects: List[Dict[str, str]]
    confidence_score: float
    data_source: str

# グローバル変数
estimation_data = []
last_update = None

def load_sample_data():
    """サンプルデータを読み込み"""
    global estimation_data, last_update
    
    estimation_data = [
        {
            "title": "ECサイト構築（アパレル向け）",
            "description": "商品管理、在庫管理、決済システム、顧客管理を含むアパレル向けECサイト。レスポンシブ対応、管理画面付き",
            "category": "EC・通販",
            "hours": 880,
            "cost": 5500000,
            "features": ["商品管理", "在庫管理", "決済システム", "顧客管理", "Laravel", "MySQL", "AWS"],
            "company": "ECソリューション株式会社",
            "source": "https://hnavi.co.jp/company/ec-solution",
            "confidence": 0.9
        },
        {
            "title": "業務管理システム（販売・顧客管理）",
            "description": "販売管理、顧客管理、請求書発行機能を含む業務システム。データ分析レポート機能付き",
            "category": "業務システム",
            "hours": 760,
            "cost": 4750000,
            "features": ["販売管理", "顧客管理", "請求書発行", "データ分析", "Java", "Spring Boot", "PostgreSQL"],
            "company": "ビジネスシステムズ合同会社",
            "source": "https://hnavi.co.jp/company/business-systems",
            "confidence": 0.85
        },
        {
            "title": "予約管理システム（サロン・クリニック向け）",
            "description": "オンライン予約、カレンダー管理、通知機能を含む予約システム。スマホアプリ連携対応",
            "category": "予約・管理",
            "hours": 440,
            "cost": 2750000,
            "features": ["予約管理", "カレンダー", "通知機能", "スマホ対応", "Python", "Django", "Vue.js"],
            "company": "リザーブテック株式会社",
            "source": "https://hnavi.co.jp/company/reserve-tech",
            "confidence": 0.8
        },
        {
            "title": "コーポレートサイト（多言語対応）",
            "description": "会社紹介、ニュース管理、お問い合わせ、採用情報を含む企業サイト。SEO対策・多言語対応",
            "category": "コーポレート",
            "hours": 200,
            "cost": 1250000,
            "features": ["会社紹介", "ニュース管理", "問い合わせ", "多言語対応", "WordPress", "PHP"],
            "company": "ウェブクリエイト株式会社", 
            "source": "https://hnavi.co.jp/company/web-create",
            "confidence": 0.75
        },
        {
            "title": "在庫管理システム（製造業向け）",
            "description": "商品の入出庫管理、在庫数管理、発注アラート機能を含む製造業向け在庫管理システム",
            "category": "業務システム",
            "hours": 520,
            "cost": 3200000,
            "features": ["入出庫管理", "在庫数管理", "アラート機能", "レポート機能", ".NET", "SQL Server"],
            "company": "インベントリシステム株式会社",
            "source": "https://hnavi.co.jp/company/inventory-systems",
            "confidence": 0.8
        },
        {
            "title": "モバイルアプリ開発（iOS・Android）",
            "description": "ネイティブアプリ開発。API連携、プッシュ通知、位置情報機能付きモバイルアプリ",
            "category": "モバイルアプリ",
            "hours": 640,
            "cost": 4000000,
            "features": ["iOS対応", "Android対応", "API連携", "プッシュ通知", "Swift", "Kotlin"],
            "company": "モバイルデベロップ株式会社",
            "source": "https://hnavi.co.jp/company/mobile-develop", 
            "confidence": 0.8
        }
    ]
    
    last_update = datetime.now()
    logger.info(f"サンプルデータ読み込み完了: {len(estimation_data)}件")

def calculate_duration_impact(duration: str, base_hours: int) -> Tuple[int, float]:
    """開発期間による工数・コスト調整"""
    duration_multipliers = {
        "1month": {"multiplier": 1.8, "risk": "高"},      # 短期間は高コスト・高リスク
        "2months": {"multiplier": 1.4, "risk": "中"},
        "3months": {"multiplier": 1.1, "risk": "低"},    # 標準的
        "4-6months": {"multiplier": 1.0, "risk": "低"},  # 最適
        "6-12months": {"multiplier": 1.2, "risk": "中"}, # 長期化によるコスト増
        "1year+": {"multiplier": 1.5, "risk": "高"}      # 仕様変更リスク
    }
    
    duration_info = duration_multipliers.get(duration, {"multiplier": 1.0, "risk": "中"})
    adjusted_hours = int(base_hours * duration_info["multiplier"])
    
    return adjusted_hours, duration_info["multiplier"]

def calculate_user_scale_impact(users: str, base_cost: int) -> Tuple[int, Dict]:
    """ユーザー規模による技術要件・コスト調整"""
    user_scale_adjustments = {
        "small": {
            "multiplier": 1.0,
            "infrastructure": "基本",
            "additional_features": ["基本認証", "簡易管理画面"],
            "tech_requirements": "標準的な構成"
        },
        "medium": {
            "multiplier": 1.3,
            "infrastructure": "スケーラブル",
            "additional_features": ["ロードバランサー", "DB最適化", "キャッシュシステム"],
            "tech_requirements": "中規模対応・パフォーマンス最適化"
        },
        "large": {
            "multiplier": 1.8,
            "infrastructure": "高可用性",
            "additional_features": ["CDN", "冗長化", "監視システム", "自動スケーリング"],
            "tech_requirements": "大規模対応・高可用性設計"
        },
        "enterprise": {
            "multiplier": 2.5,
            "infrastructure": "エンタープライズ",
            "additional_features": ["マイクロサービス", "API Gateway", "セキュリティ強化", "バックアップシステム"],
            "tech_requirements": "エンタープライズ級・セキュリティ重視"
        },
        "public": {
            "multiplier": 2.2,
            "infrastructure": "パブリック対応",
            "additional_features": ["DDoS対策", "グローバルCDN", "多言語対応", "アクセス解析"],
            "tech_requirements": "パブリック向け・グローバル対応"
        }
    }
    
    user_info = user_scale_adjustments.get(users, user_scale_adjustments["medium"])
    adjusted_cost = int(base_cost * user_info["multiplier"])
    
    return adjusted_cost, user_info

def extract_keywords(text: str) -> List[str]:
    """テキストからキーワードを抽出"""
    keywords = []
    keyword_patterns = [
        r'EC|通販|ショッピング|ecommerce',
        r'管理|システム|業務|CRM|ERP',
        r'予約|カレンダー|スケジュール|booking',
        r'サイト|ホームページ|Web|website',
        r'在庫|商品|売上|inventory',
        r'顧客|会員|customer|member',
        r'決済|支払い|課金|payment',
        r'分析|レポート|統計|analytics',
        r'CMS|コンテンツ|記事',
        r'アプリ|mobile|iOS|Android'
    ]
    
    for pattern in keyword_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            keywords.extend(re.findall(pattern, text, re.IGNORECASE))
    
    return list(set([k.lower() for k in keywords]))

def calculate_similarity_enhanced(description: str, project_data: Dict) -> float:
    """拡張類似度計算"""
    desc_keywords = set(extract_keywords(description.lower()))
    
    # プロジェクトのキーワードを結合
    project_text = f"{project_data['title']} {project_data['description']} {' '.join(project_data.get('features', []))}"
    project_keywords = set(extract_keywords(project_text.lower()))
    
    if not desc_keywords and not project_keywords:
        return 0.0
    
    # Jaccard係数で類似度計算
    intersection = desc_keywords.intersection(project_keywords)
    union = desc_keywords.union(project_keywords)
    
    similarity = len(intersection) / len(union) if union else 0.0
    
    # 信頼度で重み付け
    confidence = project_data.get('confidence', 0.5)
    return similarity * (0.7 + 0.3 * confidence)

def estimate_features_with_requirements(description: str, duration: str, users: str) -> List[str]:
    """必須項目を考慮した機能推定"""
    features = []
    
    # 基本的なキーワードベースの機能推定
    feature_mapping = {
        r'EC|通販|ショッピング|商品': ["商品管理", "在庫管理", "決済システム", "顧客管理", "注文管理"],
        r'予約|カレンダー|スケジュール|booking': ["予約管理", "カレンダー機能", "通知機能", "顧客管理"],
        r'管理|システム|業務|CRM|ERP': ["データ管理", "レポート機能", "ユーザー管理", "権限管理"],
        r'サイト|ホームページ|Web|website': ["レスポンシブ対応", "問い合わせ機能", "CMS", "SEO対策"],
        r'アプリ|mobile|iOS|Android': ["モバイル対応", "プッシュ通知", "オフライン機能", "位置情報"],
        r'在庫|inventory': ["入出庫管理", "在庫数管理", "アラート機能", "棚卸し機能"],
        r'顧客|会員|customer|CRM': ["顧客管理", "会員登録", "マイページ", "履歴管理"],
        r'決済|payment|支払い': ["決済システム", "請求管理", "売上管理", "返金処理"],
        r'分析|レポート|統計|analytics': ["データ分析", "レポート機能", "ダッシュボード", "KPI管理"]
    }
    
    for pattern, feature_list in feature_mapping.items():
        if re.search(pattern, description, re.IGNORECASE):
            features.extend(feature_list)
    
    # 開発期間による機能調整
    if duration == "1month":
        # 短期間：MVP機能のみ
        priority_features = ["認証機能", "基本CRUD", "管理画面"]
        features = [f for f in features if any(pf in f for pf in priority_features)][:8]
        features.append("MVP機能限定")
    elif duration in ["4-6months", "6-12months", "1year+"]:
        # 長期間：高度な機能追加
        features.extend(["高度なレポート機能", "ワークフロー管理", "外部システム連携"])
    
    # ユーザー規模による機能調整
    if users in ["large", "enterprise", "public"]:
        scale_features = [
            "負荷分散機能", "パフォーマンス監視", "セキュリティ強化",
            "スケーリング対応", "冗長化システム"
        ]
        features.extend(scale_features)
    elif users == "small":
        # 小規模：シンプルな機能構成
        features = [f for f in features if not any(
            complex_term in f.lower() 
            for complex_term in ["高度", "複雑", "エンタープライズ"]
        )]
    
    # 基本機能を追加
    basic_features = ["認証機能", "管理画面", "API連携", "セキュリティ対策", "バックアップ機能"]
    features.extend(basic_features)
    
    return list(set(features))[:15]  # 重複除去・上限設定

def calculate_phases_enhanced(total_hours: int, category: str, duration: str, users: str) -> Dict[str, Dict[str, int]]:
    """カテゴリ別・要件別フェーズ工数計算"""
    # 基本的なカテゴリ別配分
    phase_ratios = {
        "EC・通販": {
            "要件定義・設計": 0.25,
            "開発": 0.45,
            "テスト": 0.20,
            "デザイン": 0.10
        },
        "業務システム": {
            "要件定義・設計": 0.30,
            "開発": 0.50,
            "テスト": 0.15,
            "デザイン": 0.05
        },
        "予約・管理": {
            "要件定義・設計": 0.20,
            "開発": 0.50,
            "テスト": 0.20,
            "デザイン": 0.10
        },
        "コーポレート": {
            "要件定義・設計": 0.15,
            "開発": 0.40,
            "テスト": 0.15,
            "デザイン": 0.30
        },
        "default": {
            "要件定義・設計": 0.20,
            "開発": 0.50,
            "テスト": 0.20,
            "デザイン": 0.10
        }
    }
    
    ratios = phase_ratios.get(category, phase_ratios["default"]).copy()
    
    # 開発期間による調整
    if duration == "1month":
        # 短期間：設計を圧縮、テストは必須
        ratios["要件定義・設計"] *= 0.7
        ratios["開発"] *= 1.1
        ratios["テスト"] *= 1.2
    elif duration in ["6-12months", "1year+"]:
        # 長期間：設計・テストを強化
        ratios["要件定義・設計"] *= 1.3
        ratios["テスト"] *= 1.4
        ratios["開発"] *= 0.9
    
    # ユーザー規模による調整
    if users in ["large", "enterprise", "public"]:
        # 大規模：設計・テスト重視
        ratios["要件定義・設計"] *= 1.4
        ratios["テスト"] *= 1.6
        ratios["開発"] *= 0.9
    elif users == "small":
        # 小規模：開発重視
        ratios["要件定義・設計"] *= 0.8
        ratios["開発"] *= 1.2
    
    # 合計が1.0になるよう正規化
    total_ratio = sum(ratios.values())
    for phase in ratios:
        ratios[phase] /= total_ratio
    
    phases = {}
    for phase, ratio in ratios.items():
        hours = int(total_hours * ratio)
        # 単価をフェーズ別に設定
        if phase == "デザイン":
            cost = hours * 6000
        elif phase == "要件定義・設計":
            cost = hours * 7000
        else:
            cost = hours * 5000
            
        phases[phase] = {
            "hours": hours,
            "cost": cost
        }
    
    return phases

# 起動時にデータを読み込み
@app.on_event("startup")
async def startup_event():
    """アプリ起動時の初期化"""
    logger.info("アプリケーション起動中...")
    load_sample_data()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """メインページ"""
    return FileResponse('static/index.html')

@app.post("/api/estimate", response_model=EstimationResult)
async def estimate_project_enhanced(request: ProjectRequest):
    """拡張版工数見積もりAPI"""
    try:
        logger.info(f"見積もり要求: {request.description}")
        
        # サンプルデータでの類似度計算
        similarities = []
        for sample in estimation_data:
            similarity = calculate_similarity_enhanced(request.description, sample)
            similarities.append({
                "data": sample,
                "similarity": similarity
            })
        
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        top_similar = similarities[:3]
        
        if top_similar[0]["similarity"] > 0:
            total_weight = sum(s["similarity"] for s in top_similar if s["similarity"] > 0)
            weighted_hours = sum(
                s["data"]["hours"] * s["similarity"] for s in top_similar if s["similarity"] > 0
            ) / total_weight if total_weight > 0 else 400
            
            weighted_cost = sum(
                s["data"]["cost"] * s["similarity"] for s in top_similar if s["similarity"] > 0
            ) / total_weight if total_weight > 0 else 2000000
            
            confidence = top_similar[0]["similarity"]
            data_source = "サンプルデータベース"
        else:
            weighted_hours = 400
            weighted_cost = 2000000
            confidence = 0.3
            data_source = "デフォルト見積もり"
        
        estimated_hours = int(weighted_hours)
        estimated_cost = int(weighted_cost)
        
        # 開発期間による調整
        adjusted_hours, duration_multiplier = calculate_duration_impact(request.duration, estimated_hours)
        
        # ユーザー規模による調整
        adjusted_cost, user_info = calculate_user_scale_impact(request.users, estimated_cost)
        
        # 最終的な工数・コスト
        final_hours = adjusted_hours
        final_cost = adjusted_cost
        
        # 必須項目を考慮した機能リストを推定
        features = estimate_features_with_requirements(request.description, request.duration, request.users)
        
        # ユーザー規模による追加機能
        features.extend(user_info["additional_features"][:3])  # 最大3つ追加
        features = list(set(features))[:15]  # 重複除去・制限
        
        # カテゴリ別・要件別フェーズ工数を計算
        estimated_category = request.category or "その他"
        phases = calculate_phases_enhanced(final_hours, estimated_category, request.duration, request.users)
        
        # 類似プロジェクト情報
        similar_projects = []
        for s in similarities[:3]:
            if s["similarity"] > 0:
                similar_projects.append({
                    "title": s["data"]["title"],
                    "description": s["data"]["description"],
                    "hours": str(s["data"]["hours"]),
                    "cost": f"{s['data']['cost']:,}円",
                    "similarity": f"{s['similarity']*100:.1f}%",
                    "company": s["data"]["company"]
                })
        
        result = EstimationResult(
            project_description=request.description,
            estimated_features=features,
            total_hours=final_hours,
            total_cost=final_cost,
            phases=phases,
            similar_projects=similar_projects,
            confidence_score=confidence * 0.9,  # 必須項目追加による信頼度調整
            data_source=f"{data_source} (期間:{request.duration}, 規模:{user_info['infrastructure']})"
        )
        
        logger.info(f"見積もり結果: {final_hours}時間, {final_cost:,}円 (期間調整:{duration_multiplier:.1f}x, 規模:{request.users})")
        return result
        
    except Exception as e:
        logger.error(f"見積もりエラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"見積もり処理でエラーが発生しました: {str(e)}")

@app.get("/api/data-status")
async def get_data_status():
    """データの状態を取得"""
    return {
        "total_projects": len(estimation_data),
        "last_update": last_update.isoformat() if last_update else None,
        "data_sources": {
            "sample_projects": len(estimation_data)
        }
    }

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {
        "status": "OK", 
        "timestamp": datetime.now().isoformat(),
        "data_loaded": len(estimation_data) > 0,
        "version": "2.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)