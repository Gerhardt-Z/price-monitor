"""
爬虫服务模块 - 负责从电商平台抓取商品价格

支持平台：
- 淘宝
- 京东
- 拼多多（待扩展）

注意：
1. 请遵守robots.txt和平台规则
2. 控制爬取频率，避免被封IP
3. 仅供学习和合法商业用途
"""

import re
import json
import time
import random
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ProductInfo:
    """商品信息数据类"""
    name: str
    price: float
    original_price: Optional[float] = None
    shop_name: Optional[str] = None
    image_url: Optional[str] = None
    platform: str = ""
    product_id: str = ""
    url: str = ""
    crawl_time: datetime = None
    
    def __post_init__(self):
        if self.crawl_time is None:
            self.crawl_time = datetime.utcnow()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "price": self.price,
            "original_price": self.original_price,
            "shop_name": self.shop_name,
            "image_url": self.image_url,
            "platform": self.platform,
            "product_id": self.product_id,
            "url": self.url,
            "crawl_time": self.crawl_time.isoformat(),
        }


class BaseScraper:
    """
    爬虫基类 - 提供通用功能
    """
    
    # 请求头池
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    
    def __init__(self, delay_range: tuple = (1, 3)):
        """
        初始化爬虫
        
        Args:
            delay_range: 请求间隔范围（秒），默认1-3秒
        """
        self.session = requests.Session()
        self.delay_range = delay_range
        self._update_headers()
    
    def _update_headers(self):
        """更新请求头"""
        self.session.headers.update({
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
    
    def _random_delay(self):
        """随机延时，避免被检测"""
        delay = random.uniform(*self.delay_range)
        logger.debug(f"延时 {delay:.2f} 秒")
        time.sleep(delay)
    
    def _get(self, url: str, **kwargs) -> requests.Response:
        """
        发送GET请求
        
        Args:
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            Response对象
            
        Raises:
            requests.RequestException: 请求失败
        """
        self._random_delay()
        self._update_headers()  # 每次请求更新UA
        
        try:
            response = self.session.get(url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"请求失败: {url} - {e}")
            raise
    
    def scrape(self, url: str) -> Optional[ProductInfo]:
        """
        抓取商品信息（子类实现）
        
        Args:
            url: 商品链接
            
        Returns:
            商品信息对象，失败返回None
        """
        raise NotImplementedError


class TaobaoScraper(BaseScraper):
    """
    淘宝爬虫
    
    注意：淘宝有较强的反爬机制，此示例仅供学习
    生产环境建议使用官方API或第三方数据服务
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 淘宝需要特殊Cookie，实际使用时需要配置
        self.cookies = {}
    
    def _extract_product_id(self, url: str) -> Optional[str]:
        """
        从URL提取商品ID
        
        支持格式：
        - https://item.taobao.com/item.htm?id=123456
        - https://detail.tmall.com/item.htm?id=123456
        
        Args:
            url: 商品链接
            
        Returns:
            商品ID，失败返回None
        """
        patterns = [
            r'id=(\d+)',
            r'/item/(\d+)\.html',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def _extract_price_from_html(self, html: str) -> Optional[float]:
        """
        从HTML提取价格
        
        Args:
            html: 页面HTML
            
        Returns:
            价格，失败返回None
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # 方法1: 从script标签中提取价格JSON
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and "price" in script.string.lower():
                try:
                    # 尝试提取价格数字
                    price_match = re.search(r'"price"\s*:\s*"?(\d+\.?\d*)"?', script.string)
                    if price_match:
                        return float(price_match.group(1))
                except (ValueError, AttributeError):
                    continue
        
        # 方法2: 从价格标签提取
        price_patterns = [
            r'(\d+\.?\d*)',
        ]
        price_elements = soup.find_all(class_=re.compile(r"price|Price", re.I))
        for elem in price_elements:
            text = elem.get_text()
            for pattern in price_patterns:
                match = re.search(pattern, text)
                if match:
                    try:
                        price = float(match.group(1))
                        if 0 < price < 1000000:  # 合理价格范围
                            return price
                    except ValueError:
                        continue
        
        return None
    
    def scrape(self, url: str) -> Optional[ProductInfo]:
        """
        抓取淘宝商品信息
        
        Args:
            url: 商品链接
            
        Returns:
            商品信息对象，失败返回None
        """
        product_id = self._extract_product_id(url)
        if not product_id:
            logger.error(f"无法提取商品ID: {url}")
            return None
        
        try:
            response = self._get(url)
            html = response.text
            
            # 提取价格
            price = self._extract_price_from_html(html)
            if price is None:
                logger.warning(f"无法提取价格: {url}")
                return None
            
            # 提取商品名称
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            name = title_tag.get_text().split("-")[0].strip() if title_tag else "未知商品"
            
            # 提取店铺名
            shop_name = None
            shop_elem = soup.find(class_=re.compile(r"shop|Shop", re.I))
            if shop_name:
                shop_name = shop_elem.get_text().strip()
            
            return ProductInfo(
                name=name,
                price=price,
                shop_name=shop_name,
                platform="taobao",
                product_id=product_id,
                url=url,
            )
            
        except Exception as e:
            logger.error(f"抓取失败: {url} - {e}")
            return None


class JDScraper(BaseScraper):
    """
    京东爬虫
    
    注意：京东有较强的反爬机制，此示例仅供学习
    """
    
    def _extract_product_id(self, url: str) -> Optional[str]:
        """
        从URL提取商品ID
        
        支持格式：
        - https://item.jd.com/123456.html
        - https://item.jd.com/1234567890.html
        
        Args:
            url: 商品链接
            
        Returns:
            商品ID，失败返回None
        """
        patterns = [
            r'item\.jd\.com/(\d+)',
            r'product/(\d+)\.html',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def _get_price_from_api(self, product_id: str) -> Optional[float]:
        """
        从京东价格API获取价格
        
        Args:
            product_id: 商品ID
            
        Returns:
            价格，失败返回None
        """
        api_url = f"https://p.3.cn/prices/mgets?skuIds=J_{product_id}"
        
        try:
            response = self._get(api_url)
            data = response.json()
            
            if data and len(data) > 0:
                price_str = data[0].get("p", data[0].get("op", ""))
                if price_str:
                    return float(price_str)
        except (json.JSONDecodeError, ValueError, IndexError) as e:
            logger.error(f"解析价格API失败: {e}")
        
        return None
    
    def scrape(self, url: str) -> Optional[ProductInfo]:
        """
        抓取京东商品信息
        
        Args:
            url: 商品链接
            
        Returns:
            商品信息对象，失败返回None
        """
        product_id = self._extract_product_id(url)
        if not product_id:
            logger.error(f"无法提取商品ID: {url}")
            return None
        
        try:
            # 获取价格
            price = self._get_price_from_api(product_id)
            if price is None:
                logger.warning(f"无法获取价格: {url}")
                return None
            
            # 获取商品页面信息
            response = self._get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 提取商品名称
            title_tag = soup.find("title")
            name = title_tag.get_text().split("-")[0].strip() if title_tag else "未知商品"
            
            # 提取店铺名
            shop_name = None
            shop_elem = soup.find(class_=re.compile(r"shop|Store", re.I))
            if shop_elem:
                shop_name = shop_elem.get_text().strip()
            
            return ProductInfo(
                name=name,
                price=price,
                shop_name=shop_name,
                platform="jd",
                product_id=product_id,
                url=url,
            )
            
        except Exception as e:
            logger.error(f"抓取失败: {url} - {e}")
            return None


class ScraperFactory:
    """
    爬虫工厂 - 根据URL自动选择对应的爬虫
    """
    
    _scrapers = {
        "taobao": TaobaoScraper,
        "tmall": TaobaoScraper,  # 天猫用淘宝爬虫
        "jd": JDScraper,
        # "pdd": PDDScraper,  # 拼多多待扩展
    }
    
    @classmethod
    def get_scraper(cls, url: str) -> Optional[BaseScraper]:
        """
        根据URL获取对应的爬虫实例
        
        Args:
            url: 商品链接
            
        Returns:
            爬虫实例，不支持的平台返回None
            
        Example:
            scraper = ScraperFactory.get_scraper("https://item.jd.com/123.html")
            info = scraper.scrape("https://item.jd.com/123.html")
        """
        platform = cls._detect_platform(url)
        if platform and platform in cls._scrapers:
            return cls._scrapers[platform]()
        return None
    
    @classmethod
    def _detect_platform(cls, url: str) -> Optional[str]:
        """
        检测URL对应的平台
        
        Args:
            url: 商品链接
            
        Returns:
            平台名称，无法识别返回None
        """
        url_lower = url.lower()
        
        if "taobao.com" in url_lower or "tmall.com" in url_lower:
            return "taobao" if "taobao.com" in url_lower else "tmall"
        elif "jd.com" in url_lower:
            return "jd"
        elif "pinduoduo.com" in url_lower or "pdd.com" in url_lower:
            return "pdd"
        
        return None
    
    @classmethod
    def scrape_product(cls, url: str) -> Optional[ProductInfo]:
        """
        一站式抓取商品信息
        
        Args:
            url: 商品链接
            
        Returns:
            商品信息对象，失败返回None
            
        Example:
            info = ScraperFactory.scrape_product("https://item.jd.com/123.html")
            if info:
                print(f"商品: {info.name}, 价格: {info.price}")
        """
        scraper = cls.get_scraper(url)
        if scraper:
            return scraper.scrape(url)
        
        logger.error(f"不支持的平台: {url}")
        return None


# 便捷函数
def scrape_product(url: str) -> Optional[ProductInfo]:
    """
    抓取商品信息的便捷函数
    
    Args:
        url: 商品链接
        
    Returns:
        商品信息对象，失败返回None
        
    Example:
        info = scrape_product("https://item.jd.com/123.html")
    """
    return ScraperFactory.scrape_product(url)


# 测试代码
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG)
    
    # 测试URL
    test_urls = [
        "https://item.jd.com/100012043978.html",  # 京东示例
    ]
    
    for url in test_urls:
        print(f"\n测试抓取: {url}")
        info = scrape_product(url)
        if info:
            print(f"✅ 成功: {info.name}")
            print(f"   价格: ¥{info.price}")
            print(f"   平台: {info.platform}")
        else:
            print("❌ 抓取失败")