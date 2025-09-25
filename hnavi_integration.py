#!/usr/bin/env python3
"""
発注ナビデータ統合モジュール
スクレイピングしたデータをAI見積もりツールに統合する
"""

import pandas as pd
import numpy as np
import re
from typing import List, Dict, Optional, Tuple
import logging
from dataclasses import dataclass
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProcessedProject:
    """処理済みプロジェクトデータ"""
    title: str
    description: str
    category: str
    min_price: float
    max_price: float
    avg_price: float
    estimated_hours: int
    technologies: List[str]
    services: List[str]
    company_name: str
    source_url: str
    confidence: float

class HnaviDataProcessor:
    """発注ナビデータ処理クラス"""
    
    def __init__(self, csv_file: str = 'hnavi_pricing_data.csv'):
        self.csv_file = csv_file
        self.processed_projects = []
        self.vectorizer = None
        self.project_vectors = None
        
    def load_and_process_data(self) -> List[ProcessedProject]:
        """CSVデータを読み込んで処理"""
        try:
            if not os.path.exists(self.csv_file):
                logger.warning(f"CSVファイル {self.csv_file} が見つかりません。サンプルデータを生成します。")
                return self._generate_sample_data()
            
            df = pd.read_csv(self.csv_file, encoding='utf-8-sig')
            logger.info(f"CSVファイルを読み込みました: {len(df)}行")
            
            processed_projects = []
            
            # 企業ごとにデータをグループ化
            for company_name, group in df.groupby('company_name'):
                logger.info(f"処理中: {company_name}")
                
                # 企業の基本情報を取得
                company_info = group.iloc[0]
                
                # サービス別にプロジェクトを生成
                services = self._parse_services(company_info.get('services', ''))
                technologies = self._parse_technologies(company_info.get('technologies', ''))
                
                # 料金情報を処理
                price_ranges = self._extract_price_ranges(group)
                
                # 各サービスタイプに対してプロジェクトを生成
                for service in services:
                    project = self._create_project_from_service(
                        service, company_info, price_ranges, technologies
                    )
                    if project:
                        processed_projects.append(project)
                
                # 価格別のプロジェクトも生成
                for price_info in price_ranges:
                    project = self._create_project_from_price(
                        price_info, company_info, services, technologies
                    )
                    if project:
                        processed_projects.append(project)
            
            # 重複を除去
            processed_projects = self._remove_duplicates(processed_projects)
            
            logger.info(f"処理完了: {len(processed_projects)}件のプロジェクトデータ")
            self.processed_projects = processed_projects
            
            # ベクトル化を準備
            self._prepare_vectorization()
            
            return processed_projects
            
        except Exception as e:
            logger.error(f"データ処理エラー: {str(e)}")
            return self._generate_sample_data()
    
    def _parse_services(self, services_str: str) -> List[str]:
        """サービス文字列を解析"""
        if pd.isna(services_str) or not services_str:
            return []
        
        services = []
        service_list = services_str.split(' | ')
        
        for service in service_list:
            service = service.strip()
            if service and len(service) > 2:
                services.append(service)
        
        return services[:10]  # 最大10個
    
    def _parse_technologies(self, tech_str: str) -> List[str]:
        """技術文字列を解析"""
        if pd.isna(tech_str) or not tech_str:
            return []
        
        technologies = []
        tech_list = tech_str.split(' | ')
        
        for tech in tech_list:
            tech = tech.strip()
            if tech and len(tech) > 1:
                technologies.append(tech)
        
        return technologies[:15]  # 最大15個
    
    def _extract_price_ranges(self, group: pd.DataFrame) -> List[Dict]:
        """料金範囲を抽出"""
        price_ranges = []
        
        for _, row in group.iterrows():
            if pd.notna(row.get('min_price')) or pd.notna(row.get('max_price')):
                try:
                    min_price = float(row.get('min_price', 0)) if pd.notna(row.get('min_price')) else 0
                    max_price = float(row.get('max_price', 0)) if pd.notna(row.get('max_price')) else 0
                    
                    if min_price > 0 or max_price > 0:
                        price_range = {
                            'min_price': min_price,
                            'max_price': max_price,
                            'unit': row.get('price_unit', '万円'),
                            'context': row.get('price_context', ''),
                            'type': row.get('price_type', '一括')
                        }
                        price_ranges.append(price_range)
                        
                except (ValueError, TypeError):
                    continue
        
        return price_ranges
    
    def _create_project_from_service(self, service: str, company_info: pd.Series, 
                                   price_ranges: List[Dict], technologies: List[str]) -> Optional[ProcessedProject]:
        """サービスからプロジェクトを生成"""
        try:
            # サービスに適した価格範囲を選択
            suitable_price = self._find_suitable_price_for_service(service, price_ranges)
            
            if not suitable_price:
                # デフォルト価格を設定
                suitable_price = self._get_default_price_for_service(service)
            
            min_price = suitable_price['min_price']
            max_price = suitable_price['max_price'] if suitable_price['max_price'] > 0 else min_price * 2
            avg_price = (min_price + max_price) / 2
            
            # 万円を円に変換
            if suitable_price.get('unit', '万円') == '万円':
                min_price *= 10000
                max_price *= 10000
                avg_price *= 10000
            
            # 工数を推定（1人日 = 5万円として計算）
            estimated_hours = int(avg_price / 50000 * 8)
            
            # カテゴリを推定
            category = self._estimate_category_from_service(service)
            
            # 説明文を生成
            description = self._generate_description(service, technologies, company_info)
            
            project = ProcessedProject(
                title=f"{service}開発",
                description=description,
                category=category,
                min_price=min_price,
                max_price=max_price,
                avg_price=avg_price,
                estimated_hours=estimated_hours,
                technologies=technologies,
                services=[service],
                company_name=company_info.get('company_name', ''),
                source_url=company_info.get('company_url', ''),
                confidence=0.8
            )
            
            return project
            
        except Exception as e:
            logger.warning(f"サービス {service} からのプロジェクト生成に失敗: {str(e)}")
            return None
    
    def _create_project_from_price(self, price_info: Dict, company_info: pd.Series,
                                 services: List[str], technologies: List[str]) -> Optional[ProcessedProject]:
        """価格情報からプロジェクトを生成"""
        try:
            context = price_info.get('context', '')
            
            if not context or len(context) < 5:
                return None
            
            min_price = price_info['min_price']
            max_price = price_info['max_price'] if price_info['max_price'] > 0 else min_price * 1.5
            avg_price = (min_price + max_price) / 2
            
            # 万円を円に変換
            if price_info.get('unit', '万円') == '万円':
                min_price *= 10000
                max_price *= 10000
                avg_price *= 10000
            
            # 工数を推定
            estimated_hours = int(avg_price / 50000 * 8)
            
            # コンテキストからタイトルとカテゴリを推定
            title = self._extract_title_from_context(context)
            category = self._estimate_category_from_context(context)
            
            # 説明文を生成
            description = self._generate_description_from_context(context, technologies, company_info)
            
            project = ProcessedProject(
                title=title,
                description=description,
                category=category,
                min_price=min_price,
                max_price=max_price,
                avg_price=avg_price,
                estimated_hours=estimated_hours,
                technologies=technologies,
                services=services,
                company_name=company_info.get('company_name', ''),
                source_url=company_info.get('company_url', ''),
                confidence=0.7
            )
            
            return project
            
        except Exception as e:
            logger.warning(f"価格情報からのプロジェクト生成に失敗: {str(e)}")
            return None
    
    def _find_suitable_price_for_service(self, service: str, price_ranges: List[Dict]) -> Optional[Dict]:
        """サービスに適した価格範囲を検索"""
        service_lower = service.lower()
        
        # コンテキストにサービス名が含まれる価格を探す
        for price_range in price_ranges:
            context = price_range.get('context', '').lower()
            if service_lower in context or any(keyword in context for keyword in service_lower.split()):
                return price_range
        
        # 見つからない場合は最初の価格を返す
        return price_ranges[0] if price_ranges else None
    
    def _get_default_price_for_service(self, service: str) -> Dict:
        """サービスのデフォルト価格を取得"""
        service_prices = {
            'ECサイト': {'min_price': 300, 'max_price': 800, 'unit': '万円'},
            'webアプリ': {'min_price': 200, 'max_price': 600, 'unit': '万円'},
            '業務システム': {'min_price': 250, 'max_price': 700, 'unit': '万円'},
            'CMS': {'min_price': 100, 'max_price': 400, 'unit': '万円'},
            'スマホアプリ': {'min_price': 150, 'max_price': 500, 'unit': '万円'},
            'コーポレートサイト': {'min_price': 50, 'max_price': 200, 'unit': '万円'},
        }
        
        for key, price in service_prices.items():
            if key.lower() in service.lower():
                return price
        
        # デフォルト
        return {'min_price': 200, 'max_price': 500, 'unit': '万円'}
    
    def _estimate_category_from_service(self, service: str) -> str:
        """サービスからカテゴリを推定"""
        service_lower = service.lower()
        
        category_mapping = {
            'ec': 'EC・通販',
            'ショッピング': 'EC・通販',
            '通販': 'EC・通販',
            '業務': '業務システム',
            'システム': '業務システム',
            '管理': '業務システム',
            'cms': 'CMS・メディア',
            'コーポレート': 'コーポレート',
            '企業': 'コーポレート',
            'スマホ': 'モバイルアプリ',
            'アプリ': 'モバイルアプリ',
            'web': 'Webアプリ',
        }
        
        for keyword, category in category_mapping.items():
            if keyword in service_lower:
                return category
        
        return 'その他'
    
    def _estimate_category_from_context(self, context: str) -> str:
        """コンテキストからカテゴリを推定"""
        return self._estimate_category_from_service(context)
    
    def _extract_title_from_context(self, context: str) -> str:
        """コンテキストからタイトルを抽出"""
        # 最初の意味のある部分を抽出
        context = re.sub(r'[\d,，]+(万円?|円)', '', context)  # 価格部分を除去
        context = re.sub(r'[～〜-]', '', context)  # 範囲記号を除去
        
        words = context.split()
        if words:
            return words[0][:20]  # 最大20文字
        
        return "システム開発"
    
    def _generate_description(self, service: str, technologies: List[str], company_info: pd.Series) -> str:
        """説明文を生成"""
        description_parts = []
        
        # サービスの説明
        description_parts.append(f"{service}の開発・構築")
        
        # 技術スタック
        if technologies:
            tech_str = '、'.join(technologies[:5])
            description_parts.append(f"使用技術: {tech_str}")
        
        # 企業の特徴
        company_desc = company_info.get('company_description', '')
        if company_desc and len(company_desc) > 10:
            description_parts.append(company_desc[:100])
        
        return '。'.join(description_parts)
    
    def _generate_description_from_context(self, context: str, technologies: List[str], company_info: pd.Series) -> str:
        """コンテキストから説明文を生成"""
        description_parts = []
        
        # コンテキストをクリーンアップ
        clean_context = re.sub(r'[\d,，]+(万円?|円)', '', context)
        clean_context = re.sub(r'[～〜-]', '', clean_context)
        
        if clean_context and len(clean_context) > 5:
            description_parts.append(clean_context[:100])
        
        # 技術スタック
        if technologies:
            tech_str = '、'.join(technologies[:3])
            description_parts.append(f"使用技術: {tech_str}")
        
        return '。'.join(description_parts) if description_parts else "システム開発プロジェクト"
    
    def _remove_duplicates(self, projects: List[ProcessedProject]) -> List[ProcessedProject]:
        """重複したプロジェクトを除去"""
        seen = set()
        unique_projects = []
        
        for project in projects:
            # タイトルと会社名で重複チェック
            key = f"{project.title}_{project.company_name}"
            if key not in seen:
                seen.add(key)
                unique_projects.append(project)
        
        return unique_projects
    
    def _prepare_vectorization(self):
        """テキストのベクトル化を準備"""
        if not self.processed_projects:
            return
        
        # プロジェクトの説明文を結合
        descriptions = []
        for project in self.processed_projects:
            text = f"{project.title} {project.description} {' '.join(project.services)} {' '.join(project.technologies)}"
            descriptions.append(text)
        
        # TF-IDFベクトライザーを作成
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None,  # 日本語のストップワードは別途設定が必要
            lowercase=True,
            ngram_range=(1, 2)
        )
        
        try:
            self.project_vectors = self.vectorizer.fit_transform(descriptions)
            logger.info(f"ベクトル化完了: {self.project_vectors.shape}")
        except Exception as e:
            logger.error(f"ベクトル化エラー: {str(e)}")
            self.vectorizer = None
            self.project_vectors = None
    
    def find_similar_projects(self, query: str, top_k: int = 5) -> List[Tuple[ProcessedProject, float]]:
        """類似プロジェクトを検索"""
        if not self.vectorizer or self.project_vectors is None:
            logger.warning("ベクトル化が準備されていません")
            return []
        
        try:
            # クエリをベクトル化
            query_vector = self.vectorizer.transform([query])
            
            # 類似度を計算
            similarities = cosine_similarity(query_vector, self.project_vectors).flatten()
            
            # 上位k件を取得
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # 最小類似度
                    results.append((self.processed_projects[idx], float(similarities[idx])))
            
            return results
            
        except Exception as e:
            logger.error(f"類似プロジェクト検索エラー: {str(e)}")
            return []
    
    def _generate_sample_data(self) -> List[ProcessedProject]:
        """サンプルデータを生成"""
        logger.info("サンプルプロジェクトデータを生成中...")
        
        sample_projects = [
            ProcessedProject(
                title="ECサイト構築",
                description="商品管理、在庫管理、決済システムを含むECサイト開発。レスポンシブ対応、管理画面付き。",
                category="EC・通販",
                min_price=3000000,
                max_price=8000000,
                avg_price=5500000,
                estimated_hours=880,
                technologies=["PHP", "Laravel", "MySQL", "AWS", "Stripe"],
                services=["ECサイト開発", "決済システム", "管理画面"],
                company_name="ECソリューション株式会社",
                source_url="https://hnavi.co.jp/company/ec-solution",
                confidence=0.9
            ),
            ProcessedProject(
                title="業務管理システム",
                description="販売管理、顧客管理、請求書発行機能を含む業務システム。データ分析機能付き。",
                category="業務システム",
                min_price=2500000,
                max_price=7000000,
                avg_price=4750000,
                estimated_hours=760,
                technologies=["Java", "Spring Boot", "PostgreSQL", "React"],
                services=["業務システム", "販売管理", "データ分析"],
                company_name="ビジネスシステムズ合同会社",
                source_url="https://hnavi.co.jp/company/business-systems",
                confidence=0.85
            ),
            ProcessedProject(
                title="予約管理システム",
                description="オンライン予約、カレンダー管理、通知機能を含む予約システム。モバイル対応。",
                category="予約・管理",
                min_price=1500000,
                max_price=4000000,
                avg_price=2750000,
                estimated_hours=440,
                technologies=["Python", "Django", "Vue.js", "Firebase"],
                services=["予約システム", "カレンダー管理", "通知機能"],
                company_name="リザーブテック株式会社",
                source_url="https://hnavi.co.jp/company/reserve-tech",
                confidence=0.8
            ),
            ProcessedProject(
                title="コーポレートサイト",
                description="会社紹介、ニュース管理、お問い合わせ機能付きの企業サイト。SEO対策済み。",
                category="コーポレート",
                min_price=500000,
                max_price=2000000,
                avg_price=1250000,
                estimated_hours=200,
                technologies=["WordPress", "PHP", "MySQL", "JavaScript"],
                services=["コーポレートサイト", "CMS", "SEO対策"],
                company_name="ウェブクリエイト株式会社",
                source_url="https://hnavi.co.jp/company/web-create",
                confidence=0.75
            ),
            ProcessedProject(
                title="モバイルアプリ開発",
                description="iOS・Android対応のネイティブアプリ開発。API連携、プッシュ通知機能付き。",
                category="モバイルアプリ",
                min_price=2000000,
                max_price=6000000,
                avg_price=4000000,
                estimated_hours=640,
                technologies=["Swift", "Kotlin", "React Native", "Firebase"],
                services=["モバイルアプリ", "API開発", "プッシュ通知"],
                company_name="モバイルデベロップ株式会社",
                source_url="https://hnavi.co.jp/company/mobile-develop",
                confidence=0.8
            )
        ]
        
        self.processed_projects = sample_projects
        self._prepare_vectorization()
        
        return sample_projects
    
    def save_processed_data(self, filename: str = 'processed_hnavi_data.pkl'):
        """処理済みデータを保存"""
        try:
            data = {
                'projects': self.processed_projects,
                'vectorizer': self.vectorizer,
                'project_vectors': self.project_vectors
            }
            
            with open(filename, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"処理済みデータを {filename} に保存しました")
            
        except Exception as e:
            logger.error(f"データ保存エラー: {str(e)}")
    
    def load_processed_data(self, filename: str = 'processed_hnavi_data.pkl') -> bool:
        """処理済みデータを読み込み"""
        try:
            if not os.path.exists(filename):
                return False
            
            with open(filename, 'rb') as f:
                data = pickle.load(f)
            
            self.processed_projects = data['projects']
            self.vectorizer = data['vectorizer']
            self.project_vectors = data['project_vectors']
            
            logger.info(f"処理済みデータを {filename} から読み込みました")
            return True
            
        except Exception as e:
            logger.error(f"データ読み込みエラー: {str(e)}")
            return False
    
    def export_for_estimation_api(self, filename: str = 'hnavi_estimation_data.json'):
        """見積もりAPI用のデータをエクスポート"""
        try:
            export_data = []
            
            for project in self.processed_projects:
                export_project = {
                    "title": project.title,
                    "description": project.description,
                    "category": project.category,
                    "hours": project.estimated_hours,
                    "cost": int(project.avg_price),
                    "features": project.services + project.technologies[:3],
                    "company": project.company_name,
                    "source": project.source_url,
                    "confidence": project.confidence
                }
                export_data.append(export_project)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"見積もりAPI用データを {filename} に出力しました")
            return filename
            
        except Exception as e:
            logger.error(f"データエクスポートエラー: {str(e)}")
            return None

def main():
    """メイン実行関数"""
    logger.info("発注ナビデータ統合処理開始")
    
    processor = HnaviDataProcessor()
    
    # 既存の処理済みデータがあれば読み込み
    if not processor.load_processed_data():
        # なければCSVから処理
        processed_projects = processor.load_and_process_data()
        processor.save_processed_data()
    
    # 見積もりAPI用データをエクスポート
    export_file = processor.export_for_estimation_api()
    
    # テスト検索
    if processor.processed_projects:
        logger.info("\n=== 類似プロジェクト検索テスト ===")
        test_queries = [
            "ECサイトを作りたい",
            "販売管理システムが欲しい", 
            "予約システムを構築したい"
        ]
        
        for query in test_queries:
            logger.info(f"\nクエリ: {query}")
            similar_projects = processor.find_similar_projects(query, top_k=3)
            
            for project, similarity in similar_projects:
                logger.info(f"  - {project.title} (類似度: {similarity:.3f}, 工数: {project.estimated_hours}h)")
    
    logger.info("発注ナビデータ統合処理完了")

if __name__ == '__main__':
    main()