#!/usr/bin/env python3
"""
発注ナビスクレイピングPoC実行スクリプト
使用方法:
  python run_hnavi_poc.py --keywords "ECサイト開発" "webアプリ開発" --max-pages 2 --max-companies 10
"""

import argparse
import asyncio
import logging
from hnavi_scraper import run_hnavi_scraping_poc, HnaviScraper
from hnavi_integration import HnaviDataProcessor

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='発注ナビスクレイピングPoC実行')
    parser.add_argument('--keywords', nargs='+', 
                       default=["ECサイト開発", "webアプリ開発", "業務システム", "CMS構築"],
                       help='検索キーワード（複数指定可能）')
    parser.add_argument('--max-pages', type=int, default=3,
                       help='各キーワードの最大検索ページ数')
    parser.add_argument('--max-companies', type=int, default=20,
                       help='データ収集する最大企業数')
    parser.add_argument('--output-csv', default='hnavi_pricing_data.csv',
                       help='出力CSVファイル名')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='リクエスト間の待機時間（秒）')
    parser.add_argument('--test-mode', action='store_true',
                       help='テストモード（サンプルデータのみ生成）')
    
    args = parser.parse_args()
    
    logger.info("=== 発注ナビスクレイピングPoC開始 ===")
    logger.info(f"検索キーワード: {args.keywords}")
    logger.info(f"最大ページ数: {args.max_pages}")
    logger.info(f"最大企業数: {args.max_companies}")
    logger.info(f"出力ファイル: {args.output_csv}")
    
    try:
        if args.test_mode:
            logger.info("テストモードで実行します（実際のスクレイピングは行いません）")
            run_test_mode(args)
        else:
            run_full_scraping(args)
            
        logger.info("=== 発注ナビスクレイピングPoC完了 ===")
        
    except KeyboardInterrupt:
        logger.info("ユーザーによって中断されました")
    except Exception as e:
        logger.error(f"実行中にエラーが発生しました: {str(e)}")
        raise

def run_test_mode(args):
    """テストモード実行"""
    from hnavi_scraper import generate_sample_pricing_data, save_pricing_data_to_csv, display_statistics
    
    logger.info("サンプルデータを生成中...")
    
    # サンプルデータ生成
    pricing_data = generate_sample_pricing_data()
    
    # 追加のサンプルデータを生成
    additional_samples = [
        {
            "company_name": "システム開発株式会社Alpha",
            "company_url": "https://hnavi.co.jp/company/alpha-systems",
            "pricing_section": "Webアプリ開発: 200万円～600万円\nスマホアプリ: 300万円～800万円",
            "services": ["Webアプリ開発", "スマホアプリ", "システム開発"],
            "price_ranges": [
                {"min_price": "200", "max_price": "600", "unit": "万円", "type": "一括", "context": "Webアプリ開発"}
            ],
            "development_types": ["Webアプリ", "スマホアプリ"],
            "technologies": ["React", "Vue.js", "Python", "Django", "AWS"],
            "company_description": "最新技術を使った高品質なシステム開発",
            "location": "東京都新宿区",
            "established": "2012年",
            "employees": "80名"
        },
        {
            "company_name": "クラウドソリューションズ合同会社",
            "company_url": "https://hnavi.co.jp/company/cloud-solutions",
            "pricing_section": "業務システム: 300万円～1000万円\nクラウド移行: 150万円～500万円",
            "services": ["業務システム", "クラウド移行", "インフラ構築"],
            "price_ranges": [
                {"min_price": "300", "max_price": "1000", "unit": "万円", "type": "一括", "context": "業務システム"}
            ],
            "development_types": ["業務システム", "クラウドシステム"],
            "technologies": ["AWS", "Azure", "Docker", "Kubernetes", "Java"],
            "company_description": "クラウドインフラに特化したシステム開発会社",
            "location": "大阪府大阪市",
            "established": "2016年",
            "employees": "45名"
        }
    ]
    
    # CompanyPricingオブジェクトに変換
    from hnavi_scraper import CompanyPricing
    for sample in additional_samples:
        pricing = CompanyPricing(
            company_name=sample["company_name"],
            company_url=sample["company_url"],
            pricing_section=sample["pricing_section"],
            services=sample["services"],
            price_ranges=sample["price_ranges"],
            development_types=sample["development_types"],
            technologies=sample["technologies"],
            company_description=sample["company_description"],
            location=sample["location"],
            established=sample["established"],
            employees=sample["employees"]
        )
        pricing_data.append(pricing)
    
    # CSVに保存
    save_pricing_data_to_csv(pricing_data, args.output_csv)
    
    # 統計表示
    display_statistics(pricing_data)
    
    # データ統合処理も実行
    run_integration_process(args.output_csv)

def run_full_scraping(args):
    """フルスクレイピング実行"""
    scraper = HnaviScraper(delay_range=(args.delay, args.delay + 1.0))
    
    try:
        # 1. 企業検索
        logger.info("企業検索を開始...")
        company_urls = scraper.search_companies(args.keywords, max_pages=args.max_pages)
        
        if not company_urls:
            logger.warning("企業URLが見つかりませんでした。サンプルデータを使用します。")
            run_test_mode(args)
            return
        
        logger.info(f"検索結果: {len(company_urls)}社の企業URL")
        
        # 2. 料金情報収集
        pricing_data = []
        max_companies = min(args.max_companies, len(company_urls))
        
        logger.info(f"{max_companies}社の料金情報を収集開始...")
        
        for i, url in enumerate(company_urls[:max_companies], 1):
            logger.info(f"処理中: {i}/{max_companies} - {url}")
            
            try:
                pricing = scraper.scrape_company_pricing(url)
                if pricing:
                    pricing_data.append(pricing)
                    logger.info(f"取得成功: {pricing.company_name}")
                else:
                    logger.warning(f"取得失敗: {url}")
                    
            except Exception as e:
                logger.error(f"企業データ取得エラー {url}: {str(e)}")
                continue
        
        if not pricing_data:
            logger.warning("料金データが取得できませんでした。サンプルデータを使用します。")
            run_test_mode(args)
            return
        
        # 3. CSVに保存
        from hnavi_scraper import save_pricing_data_to_csv, display_statistics
        save_pricing_data_to_csv(pricing_data, args.output_csv)
        
        # 4. 統計表示
        display_statistics(pricing_data)
        
        # 5. データ統合処理
        run_integration_process(args.output_csv)
        
    except Exception as e:
        logger.error(f"スクレイピング処理エラー: {str(e)}")
        logger.info("エラー発生のため、サンプルデータで継続します")
        run_test_mode(args)

def run_integration_process(csv_file: str):
    """データ統合処理を実行"""
    try:
        logger.info("データ統合処理を開始...")
        
        processor = HnaviDataProcessor(csv_file)
        processed_projects = processor.load_and_process_data()
        
        if processed_projects:
            # 処理済みデータを保存
            processor.save_processed_data()
            
            # 見積もりAPI用データをエクスポート
            export_file = processor.export_for_estimation_api()
            
            logger.info(f"データ統合完了: {len(processed_projects)}件のプロジェクト")
            if export_file:
                logger.info(f"見積もりAPI用データ: {export_file}")
            
            # 類似検索のテスト
            test_similarity_search(processor)
        else:
            logger.warning("統合するデータがありませんでした")
            
    except Exception as e:
        logger.error(f"データ統合エラー: {str(e)}")

def test_similarity_search(processor: HnaviDataProcessor):
    """類似検索のテスト"""
    test_queries = [
        "ECサイトを作りたい。商品管理と決済機能が必要",
        "美容室向けの予約システムが欲しい",
        "在庫管理システムを構築したい",
        "会社のホームページをリニューアルしたい",
        "スマホアプリを開発したい。iOS・Android対応"
    ]
    
    logger.info("\n=== 類似プロジェクト検索テスト ===")
    
    for query in test_queries:
        logger.info(f"\nクエリ: {query}")
        similar_projects = processor.find_similar_projects(query, top_k=3)
        
        if similar_projects:
            for project, similarity in similar_projects:
                logger.info(f"  - {project.title}")
                logger.info(f"    類似度: {similarity:.3f} | 工数: {project.estimated_hours}h | 費用: {int(project.avg_price):,}円")
                logger.info(f"    企業: {project.company_name}")
        else:
            logger.info("  類似プロジェクトが見つかりませんでした")

if __name__ == '__main__':
    main()