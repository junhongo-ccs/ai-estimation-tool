#!/usr/bin/env python3
"""
発注ナビ（hnavi.co.jp）専用スクレイピングPoC
「開発費用・料金の目安」セクションを中心にデータを収集
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin, urlparse, parse_qs
import logging
from typing import List, Dict, Optional, Tuple
import json
from dataclasses import dataclass
import random

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CompanyPricing:
    """企業の料金情報を格納するデータクラス"""
    company_name: str
    company_url: str
    pricing_section: str
    services: List[str]
    price_ranges: List[Dict[str, str]]
    development_types: List[str]
    technologies: List[str]
    company_description: str
    location: str
    established: str
    employees: str

class HnaviScraper:
    """発注ナビ専用スクレイピングクラス"""
    
    def __init__(self, delay_range: Tuple[float, float] = (1.0, 3.0)):
        self.base_url = "https://hnavi.co.jp"
        self.delay_range = delay_range
        self.session = requests.Session()
        
        # ユーザーエージェントをランダムに選択
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
        ]
        
        self.session.headers.update({
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def random_delay(self):
        """ランダムな待機時間"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
        
    def fetch_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """ページを取得してBeautifulSoupオブジェクトを返す"""
        for attempt in range(retries):
            try:
                logger.info(f"Fetching: {url} (attempt {attempt + 1})")
                
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                # 文字化け対策
                if response.apparent_encoding:
                    response.encoding = response.apparent_encoding
                else:
                    response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                self.random_delay()
                
                return soup
                
            except requests.RequestException as e:
                logger.warning(f"Error fetching {url} (attempt {attempt + 1}): {str(e)}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # 指数バックオフ
                else:
                    logger.error(f"Failed to fetch {url} after {retries} attempts")
                    return None
        
        return None
    
    def search_companies(self, keywords: List[str], max_pages: int = 5) -> List[str]:
        """キーワードで企業を検索し、企業ページのURLリストを返す"""
        company_urls = []
        
        for keyword in keywords:
            logger.info(f"Searching for: {keyword}")
            
            # 検索ページのURL構築
            search_url = f"{self.base_url}/search"
            
            # 検索パラメータ
            search_params = {
                'q': keyword,
                'category': 'development',  # 開発カテゴリ
                'page': 1
            }
            
            for page in range(1, max_pages + 1):
                search_params['page'] = page
                
                try:
                    response = self.session.get(search_url, params=search_params, timeout=30)
                    if response.status_code != 200:
                        logger.warning(f"Search failed for {keyword}, page {page}: {response.status_code}")
                        continue
                        
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 企業リンクを抽出（発注ナビの構造に合わせて調整）
                    company_links = self._extract_company_links(soup)
                    
                    if not company_links:
                        logger.info(f"No more results for {keyword} at page {page}")
                        break
                    
                    company_urls.extend(company_links)
                    logger.info(f"Found {len(company_links)} companies on page {page} for {keyword}")
                    
                    self.random_delay()
                    
                except Exception as e:
                    logger.error(f"Error searching {keyword} page {page}: {str(e)}")
                    continue
        
        # 重複を除去
        unique_urls = list(set(company_urls))
        logger.info(f"Total unique company URLs found: {len(unique_urls)}")
        
        return unique_urls
    
    def _extract_company_links(self, soup: BeautifulSoup) -> List[str]:
        """検索結果ページから企業ページのURLを抽出"""
        company_links = []
        
        # 発注ナビの検索結果構造に合わせたセレクタ
        # （実際のサイト構造に応じて調整が必要）
        link_selectors = [
            'a[href*="/company/"]',           # 企業ページへのリンク
            'a[href*="/profile/"]',           # プロフィールページ
            '.company-link a',                # 企業リンククラス
            '.search-result-item a',          # 検索結果アイテム
            'h3 a, h4 a',                    # 見出し内のリンク
        ]
        
        for selector in link_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    # 相対URLを絶対URLに変換
                    full_url = urljoin(self.base_url, href)
                    
                    # 企業ページのURLパターンをチェック
                    if self._is_company_page(full_url):
                        company_links.append(full_url)
        
        return company_links
    
    def _is_company_page(self, url: str) -> bool:
        """URLが企業ページかどうかを判定"""
        company_patterns = [
            r'/company/\d+',
            r'/profile/\d+',
            r'/company/[a-zA-Z0-9-]+',
            r'/dev-company/',
        ]
        
        for pattern in company_patterns:
            if re.search(pattern, url):
                return True
        
        return False
    
    def scrape_company_pricing(self, company_url: str) -> Optional[CompanyPricing]:
        """企業ページから料金情報を抽出"""
        soup = self.fetch_page(company_url)
        if not soup:
            return None
        
        try:
            # 企業名を取得
            company_name = self._extract_company_name(soup)
            
            # 料金セクションを特定
            pricing_section = self._extract_pricing_section(soup)
            
            # サービス情報を抽出
            services = self._extract_services(soup)
            
            # 料金情報を抽出
            price_ranges = self._extract_price_ranges(soup, pricing_section)
            
            # 開発タイプを抽出
            development_types = self._extract_development_types(soup)
            
            # 技術スタックを抽出
            technologies = self._extract_technologies(soup)
            
            # 企業情報を抽出
            company_info = self._extract_company_info(soup)
            
            return CompanyPricing(
                company_name=company_name,
                company_url=company_url,
                pricing_section=pricing_section,
                services=services,
                price_ranges=price_ranges,
                development_types=development_types,
                technologies=technologies,
                company_description=company_info.get('description', ''),
                location=company_info.get('location', ''),
                established=company_info.get('established', ''),
                employees=company_info.get('employees', '')
            )
            
        except Exception as e:
            logger.error(f"Error scraping company pricing from {company_url}: {str(e)}")
            return None
    
    def _extract_company_name(self, soup: BeautifulSoup) -> str:
        """企業名を抽出"""
        name_selectors = [
            'h1',
            '.company-name',
            '.profile-name',
            'title',
            '.main-title'
        ]
        
        for selector in name_selectors:
            element = soup.select_one(selector)
            if element:
                name = element.get_text(strip=True)
                # 「発注ナビ」などの不要な文字列を除去
                name = re.sub(r'[\s\-\|]*発注ナビ.*$', '', name)
                name = re.sub(r'[\s\-\|]*hnavi.*$', '', name, flags=re.IGNORECASE)
                if name and len(name) > 2:
                    return name
        
        return "企業名不明"
    
    def _extract_pricing_section(self, soup: BeautifulSoup) -> str:
        """料金セクションのテキストを抽出"""
        pricing_keywords = [
            '開発費用',
            '料金の目安',
            '価格帯',
            '費用目安',
            'コスト',
            '料金',
            '価格',
            'pricing',
            'cost'
        ]
        
        pricing_text = ""
        
        # セクション見出しから料金関連を探す
        for keyword in pricing_keywords:
            # 見出しを探す
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'], 
                                   string=re.compile(keyword, re.IGNORECASE))
            
            for heading in headings:
                # 見出しの次の要素やコンテンツを取得
                next_elements = []
                current = heading.parent
                
                # 同じレベルの見出しまでの要素を取得
                while current and current.next_sibling:
                    sibling = current.next_sibling
                    if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        break
                    if hasattr(sibling, 'get_text'):
                        text = sibling.get_text(strip=True)
                        if text and len(text) > 10:
                            next_elements.append(text)
                    current = sibling
                
                if next_elements:
                    pricing_text += f"\n{keyword}セクション:\n" + "\n".join(next_elements[:3])
        
        # 料金テーブルや価格リストも探す
        price_tables = soup.find_all(['table', 'ul', 'dl'], 
                                   class_=re.compile(r'price|cost|fee|料金', re.IGNORECASE))
        
        for table in price_tables:
            table_text = table.get_text(strip=True)
            if len(table_text) > 20 and len(table_text) < 1000:
                pricing_text += f"\n料金テーブル:\n{table_text}\n"
        
        return pricing_text[:2000]  # テキスト量を制限
    
    def _extract_services(self, soup: BeautifulSoup) -> List[str]:
        """サービス一覧を抽出"""
        services = []
        
        service_keywords = [
            'webアプリ', 'モバイルアプリ', 'ECサイト', 'CMS', 
            'システム開発', '業務システム', 'API開発',
            'wordpress', 'react', 'vue.js', 'laravel'
        ]
        
        text = soup.get_text().lower()
        
        for keyword in service_keywords:
            if keyword.lower() in text:
                services.append(keyword)
        
        # サービス一覧のセクションからも抽出
        service_sections = soup.find_all(['ul', 'ol', 'div'], 
                                       class_=re.compile(r'service|skill|tech', re.IGNORECASE))
        
        for section in service_sections:
            items = section.find_all(['li', 'span', 'div'])
            for item in items[:10]:  # 最大10項目
                service_text = item.get_text(strip=True)
                if 5 < len(service_text) < 50:
                    services.append(service_text)
        
        return list(set(services))[:15]  # 重複を除去し、最大15項目
    
    def _extract_price_ranges(self, soup: BeautifulSoup, pricing_section: str) -> List[Dict[str, str]]:
        """料金範囲を抽出"""
        price_ranges = []
        
        # 価格パターンの正規表現
        price_patterns = [
            r'(\d+(?:,\d{3})*)\s*[～〜-]\s*(\d+(?:,\d{3})*)\s*万円',
            r'(\d+(?:,\d{3})*)\s*万円\s*[～〜-]\s*(\d+(?:,\d{3})*)\s*万円',
            r'(\d+(?:,\d{3})*)\s*[～〜-]\s*(\d+(?:,\d{3})*)\s*円',
            r'月額\s*(\d+(?:,\d{3})*)\s*[～〜-]\s*(\d+(?:,\d{3})*)\s*円',
            r'(\d+)\s*万円?台',
        ]
        
        # pricing_sectionから価格を抽出
        full_text = pricing_section + " " + soup.get_text()
        
        for pattern in price_patterns:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) >= 2:
                    price_range = {
                        'min_price': match.group(1).replace(',', ''),
                        'max_price': match.group(2).replace(',', ''),
                        'unit': '万円' if '万円' in match.group(0) else '円',
                        'type': '月額' if '月額' in match.group(0) else '一括',
                        'context': match.group(0)
                    }
                    price_ranges.append(price_range)
        
        return price_ranges[:10]  # 最大10項目
    
    def _extract_development_types(self, soup: BeautifulSoup) -> List[str]:
        """開発タイプを抽出"""
        dev_types = []
        
        type_keywords = [
            'ECサイト', 'コーポレートサイト', 'ランディングページ',
            '業務システム', '販売管理', '在庫管理', '顧客管理',
            'スマホアプリ', 'webアプリ', 'API', 'CMS'
        ]
        
        text = soup.get_text()
        
        for keyword in type_keywords:
            if keyword in text:
                dev_types.append(keyword)
        
        return dev_types
    
    def _extract_technologies(self, soup: BeautifulSoup) -> List[str]:
        """技術スタックを抽出"""
        technologies = []
        
        tech_keywords = [
            'PHP', 'Laravel', 'WordPress', 'Python', 'Django',
            'JavaScript', 'React', 'Vue.js', 'Node.js',
            'Java', 'Spring', 'Ruby', 'Rails',
            'MySQL', 'PostgreSQL', 'MongoDB',
            'AWS', 'Azure', 'GCP', 'Docker'
        ]
        
        text = soup.get_text()
        
        for keyword in tech_keywords:
            if re.search(rf'\b{re.escape(keyword)}\b', text, re.IGNORECASE):
                technologies.append(keyword)
        
        return technologies
    
    def _extract_company_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """企業情報を抽出"""
        info = {}
        
        # 説明文を抽出
        desc_selectors = [
            '.company-description',
            '.profile-description', 
            '.about',
            'meta[name="description"]'
        ]
        
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    info['description'] = element.get('content', '')
                else:
                    info['description'] = element.get_text(strip=True)
                break
        
        # 所在地を抽出
        location_patterns = [
            r'所在地[:\s]*([^\n]+)',
            r'住所[:\s]*([^\n]+)',
            r'Location[:\s]*([^\n]+)',
        ]
        
        text = soup.get_text()
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                info['location'] = match.group(1).strip()
                break
        
        return info

def run_hnavi_scraping_poc():
    """発注ナビスクレイピングPoCの実行"""
    logger.info("発注ナビスクレイピングPoC開始")
    
    scraper = HnaviScraper()
    
    # 検索キーワード
    keywords = [
        "ECサイト開発",
        "webアプリ開発", 
        "業務システム",
        "CMS構築",
        "Laravel開発"
    ]
    
    try:
        # 1. 企業検索
        logger.info("企業検索を開始...")
        company_urls = scraper.search_companies(keywords, max_pages=3)
        
        if not company_urls:
            logger.warning("企業URLが見つかりませんでした。サンプルデータを生成します。")
            company_urls = generate_sample_company_urls()
        
        # 2. 各企業の料金情報を収集
        pricing_data = []
        max_companies = min(20, len(company_urls))  # 最大20社
        
        logger.info(f"{max_companies}社の料金情報を収集開始...")
        
        for i, url in enumerate(company_urls[:max_companies], 1):
            logger.info(f"処理中: {i}/{max_companies} - {url}")
            
            pricing = scraper.scrape_company_pricing(url)
            if pricing:
                pricing_data.append(pricing)
                logger.info(f"取得成功: {pricing.company_name}")
            else:
                logger.warning(f"取得失敗: {url}")
        
        # 3. 結果をCSVに保存
        save_pricing_data_to_csv(pricing_data)
        
        # 4. 結果統計を表示
        display_statistics(pricing_data)
        
    except Exception as e:
        logger.error(f"スクレイピング中にエラーが発生: {str(e)}")
        # エラーの場合はサンプルデータを生成
        pricing_data = generate_sample_pricing_data()
        save_pricing_data_to_csv(pricing_data)

def generate_sample_company_urls() -> List[str]:
    """サンプル企業URLを生成"""
    return [
        "https://hnavi.co.jp/company/sample1",
        "https://hnavi.co.jp/company/sample2", 
        "https://hnavi.co.jp/company/sample3",
        "https://hnavi.co.jp/company/sample4",
        "https://hnavi.co.jp/company/sample5"
    ]

def generate_sample_pricing_data() -> List[CompanyPricing]:
    """サンプル料金データを生成"""
    return [
        CompanyPricing(
            company_name="サンプル開発株式会社",
            company_url="https://hnavi.co.jp/company/sample1",
            pricing_section="ECサイト開発: 300万円～800万円\n業務システム: 200万円～500万円",
            services=["ECサイト開発", "業務システム", "CMS構築"],
            price_ranges=[
                {"min_price": "300", "max_price": "800", "unit": "万円", "type": "一括", "context": "ECサイト開発"}
            ],
            development_types=["ECサイト", "業務システム"],
            technologies=["PHP", "Laravel", "MySQL", "AWS"],
            company_description="中小企業向けのシステム開発を得意とする会社",
            location="東京都渋谷区",
            established="2015年",
            employees="50名"
        ),
        CompanyPricing(
            company_name="テックソリューション合同会社",
            company_url="https://hnavi.co.jp/company/sample2",
            pricing_section="Webアプリ開発: 100万円～400万円\nスマホアプリ: 150万円～600万円",
            services=["Webアプリ開発", "スマホアプリ", "API開発"],
            price_ranges=[
                {"min_price": "100", "max_price": "400", "unit": "万円", "type": "一括", "context": "Webアプリ開発"}
            ],
            development_types=["Webアプリ", "スマホアプリ"],
            technologies=["React", "Node.js", "MongoDB", "Docker"],
            company_description="モダンな技術スタックでの開発が強み",
            location="大阪府大阪市",
            established="2018年",
            employees="30名"
        )
    ]

def save_pricing_data_to_csv(pricing_data: List[CompanyPricing], filename: str = 'hnavi_pricing_data.csv'):
    """料金データをCSVファイルに保存"""
    if not pricing_data:
        logger.warning("保存する料金データがありません")
        return
    
    # データフレーム用のリストを作成
    csv_data = []
    
    for pricing in pricing_data:
        base_row = {
            'company_name': pricing.company_name,
            'company_url': pricing.company_url,
            'pricing_section': pricing.pricing_section,
            'services': ' | '.join(pricing.services),
            'development_types': ' | '.join(pricing.development_types),
            'technologies': ' | '.join(pricing.technologies),
            'company_description': pricing.company_description,
            'location': pricing.location,
            'established': pricing.established,
            'employees': pricing.employees
        }
        
        # 料金情報を展開
        if pricing.price_ranges:
            for price_range in pricing.price_ranges:
                row = base_row.copy()
                row.update({
                    'min_price': price_range.get('min_price', ''),
                    'max_price': price_range.get('max_price', ''),
                    'price_unit': price_range.get('unit', ''),
                    'price_type': price_range.get('type', ''),
                    'price_context': price_range.get('context', '')
                })
                csv_data.append(row)
        else:
            csv_data.append(base_row)
    
    # CSVファイルに保存
    df = pd.DataFrame(csv_data)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    logger.info(f"料金データを {filename} に保存しました ({len(csv_data)}行)")

def display_statistics(pricing_data: List[CompanyPricing]):
    """収集した料金データの統計を表示"""
    if not pricing_data:
        logger.warning("統計表示する料金データがありません")
        return
    
    logger.info("=== 収集結果統計 ===")
    logger.info(f"収集企業数: {len(pricing_data)}")
    
    # サービス統計
    all_services = []
    for pricing in pricing_data:
        all_services.extend(pricing.services)
    
    if all_services:
        service_counts = pd.Series(all_services).value_counts()
        logger.info("上位サービス:")
        for service, count in service_counts.head(5).items():
            logger.info(f"  {service}: {count}社")
    
    # 技術統計
    all_technologies = []
    for pricing in pricing_data:
        all_technologies.extend(pricing.technologies)
    
    if all_technologies:
        tech_counts = pd.Series(all_technologies).value_counts()
        logger.info("上位技術:")
        for tech, count in tech_counts.head(5).items():
            logger.info(f"  {tech}: {count}社")
    
    # 料金統計
    price_data = []
    for pricing in pricing_data:
        for price_range in pricing.price_ranges:
            try:
                min_price = float(price_range.get('min_price', 0))
                max_price = float(price_range.get('max_price', 0))
                if min_price > 0:
                    price_data.append(min_price)
                if max_price > 0:
                    price_data.append(max_price)
            except (ValueError, TypeError):
                continue
    
    if price_data:
        price_series = pd.Series(price_data)
        logger.info("料金統計（万円）:")
        logger.info(f"  平均: {price_series.mean():.1f}万円")
        logger.info(f"  中央値: {price_series.median():.1f}万円")
        logger.info(f"  最小: {price_series.min():.1f}万円")
        logger.info(f"  最大: {price_series.max():.1f}万円")

if __name__ == '__main__':
    run_hnavi_scraping_poc()