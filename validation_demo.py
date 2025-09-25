#!/usr/bin/env python3
"""
必須項目（開発期間・想定ユーザー数）を含む見積もり精度向上デモ
"""

def demonstrate_estimation_differences():
    """必須項目有無による見積もり精度の差を示すデモ"""
    
    print("🎯 必須項目追加による見積もり精度向上デモ")
    print("="*60)
    
    # サンプルプロジェクト
    project_description = "美容室向けの予約管理システムを作りたい。顧客管理、スタッフスケジュール管理、売上レポート機能が必要"
    
    print(f"📝 プロジェクト概要: {project_description}")
    print()
    
    # 従来の見積もり（必須項目なし）
    print("【従来の見積もり】必須項目なし")
    print("-" * 40)
    basic_estimate = {
        "hours": 440,
        "cost": 2750000,
        "features": ["予約管理", "顧客管理", "カレンダー", "レポート機能", "認証機能"]
    }
    
    print(f"工数: {basic_estimate['hours']:,}時間")
    print(f"費用: {basic_estimate['cost']:,}円")
    print(f"機能: {', '.join(basic_estimate['features'][:3])}...")
    print("⚠️  曖昧な見積もり - 実際の要件が不明")
    print()
    
    # 新しい見積もりパターン
    scenarios = [
        {
            "name": "急ぎ案件（1ヶ月・小規模）",
            "duration": "1month",
            "users": "small",
            "multipliers": {"duration": 1.8, "users": 1.0},
            "additional_features": ["MVP機能限定"],
            "risk": "高"
        },
        {
            "name": "標準案件（3ヶ月・中規模）", 
            "duration": "3months",
            "users": "medium",
            "multipliers": {"duration": 1.1, "users": 1.3},
            "additional_features": ["ロードバランサー", "DB最適化"],
            "risk": "低"
        },
        {
            "name": "大規模案件（6ヶ月・企業規模）",
            "duration": "6-12months", 
            "users": "enterprise",
            "multipliers": {"duration": 1.2, "users": 2.5},
            "additional_features": ["マイクロサービス", "API Gateway", "セキュリティ強化"],
            "risk": "中"
        }
    ]
    
    for scenario in scenarios:
        print(f"【拡張版見積もり】{scenario['name']}")
        print("-" * 40)
        
        # 工数・コスト計算
        adjusted_hours = int(basic_estimate['hours'] * scenario['multipliers']['duration'])
        adjusted_cost = int(basic_estimate['cost'] * scenario['multipliers']['users'])
        
        # 機能リスト
        features = basic_estimate['features'].copy()
        features.extend(scenario['additional_features'])
        
        print(f"期間: {scenario['duration']} | 規模: {scenario['users']}")
        print(f"工数: {adjusted_hours:,}時間 (x{scenario['multipliers']['duration']})")
        print(f"費用: {adjusted_cost:,}円 (x{scenario['multipliers']['users']})")
        print(f"機能: {', '.join(features[:4])}...")
        print(f"リスク: {scenario['risk']} | 追加機能: {len(scenario['additional_features'])}個")
        
        # コスト差分
        cost_diff = adjusted_cost - basic_estimate['cost']
        cost_diff_percent = (cost_diff / basic_estimate['cost']) * 100
        
        if cost_diff > 0:
            print(f"💰 追加コスト: +{cost_diff:,}円 (+{cost_diff_percent:.1f}%)")
        else:
            print(f"💰 コスト削減: {cost_diff:,}円 ({cost_diff_percent:.1f}%)")
        
        print()
    
    # 精度向上のメリット
    print("🎯 必須項目導入のメリット")
    print("="*40)
    benefits = [
        "見積もり精度の向上（±10% → ±5%）",
        "開発リスクの事前把握", 
        "適切な技術選定",
        "プロジェクト成功率の向上",
        "顧客満足度の向上"
    ]
    
    for i, benefit in enumerate(benefits, 1):
        print(f"{i}. {benefit}")
    
    print("\n" + "="*60)
    print("✅ 必須項目により、より現実的で精度の高い見積もりが可能に！")

def show_feature_customization_examples():
    """機能カスタマイズの例を表示"""
    print("\n🔧 ユーザー規模別機能カスタマイズ例")
    print("="*50)
    
    base_features = ["予約管理", "顧客管理", "認証機能", "管理画面"]
    
    customizations = {
        "small": {
            "name": "小規模（～100人）",
            "add": ["簡易レポート", "基本通知"],
            "remove": [],
            "description": "シンプルで使いやすい構成"
        },
        "medium": {
            "name": "中規模（100～1,000人）",
            "add": ["ロードバランサー", "DB最適化", "詳細レポート", "API連携"],
            "remove": [],
            "description": "パフォーマンス最適化済み"
        },
        "enterprise": {
            "name": "企業規模（10,000人以上）",
            "add": ["マイクロサービス", "冗長化", "監視システム", "セキュリティ強化", "自動スケーリング"],
            "remove": [],
            "description": "エンタープライズ級の高可用性"
        }
    }
    
    for scale, config in customizations.items():
        features = base_features.copy()
        features.extend(config["add"])
        
        print(f"\n【{config['name']}】")
        print(f"特徴: {config['description']}")
        print(f"機能数: {len(features)}個")
        print(f"機能例: {', '.join(features[:6])}")
        if len(features) > 6:
            print(f"         その他{len(features)-6}個...")

if __name__ == "__main__":
    demonstrate_estimation_differences()
    show_feature_customization_examples()