"""告警规则模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum

from .database import Base


class AlertType(enum.Enum):
    """告警类型枚举"""
    PRICE_DROP = "price_drop"      # 降价
    PRICE_RISE = "price_rise"      # 涨价
    PRICE_THRESHOLD = "threshold"  # 价格阈值
    STOCK_CHANGE = "stock_change"  # 库存变化


class AlertRule(Base):
    """
    告警规则模型 - 定义价格告警条件
    
    Attributes:
        id: 主键ID
        product_id: 关联商品ID
        alert_type: 告警类型
        threshold_value: 阈值（降价金额/涨价金额/目标价格）
        threshold_percent: 百分比阈值
        is_active: 是否启用
        notify_method: 通知方式（email/wechat/sms）
        notify_target: 通知目标（邮箱/手机号）
        last_triggered_at: 上次触发时间
        trigger_count: 触发次数
        created_at: 创建时间
    """
    
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String(20), nullable=False, comment="告警类型: price_drop/price_rise/threshold")
    threshold_value = Column(Float, nullable=True, comment="阈值金额")
    threshold_percent = Column(Float, nullable=True, comment="百分比阈值（如5表示5%）")
    is_active = Column(Boolean, default=True, index=True, comment="是否启用")
    notify_method = Column(String(20), default="email", comment="通知方式: email/wechat/sms")
    notify_target = Column(String(200), nullable=True, comment="通知目标")
    last_triggered_at = Column(DateTime, nullable=True, comment="上次触发时间")
    trigger_count = Column(Integer, default=0, comment="触发次数")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    
    # 关联关系
    product = relationship("Product", back_populates="alert_rules")
    
    def __repr__(self) -> str:
        return f"<AlertRule(id={self.id}, type={self.alert_type}, product_id={self.product_id})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "alert_type": self.alert_type,
            "threshold_value": self.threshold_value,
            "threshold_percent": self.threshold_percent,
            "is_active": self.is_active,
            "notify_method": self.notify_method,
            "notify_target": self.notify_target,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "trigger_count": self.trigger_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }