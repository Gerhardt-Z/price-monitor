"""
告警服务模块 - 价格变化通知

功能：
- 告警规则管理
- 价格变化检测
- 多渠道通知（邮件、微信、短信）
- 告警历史记录
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.product import Product
from models.price_record import PriceRecord
from models.alert_rule import AlertRule

logger = logging.getLogger(__name__)


@dataclass
class AlertEvent:
    """告警事件"""
    product_id: int
    product_name: str
    alert_type: str
    current_price: float
    previous_price: float
    price_change: float
    price_change_percent: float
    threshold_value: Optional[float]
    triggered_at: datetime
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "alert_type": self.alert_type,
            "current_price": self.current_price,
            "previous_price": self.previous_price,
            "price_change": round(self.price_change, 2),
            "price_change_percent": round(self.price_change_percent, 2),
            "threshold_value": self.threshold_value,
            "triggered_at": self.triggered_at.isoformat(),
        }
    
    def format_message(self) -> str:
        """格式化告警消息"""
        direction = "降" if self.price_change < 0 else "涨"
        return f"""
🔔 价格告警通知

商品：{self.product_name}
类型：{self.alert_type}
当前价格：¥{self.current_price:.2f}
之前价格：¥{self.previous_price:.2f}
价格{direction}动：¥{abs(self.price_change):.2f} ({abs(self.price_change_percent):.2f}%)
触发时间：{self.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}
"""


class AlertService:
    """
    告警服务 - 检测价格变化并发送通知
    
    Example:
        alert_service = AlertService(db_session)
        events = alert_service.check_all_alerts()
        for event in events:
            alert_service.send_notification(event)
    """
    
    def __init__(self, db: Session, email_config: Optional[Dict] = None):
        """
        初始化告警服务
        
        Args:
            db: 数据库会话
            email_config: 邮件配置，包含smtp_server, smtp_port, sender, password
        """
        self.db = db
        self.email_config = email_config or {}
    
    def check_product_alert(self, product_id: int) -> List[AlertEvent]:
        """
        检查单个商品的告警
        
        Args:
            product_id: 商品ID
            
        Returns:
            触发的告警事件列表
        """
        events = []
        
        # 获取商品信息
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product or not product.current_price:
            return events
        
        # 获取最近两次价格记录
        records = self.db.query(PriceRecord).filter(
            PriceRecord.product_id == product_id
        ).order_by(PriceRecord.crawl_time.desc()).limit(2).all()
        
        if len(records) < 2:
            return events
        
        current_price = records[0].price
        previous_price = records[1].price
        
        # 获取该商品的告警规则
        rules = self.db.query(AlertRule).filter(
            and_(
                AlertRule.product_id == product_id,
                AlertRule.is_active == True
            )
        ).all()
        
        for rule in rules:
            event = self._check_rule(
                rule=rule,
                product=product,
                current_price=current_price,
                previous_price=previous_price
            )
            if event:
                events.append(event)
                # 更新规则触发记录
                rule.last_triggered_at = datetime.utcnow()
                rule.trigger_count += 1
                self.db.commit()
        
        return events
    
    def check_all_alerts(self) -> List[AlertEvent]:
        """
        检查所有商品的告警
        
        Returns:
            所有触发的告警事件列表
        """
        events = []
        
        # 获取所有激活的商品
        products = self.db.query(Product).filter(Product.is_active == True).all()
        
        for product in products:
            product_events = self.check_product_alert(product.id)
            events.extend(product_events)
        
        logger.info(f"告警检查完成，触发 {len(events)} 个告警")
        return events
    
    def _check_rule(
        self,
        rule: AlertRule,
        product: Product,
        current_price: float,
        previous_price: float
    ) -> Optional[AlertEvent]:
        """
        检查单条规则
        
        Args:
            rule: 告警规则
            product: 商品信息
            current_price: 当前价格
            previous_price: 之前价格
            
        Returns:
            告警事件，未触发返回None
        """
        price_change = current_price - previous_price
        price_change_percent = (price_change / previous_price * 100) if previous_price > 0 else 0
        
        event = None
        
        if rule.alert_type == "price_drop":
            # 降价告警
            if rule.threshold_value:
                # 按金额
                if price_change <= -rule.threshold_value:
                    event = AlertEvent(
                        product_id=product.id,
                        product_name=product.name,
                        alert_type="降价告警（金额）",
                        current_price=current_price,
                        previous_price=previous_price,
                        price_change=price_change,
                        price_change_percent=price_change_percent,
                        threshold_value=rule.threshold_value,
                        triggered_at=datetime.utcnow()
                    )
            elif rule.threshold_percent:
                # 按百分比
                if price_change_percent <= -rule.threshold_percent:
                    event = AlertEvent(
                        product_id=product.id,
                        product_name=product.name,
                        alert_type="降价告警（百分比）",
                        current_price=current_price,
                        previous_price=previous_price,
                        price_change=price_change,
                        price_change_percent=price_change_percent,
                        threshold_value=rule.threshold_percent,
                        triggered_at=datetime.utcnow()
                    )
        
        elif rule.alert_type == "price_rise":
            # 涨价告警
            if rule.threshold_value:
                if price_change >= rule.threshold_value:
                    event = AlertEvent(
                        product_id=product.id,
                        product_name=product.name,
                        alert_type="涨价告警（金额）",
                        current_price=current_price,
                        previous_price=previous_price,
                        price_change=price_change,
                        price_change_percent=price_change_percent,
                        threshold_value=rule.threshold_value,
                        triggered_at=datetime.utcnow()
                    )
            elif rule.threshold_percent:
                if price_change_percent >= rule.threshold_percent:
                    event = AlertEvent(
                        product_id=product.id,
                        product_name=product.name,
                        alert_type="涨价告警（百分比）",
                        current_price=current_price,
                        previous_price=previous_price,
                        price_change=price_change,
                        price_change_percent=price_change_percent,
                        threshold_value=rule.threshold_percent,
                        triggered_at=datetime.utcnow()
                    )
        
        elif rule.alert_type == "threshold":
            # 价格阈值告警
            if rule.threshold_value and current_price <= rule.threshold_value:
                event = AlertEvent(
                    product_id=product.id,
                    product_name=product.name,
                    alert_type="价格阈值告警",
                    current_price=current_price,
                    previous_price=previous_price,
                    price_change=price_change,
                    price_change_percent=price_change_percent,
                    threshold_value=rule.threshold_value,
                    triggered_at=datetime.utcnow()
                )
        
        return event
    
    def send_notification(self, event: AlertEvent, method: str = "email") -> bool:
        """
        发送告警通知
        
        Args:
            event: 告警事件
            method: 通知方式 (email/wechat/log)
            
        Returns:
            是否发送成功
        """
        try:
            if method == "email":
                return self._send_email(event)
            elif method == "wechat":
                return self._send_wechat(event)
            elif method == "log":
                logger.info(event.format_message())
                return True
            else:
                logger.warning(f"不支持的通知方式: {method}")
                return False
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
            return False
    
    def _send_email(self, event: AlertEvent) -> bool:
        """
        发送邮件通知
        
        Args:
            event: 告警事件
            
        Returns:
            是否发送成功
        """
        if not self.email_config:
            logger.warning("邮件配置未设置")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = self.email_config.get("sender", "")
            msg["To"] = self.email_config.get("receiver", "")
            msg["Subject"] = f"🔔 价格告警: {event.product_name}"
            
            # 邮件正文
            body = event.format_message()
            msg.attach(MIMEText(body, "plain", "utf-8"))
            
            # 发送邮件
            with smtplib.SMTP_SSL(
                self.email_config.get("smtp_server", "smtp.qq.com"),
                self.email_config.get("smtp_port", 465)
            ) as server:
                server.login(
                    self.email_config.get("sender", ""),
                    self.email_config.get("password", "")
                )
                server.send_message(msg)
            
            logger.info(f"邮件发送成功: {event.product_name}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    def _send_wechat(self, event: AlertEvent) -> bool:
        """
        发送微信通知（通过Server酱）
        
        Args:
            event: 告警事件
            
        Returns:
            是否发送成功
        """
        import requests
        
        send_key = self.email_config.get("wechat_send_key", "")
        if not send_key:
            logger.warning("微信SendKey未配置")
            return False
        
        try:
            url = f"https://sctapi.ftqq.com/{send_key}.send"
            data = {
                "title": f"价格告警: {event.product_name}",
                "desp": event.format_message()
            }
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"微信通知发送成功: {event.product_name}")
                return True
            else:
                logger.error(f"微信通知发送失败: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"微信通知发送失败: {e}")
            return False
    
    def get_alert_history(
        self,
        product_id: Optional[int] = None,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取告警历史（从日志或数据库）
        
        Args:
            product_id: 商品ID，None表示全部
            days: 天数
            limit: 返回数量限制
            
        Returns:
            告警历史列表
        """
        # 这里简化处理，实际应该有专门的告警历史表
        # 可以从规则的last_triggered_at和trigger_count推断
        query = self.db.query(AlertRule).filter(
            AlertRule.last_triggered_at.isnot(None)
        )
        
        if product_id:
            query = query.filter(AlertRule.product_id == product_id)
        
        start_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AlertRule.last_triggered_at >= start_date)
        
        rules = query.order_by(AlertRule.last_triggered_at.desc()).limit(limit).all()
        
        history = []
        for rule in rules:
            product = self.db.query(Product).filter(Product.id == rule.product_id).first()
            history.append({
                "rule_id": rule.id,
                "product_id": rule.product_id,
                "product_name": product.name if product else "未知",
                "alert_type": rule.alert_type,
                "trigger_count": rule.trigger_count,
                "last_triggered_at": rule.last_triggered_at.isoformat(),
            })
        
        return history


# 便捷函数
def check_and_notify(db: Session, email_config: Optional[Dict] = None) -> List[Dict]:
    """
    检查告警并发送通知的便捷函数
    
    Args:
        db: 数据库会话
        email_config: 邮件配置
        
    Returns:
        触发的告警事件列表
    """
    service = AlertService(db, email_config)
    events = service.check_all_alerts()
    
    for event in events:
        service.send_notification(event, method="log")
    
    return [e.to_dict() for e in events]