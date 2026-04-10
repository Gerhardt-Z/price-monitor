"""
价格查询API

提供价格记录查询、趋势分析接口
"""

from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel

from models.database import get_db
from models.product import Product
from models.price_record import PriceRecord
from services.price_analyzer import PriceAnalyzer, PriceStats, PriceTrend

router = APIRouter(prefix="/prices", tags=["价格查询"])


# ==================== 响应模型 ====================

class PriceRecordResponse(BaseModel):
    """价格记录响应"""
    id: int
    product_id: int
    price: float
    original_price: Optional[float]
    crawl_time: str
    source: str
    platform: Optional[str]


class PriceStatsResponse(BaseModel):
    """价格统计响应"""
    product_id: int
    product_name: str
    current_price: float
    min_price: float
    max_price: float
    avg_price: float
    price_std: float
    price_change: float
    price_change_percent: float
    record_count: int
    first_record_time: Optional[str]
    last_record_time: Optional[str]


class PriceTrendResponse(BaseModel):
    """价格趋势响应"""
    product_id: int
    dates: List[str]
    prices: List[float]
    moving_avg_7: List[Optional[float]]
    moving_avg_30: List[Optional[float]]


class PriceComparisonResponse(BaseModel):
    """价格对比响应"""
    rank: int
    product_id: int
    product_name: str
    current_price: float
    min_price: float
    max_price: float
    avg_price: float


# ==================== API接口 ====================

@router.get("/{product_id}/records", response_model=List[PriceRecordResponse], summary="获取价格记录")
async def get_price_records(
    product_id: int,
    days: Optional[int] = Query(None, description="查询天数"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    db: Session = Depends(get_db)
):
    """
    获取商品的价格记录
    
    - **product_id**: 商品ID
    - **days**: 最近N天的数据
    - **start_date/end_date**: 自定义日期范围
    """
    # 验证商品存在
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    
    query = db.query(PriceRecord).filter(PriceRecord.product_id == product_id)
    
    # 日期筛选
    if days:
        start = datetime.utcnow() - timedelta(days=days)
        query = query.filter(PriceRecord.crawl_time >= start)
    elif start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(PriceRecord.crawl_time >= start)
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(PriceRecord.crawl_time < end)
    
    records = query.order_by(PriceRecord.crawl_time.desc()).limit(limit).all()
    
    return [r.to_dict() for r in records]


@router.get("/{product_id}/stats", response_model=PriceStatsResponse, summary="获取价格统计")
async def get_price_stats(
    product_id: int,
    days: Optional[int] = Query(None, description="统计天数"),
    db: Session = Depends(get_db)
):
    """
    获取商品价格统计信息
    
    包含：最高价、最低价、平均价、标准差、价格变动等
    """
    analyzer = PriceAnalyzer(db)
    stats = analyzer.get_price_stats(product_id, days)
    
    if not stats:
        raise HTTPException(status_code=404, detail="没有找到价格数据")
    
    return stats.to_dict()


@router.get("/{product_id}/trend", response_model=PriceTrendResponse, summary="获取价格趋势")
async def get_price_trend(
    product_id: int,
    days: int = Query(30, description="天数", ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    获取价格趋势数据（用于图表展示）
    
    包含：每日价格、7日移动平均、30日移动平均
    """
    analyzer = PriceAnalyzer(db)
    trend = analyzer.get_price_trend(product_id, days)
    
    if not trend:
        raise HTTPException(status_code=404, detail="没有找到价格数据")
    
    return trend.to_dict()


@router.get("/{product_id}/lowest", summary="获取历史最低价")
async def get_lowest_price(
    product_id: int,
    days: int = Query(90, description="查询天数"),
    db: Session = Depends(get_db)
):
    """获取指定时间段内的历史最低价"""
    analyzer = PriceAnalyzer(db)
    result = analyzer.get_lowest_price_period(product_id, days)
    
    if not result:
        raise HTTPException(status_code=404, detail="没有找到价格数据")
    
    return result


@router.get("/{product_id}/anomalies", summary="检测异常价格")
async def get_price_anomalies(
    product_id: int,
    std_threshold: float = Query(2.0, description="标准差阈值"),
    db: Session = Depends(get_db)
):
    """
    检测异常价格波动
    
    - **std_threshold**: 偏离均值的标准差倍数，默认2.0
    """
    analyzer = PriceAnalyzer(db)
    anomalies = analyzer.detect_price_anomalies(product_id, std_threshold)
    
    return {
        "product_id": product_id,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies
    }


@router.post("/compare", response_model=List[PriceComparisonResponse], summary="价格对比")
async def compare_prices(
    product_ids: List[int],
    db: Session = Depends(get_db)
):
    """
    对比多个商品的价格
    
    - **product_ids**: 商品ID列表
    """
    if len(product_ids) > 20:
        raise HTTPException(status_code=400, detail="最多对比20个商品")
    
    analyzer = PriceAnalyzer(db)
    results = analyzer.compare_with_competitors(product_ids)
    
    return results


@router.get("/latest/all", summary="获取所有商品最新价格")
async def get_all_latest_prices(
    platform: Optional[str] = Query(None, description="平台筛选"),
    is_active: bool = Query(True, description="是否只看启用的商品"),
    db: Session = Depends(get_db)
):
    """获取所有商品的最新价格"""
    query = db.query(Product)
    
    if platform:
        query = query.filter(Product.platform == platform)
    if is_active:
        query = query.filter(Product.is_active == True)
    
    products = query.all()
    
    results = []
    for product in products:
        results.append({
            "product_id": product.id,
            "name": product.name,
            "platform": product.platform,
            "current_price": product.current_price,
            "last_crawl_at": product.last_crawl_at.isoformat() if product.last_crawl_at else None,
        })
    
    return results


@router.get("/summary/daily", summary="每日价格汇总")
async def get_daily_summary(
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)，默认今天"),
    db: Session = Depends(get_db)
):
    """获取指定日期的价格变动汇总"""
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    else:
        target_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    next_date = target_date + timedelta(days=1)
    
    # 查询当天的价格记录
    records = db.query(PriceRecord).filter(
        and_(
            PriceRecord.crawl_time >= target_date,
            PriceRecord.crawl_time < next_date
        )
    ).all()
    
    # 按商品分组统计
    product_stats = {}
    for record in records:
        if record.product_id not in product_stats:
            product_stats[record.product_id] = {
                "prices": [],
                "product": record.product
            }
        product_stats[record.product_id]["prices"].append(record.price)
    
    summary = []
    for product_id, stats in product_stats.items():
        prices = stats["prices"]
        product = stats["product"]
        
        summary.append({
            "product_id": product_id,
            "product_name": product.name if product else "未知",
            "record_count": len(prices),
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(prices),
            "first_price": prices[0],
            "last_price": prices[-1],
            "price_change": prices[-1] - prices[0],
        })
    
    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "total_records": len(records),
        "products": summary
    }