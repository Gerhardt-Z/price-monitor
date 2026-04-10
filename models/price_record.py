"""价格记录模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from .database import Base


class PriceRecord(Base):
    """
    价格记录模型 - 存储商品的历史价格
    
    Attributes:
        id: 主键ID
        product_id: 关联商品ID
        price: 价格
        original_price: 原价
        crawl_time: 爬取时间
        source: 数据来源（manual/api/crawler）
        platform: 平台
        extra_data: 额外数据（JSON格式）
    """
    
    __tablename__ = "price_records"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    price = Column(Float, nullable=False, comment="价格")
    original_price = Column(Float, nullable=True, comment="原价")
    crawl_time = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="爬取时间")
    source = Column(String(20), default="crawler", comment="数据来源: manual/api/crawler")
    platform = Column(String(20), nullable=True, comment="平台")
    extra_data = Column(String(2000), nullable=True, comment="额外数据JSON")
    
    # 关联关系
    product = relationship("Product", back_populates="price_records")
    
    # 复合索引
    __table_args__ = (
        Index("idx_product_crawl_time", "product_id", "crawl_time"),
    )
    
    def __repr__(self) -> str:
        return f"<PriceRecord(id={self.id}, product_id={self.product_id}, price={self.price})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "price": self.price,
            "original_price": self.original_price,
            "crawl_time": self.crawl_time.isoformat() if self.crawl_time else None,
            "source": self.source,
            "platform": self.platform,
            "extra_data": self.extra_data,
        }