"""商品模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.orm import relationship

from .database import Base


class Product(Base):
    """
    商品模型 - 存储被监控的商品信息
    
    Attributes:
        id: 主键ID
        name: 商品名称
        url: 商品链接
        platform: 平台（taobao/jd/pdd）
        product_id: 平台商品ID
        shop_name: 店铺名称
        category: 商品分类
        image_url: 商品图片
        current_price: 当前价格
        original_price: 原价
        is_active: 是否激活监控
        last_crawl_at: 上次爬取时间
        created_at: 创建时间
        updated_at: 更新时间
        notes: 备注
    """
    
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(500), nullable=False, comment="商品名称")
    url = Column(String(1000), nullable=False, unique=True, comment="商品链接")
    platform = Column(String(20), nullable=False, index=True, comment="平台: taobao/jd/pdd")
    product_id = Column(String(100), nullable=False, index=True, comment="平台商品ID")
    shop_name = Column(String(200), nullable=True, comment="店铺名称")
    category = Column(String(100), nullable=True, comment="商品分类")
    image_url = Column(String(1000), nullable=True, comment="商品图片URL")
    current_price = Column(Float, nullable=True, comment="当前价格")
    original_price = Column(Float, nullable=True, comment="原价")
    is_active = Column(Boolean, default=True, index=True, comment="是否激活监控")
    last_crawl_at = Column(DateTime, nullable=True, comment="上次爬取时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    notes = Column(Text, nullable=True, comment="备注")
    
    # 关联关系
    price_records = relationship("PriceRecord", back_populates="product", cascade="all, delete-orphan")
    alert_rules = relationship("AlertRule", back_populates="product", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name[:20]}...', platform='{self.platform}')>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "platform": self.platform,
            "product_id": self.product_id,
            "shop_name": self.shop_name,
            "category": self.category,
            "image_url": self.image_url,
            "current_price": self.current_price,
            "original_price": self.original_price,
            "is_active": self.is_active,
            "last_crawl_at": self.last_crawl_at.isoformat() if self.last_crawl_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "notes": self.notes,
        }