"""
价格分析模块 - 分析价格趋势、计算统计数据

功能：
- 价格趋势分析
- 统计数据计算（最高价、最低价、平均价、波动率）
- 异常价格检测
- 价格预测（简单移动平均）
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from statistics import mean, stdev

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from models.product import Product
from models.price_record import PriceRecord

logger = logging.getLogger(__name__)


@dataclass
class PriceStats:
    """价格统计数据"""
    product_id: int
    product_name: str
    current_price: float
    min_price: float
    max_price: float
    avg_price: float
    price_std: float  # 标准差
    price_change: float  # 价格变动
    price_change_percent: float  # 价格变动百分比
    record_count: int
    first_record_time: datetime
    last_record_time: datetime
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "current_price": self.current_price,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "avg_price": self.avg_price,
            "price_std": round(self.price_std, 2),
            "price_change": round(self.price_change, 2),
            "price_change_percent": round(self.price_change_percent, 2),
            "record_count": self.record_count,
            "first_record_time": self.first_record_time.isoformat() if self.first_record_time else None,
            "last_record_time": self.last_record_time.isoformat() if self.last_record_time else None,
        }


@dataclass
class PriceTrend:
    """价格趋势数据"""
    product_id: int
    dates: List[str]
    prices: List[float]
    moving_avg_7: List[float]  # 7天移动平均
    moving_avg_30: List[float]  # 30天移动平均
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "product_id": self.product_id,
            "dates": self.dates,
            "prices": self.prices,
            "moving_avg_7": self.moving_avg_7,
            "moving_avg_30": self.moving_avg_30,
        }


class PriceAnalyzer:
    """
    价格分析器 - 提供各种价格分析功能
    
    Example:
        analyzer = PriceAnalyzer(db_session)
        stats = analyzer.get_price_stats(product_id=1)
        trend = analyzer.get_price_trend(product_id=1, days=30)
    """
    
    def __init__(self, db: Session):
        """
        初始化分析器
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    def get_price_stats(
        self,
        product_id: int,
        days: Optional[int] = None
    ) -> Optional[PriceStats]:
        """
        获取商品价格统计
        
        Args:
            product_id: 商品ID
            days: 统计天数，None表示全部
            
        Returns:
            价格统计数据，商品不存在返回None
        """
        # 获取商品信息
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            logger.warning(f"商品不存在: {product_id}")
            return None
        
        # 构建查询
        query = self.db.query(PriceRecord).filter(
            PriceRecord.product_id == product_id
        )
        
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(PriceRecord.crawl_time >= start_date)
        
        # 按时间排序
        records = query.order_by(PriceRecord.crawl_time).all()
        
        if not records:
            logger.warning(f"没有价格记录: {product_id}")
            return None
        
        # 提取价格列表
        prices = [r.price for r in records]
        
        # 计算统计数据
        min_price = min(prices)
        max_price = max(prices)
        avg_price = mean(prices)
        price_std = stdev(prices) if len(prices) > 1 else 0.0
        
        # 计算价格变动
        first_price = prices[0]
        last_price = prices[-1]
        price_change = last_price - first_price
        price_change_percent = (price_change / first_price * 100) if first_price > 0 else 0.0
        
        return PriceStats(
            product_id=product_id,
            product_name=product.name,
            current_price=product.current_price or last_price,
            min_price=min_price,
            max_price=max_price,
            avg_price=avg_price,
            price_std=price_std,
            price_change=price_change,
            price_change_percent=price_change_percent,
            record_count=len(records),
            first_record_time=records[0].crawl_time,
            last_record_time=records[-1].crawl_time,
        )
    
    def get_price_trend(
        self,
        product_id: int,
        days: int = 30
    ) -> Optional[PriceTrend]:
        """
        获取价格趋势数据
        
        Args:
            product_id: 商品ID
            days: 天数
            
        Returns:
            价格趋势数据
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        records = self.db.query(PriceRecord).filter(
            and_(
                PriceRecord.product_id == product_id,
                PriceRecord.crawl_time >= start_date
            )
        ).order_by(PriceRecord.crawl_time).all()
        
        if not records:
            return None
        
        # 提取日期和价格
        dates = [r.crawl_time.strftime("%Y-%m-%d") for r in records]
        prices = [r.price for r in records]
        
        # 计算移动平均线
        moving_avg_7 = self._calculate_moving_average(prices, 7)
        moving_avg_30 = self._calculate_moving_average(prices, 30)
        
        return PriceTrend(
            product_id=product_id,
            dates=dates,
            prices=prices,
            moving_avg_7=moving_avg_7,
            moving_avg_30=moving_avg_30,
        )
    
    def _calculate_moving_average(
        self,
        prices: List[float],
        window: int
    ) -> List[float]:
        """
        计算移动平均线
        
        Args:
            prices: 价格列表
            window: 窗口大小
            
        Returns:
            移动平均值列表
        """
        if len(prices) < window:
            return [None] * len(prices)
        
        result = []
        for i in range(len(prices)):
            if i < window - 1:
                result.append(None)
            else:
                avg = mean(prices[i - window + 1:i + 1])
                result.append(round(avg, 2))
        
        return result
    
    def detect_price_anomalies(
        self,
        product_id: int,
        std_threshold: float = 2.0
    ) -> List[Dict]:
        """
        检测异常价格（偏离均值超过N个标准差）
        
        Args:
            product_id: 商品ID
            std_threshold: 标准差阈值，默认2.0
            
        Returns:
            异常价格记录列表
        """
        records = self.db.query(PriceRecord).filter(
            PriceRecord.product_id == product_id
        ).order_by(PriceRecord.crawl_time).all()
        
        if len(records) < 10:  # 数据太少不做异常检测
            return []
        
        prices = [r.price for r in records]
        avg_price = mean(prices)
        std_price = stdev(prices)
        
        if std_price == 0:
            return []
        
        anomalies = []
        for record in records:
            z_score = abs(record.price - avg_price) / std_price
            if z_score > std_threshold:
                anomalies.append({
                    "id": record.id,
                    "price": record.price,
                    "crawl_time": record.crawl_time.isoformat(),
                    "z_score": round(z_score, 2),
                    "deviation": round(record.price - avg_price, 2),
                    "deviation_percent": round((record.price - avg_price) / avg_price * 100, 2),
                })
        
        return anomalies
    
    def get_lowest_price_period(
        self,
        product_id: int,
        days: int = 90
    ) -> Optional[Dict]:
        """
        获取最近N天内的最低价时间段
        
        Args:
            product_id: 商品ID
            days: 天数
            
        Returns:
            最低价信息
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        record = self.db.query(PriceRecord).filter(
            and_(
                PriceRecord.product_id == product_id,
                PriceRecord.crawl_time >= start_date
            )
        ).order_by(PriceRecord.price.asc()).first()
        
        if not record:
            return None
        
        return {
            "price": record.price,
            "date": record.crawl_time.strftime("%Y-%m-%d"),
            "crawl_time": record.crawl_time.isoformat(),
        }
    
    def compare_with_competitors(
        self,
        product_ids: List[int]
    ) -> List[Dict]:
        """
        比较多个商品的价格
        
        Args:
            product_ids: 商品ID列表
            
        Returns:
            价格对比结果
        """
        results = []
        
        for pid in product_ids:
            stats = self.get_price_stats(pid)
            if stats:
                results.append(stats.to_dict())
        
        # 按当前价格排序
        results.sort(key=lambda x: x["current_price"])
        
        # 添加排名
        for i, item in enumerate(results):
            item["rank"] = i + 1
        
        return results


# 便捷函数
def get_product_stats(db: Session, product_id: int) -> Optional[Dict]:
    """
    获取商品价格统计的便捷函数
    
    Args:
        db: 数据库会话
        product_id: 商品ID
        
    Returns:
        价格统计数据字典
    """
    analyzer = PriceAnalyzer(db)
    stats = analyzer.get_price_stats(product_id)
    return stats.to_dict() if stats else None


def get_product_trend(db: Session, product_id: int, days: int = 30) -> Optional[Dict]:
    """
    获取价格趋势的便捷函数
    
    Args:
        db: 数据库会话
        product_id: 商品ID
        days: 天数
        
    Returns:
        价格趋势数据字典
    """
    analyzer = PriceAnalyzer(db)
    trend = analyzer.get_price_trend(product_id, days)
    return trend.to_dict() if trend else None