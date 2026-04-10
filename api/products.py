"""
商品管理API

提供商品的增删改查接口
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, HttpUrl

from models.database import get_db
from models.product import Product
from services.scraper import scrape_product

router = APIRouter(prefix="/products", tags=["商品管理"])


# ==================== 请求/响应模型 ====================

class ProductCreate(BaseModel):
    """创建商品请求"""
    url: str = Field(..., description="商品链接", example="https://item.jd.com/100012043978.html")
    name: Optional[str] = Field(None, description="商品名称（可从URL自动获取）")
    category: Optional[str] = Field(None, description="商品分类")
    notes: Optional[str] = Field(None, description="备注")


class ProductUpdate(BaseModel):
    """更新商品请求"""
    name: Optional[str] = Field(None, description="商品名称")
    category: Optional[str] = Field(None, description="商品分类")
    is_active: Optional[bool] = Field(None, description="是否启用监控")
    notes: Optional[str] = Field(None, description="备注")


class ProductResponse(BaseModel):
    """商品响应"""
    id: int
    name: str
    url: str
    platform: str
    product_id: str
    shop_name: Optional[str]
    category: Optional[str]
    image_url: Optional[str]
    current_price: Optional[float]
    original_price: Optional[float]
    is_active: bool
    last_crawl_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class BatchAddRequest(BaseModel):
    """批量添加请求"""
    urls: List[str] = Field(..., description="商品链接列表", min_length=1, max_length=50)


# ==================== API接口 ====================

@router.get("/", response_model=List[ProductResponse], summary="获取商品列表")
async def get_products(
    platform: Optional[str] = Query(None, description="平台筛选: taobao/jd/pdd"),
    is_active: Optional[bool] = Query(None, description="是否启用监控"),
    category: Optional[str] = Query(None, description="分类筛选"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db)
):
    """
    获取商品列表
    
    - **platform**: 按平台筛选
    - **is_active**: 按启用状态筛选
    - **category**: 按分类筛选
    - **keyword**: 按名称搜索
    """
    query = db.query(Product)
    
    if platform:
        query = query.filter(Product.platform == platform)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    if category:
        query = query.filter(Product.category == category)
    if keyword:
        query = query.filter(Product.name.contains(keyword))
    
    products = query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()
    return [p.to_dict() for p in products]


@router.get("/{product_id}", response_model=ProductResponse, summary="获取商品详情")
async def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    """获取单个商品的详细信息"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product.to_dict()


@router.post("/", response_model=ProductResponse, summary="添加商品")
async def create_product(
    data: ProductCreate,
    auto_crawl: bool = Query(True, description="是否自动抓取商品信息"),
    db: Session = Depends(get_db)
):
    """
    添加新商品
    
    - **url**: 商品链接（必填）
    - **auto_crawl**: 是否立即抓取商品信息
    """
    # 检查是否已存在
    existing = db.query(Product).filter(Product.url == data.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="该商品已存在")
    
    # 自动抓取商品信息
    if auto_crawl:
        info = scrape_product(data.url)
        if info:
            product = Product(
                name=data.name or info.name,
                url=data.url,
                platform=info.platform,
                product_id=info.product_id,
                shop_name=info.shop_name,
                image_url=info.image_url,
                current_price=info.price,
                original_price=info.original_price,
                category=data.category,
                notes=data.notes,
                last_crawl_at=info.crawl_time
            )
        else:
            # 抓取失败，使用基础信息
            product = Product(
                name=data.name or "未知商品",
                url=data.url,
                platform=_detect_platform(data.url),
                product_id=_extract_product_id(data.url),
                category=data.category,
                notes=data.notes
            )
    else:
        product = Product(
            name=data.name or "未知商品",
            url=data.url,
            platform=_detect_platform(data.url),
            product_id=_extract_product_id(data.url),
            category=data.category,
            notes=data.notes
        )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return product.to_dict()


@router.put("/{product_id}", response_model=ProductResponse, summary="更新商品")
async def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db)
):
    """更新商品信息"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    
    # 更新字段
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)
    
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    
    return product.to_dict()


@router.delete("/{product_id}", summary="删除商品")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    """删除商品及其所有价格记录"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    
    db.delete(product)
    db.commit()
    
    return {"message": "删除成功", "product_id": product_id}


@router.post("/batch", response_model=List[ProductResponse], summary="批量添加商品")
async def batch_add_products(
    data: BatchAddRequest,
    db: Session = Depends(get_db)
):
    """
    批量添加商品
    
    - **urls**: 商品链接列表（最多50个）
    """
    results = []
    
    for url in data.urls:
        # 跳过已存在的
        existing = db.query(Product).filter(Product.url == url).first()
        if existing:
            results.append(existing.to_dict())
            continue
        
        # 抓取并添加
        info = scrape_product(url)
        if info:
            product = Product(
                name=info.name,
                url=url,
                platform=info.platform,
                product_id=info.product_id,
                shop_name=info.shop_name,
                image_url=info.image_url,
                current_price=info.price,
                original_price=info.original_price,
                last_crawl_at=info.crawl_time
            )
        else:
            product = Product(
                name="未知商品",
                url=url,
                platform=_detect_platform(url),
                product_id=_extract_product_id(url)
            )
        
        db.add(product)
        db.commit()
        db.refresh(product)
        results.append(product.to_dict())
    
    return results


@router.post("/{product_id}/refresh", response_model=ProductResponse, summary="刷新商品价格")
async def refresh_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    """手动刷新商品价格"""
    from services.scraper import scrape_product
    from models.price_record import PriceRecord
    
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    
    info = scrape_product(product.url)
    if not info:
        raise HTTPException(status_code=500, detail="抓取失败")
    
    # 保存价格记录
    record = PriceRecord(
        product_id=product.id,
        price=info.price,
        original_price=info.original_price,
        crawl_time=info.crawl_time,
        source="manual",
        platform=info.platform
    )
    db.add(record)
    
    # 更新商品
    product.current_price = info.price
    product.last_crawl_at = info.crawl_time
    db.commit()
    db.refresh(product)
    
    return product.to_dict()


# ==================== 辅助函数 ====================

def _detect_platform(url: str) -> str:
    """检测平台"""
    url_lower = url.lower()
    if "taobao.com" in url_lower:
        return "taobao"
    elif "tmall.com" in url_lower:
        return "tmall"
    elif "jd.com" in url_lower:
        return "jd"
    elif "pinduoduo.com" in url_lower or "pdd.com" in url_lower:
        return "pdd"
    return "unknown"


def _extract_product_id(url: str) -> str:
    """提取商品ID"""
    import re
    patterns = [r'id=(\d+)', r'/(\d+)\.html', r'/(\d+)$']
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return "unknown"