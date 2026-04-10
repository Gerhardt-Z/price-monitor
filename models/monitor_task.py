"""监控任务模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text
import enum

from .database import Base


class TaskStatus(enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    PAUSED = "paused"        # 暂停


class MonitorTask(Base):
    """
    监控任务模型 - 记录爬取任务执行历史
    
    Attributes:
        id: 主键ID
        task_name: 任务名称
        platform: 监控平台
        status: 任务状态
        total_products: 总商品数
        success_count: 成功数
        fail_count: 失败数
        start_time: 开始时间
        end_time: 结束时间
        duration: 耗时（秒）
        error_log: 错误日志
        created_at: 创建时间
    """
    
    __tablename__ = "monitor_tasks"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_name = Column(String(100), nullable=False, comment="任务名称")
    platform = Column(String(20), nullable=True, comment="监控平台: all/taobao/jd/pdd")
    status = Column(String(20), default="pending", index=True, comment="任务状态")
    total_products = Column(Integer, default=0, comment="总商品数")
    success_count = Column(Integer, default=0, comment="成功数")
    fail_count = Column(Integer, default=0, comment="失败数")
    start_time = Column(DateTime, nullable=True, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    duration = Column(Integer, nullable=True, comment="耗时（秒）")
    error_log = Column(Text, nullable=True, comment="错误日志")
    created_at = Column(DateTime, default=datetime.utcnow, index=True, comment="创建时间")
    
    def __repr__(self) -> str:
        return f"<MonitorTask(id={self.id}, name='{self.task_name}', status={self.status})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "task_name": self.task_name,
            "platform": self.platform,
            "status": self.status,
            "total_products": self.total_products,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_products == 0:
            return 0.0
        return (self.success_count / self.total_products) * 100