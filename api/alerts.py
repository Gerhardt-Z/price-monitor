"""
告警管理API

提供告警规则的增删改查和告警历史查询
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from models.database import get_db
from models.product import Product
from models.alert_rule import AlertRule
from services.alert import AlertService, check_and_notify

router = APIRouter(prefix="/alerts", tags=["告警管理"])


# ==================== 请求/响应模型 ====================

class AlertRuleCreate(BaseModel):
    """创建告警规则请求"""
    product_id: int = Field(..., description="商品ID")
    alert_type: str = Field(..., description="告警类型: price_drop/price_rise/threshold")
    threshold_value: Optional[float] = Field(None, description="阈值金额")
    threshold_percent: Optional[float] = Field(None, description="百分比阈值")
    notify_method: str = Field("email", description="通知方式: email/wechat/log")
    notify_target: Optional[str] = Field(None, description="通知目标（邮箱/手机号）")


class AlertRuleUpdate(BaseModel):
    """更新告警规则请求"""
    alert_type: Optional[str] = None
    threshold_value: Optional[float] = None
    threshold_percent: Optional[float] = None
    is_active: Optional[bool] = None
    notify_method: Optional[str] = None
    notify_target: Optional[str] = None


class AlertRuleResponse(BaseModel):
    """告警规则响应"""
    id: int
    product_id: int
    alert_type: str
    threshold_value: Optional[float]
    threshold_percent: Optional[float]
    is_active: bool
    notify_method: str
    notify_target: Optional[str]
    last_triggered_at: Optional[str]
    trigger_count: int
    created_at: Optional[str]


# ==================== API接口 ====================

@router.get("/rules", response_model=List[AlertRuleResponse], summary="获取告警规则列表")
async def get_alert_rules(
    product_id: Optional[int] = Query(None, description="商品ID筛选"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    db: Session = Depends(get_db)
):
    """获取告警规则列表"""
    query = db.query(AlertRule)
    
    if product_id:
        query = query.filter(AlertRule.product_id == product_id)
    if is_active is not None:
        query = query.filter(AlertRule.is_active == is_active)
    
    rules = query.order_by(AlertRule.created_at.desc()).all()
    return [r.to_dict() for r in rules]


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse, summary="获取告警规则详情")
async def get_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """获取单个告警规则详情"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    return rule.to_dict()


@router.post("/rules", response_model=AlertRuleResponse, summary="创建告警规则")
async def create_alert_rule(
    data: AlertRuleCreate,
    db: Session = Depends(get_db)
):
    """
    创建告警规则
    
    - **alert_type**: 
        - price_drop: 降价告警
        - price_rise: 涨价告警
        - threshold: 价格阈值告警
    """
    # 验证商品存在
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    
    # 验证阈值
    if not data.threshold_value and not data.threshold_percent:
        raise HTTPException(status_code=400, detail="必须设置阈值金额或百分比")
    
    rule = AlertRule(
        product_id=data.product_id,
        alert_type=data.alert_type,
        threshold_value=data.threshold_value,
        threshold_percent=data.threshold_percent,
        notify_method=data.notify_method,
        notify_target=data.notify_target
    )
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return rule.to_dict()


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse, summary="更新告警规则")
async def update_alert_rule(
    rule_id: int,
    data: AlertRuleUpdate,
    db: Session = Depends(get_db)
):
    """更新告警规则"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    db.commit()
    db.refresh(rule)
    
    return rule.to_dict()


@router.delete("/rules/{rule_id}", summary="删除告警规则")
async def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """删除告警规则"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    
    db.delete(rule)
    db.commit()
    
    return {"message": "删除成功", "rule_id": rule_id}


@router.post("/check", summary="手动触发告警检查")
async def trigger_alert_check(
    product_id: Optional[int] = Query(None, description="指定商品ID，不传则检查全部"),
    send_notification: bool = Query(True, description="是否发送通知"),
    db: Session = Depends(get_db)
):
    """
    手动触发告警检查
    
    检查所有（或指定商品）的价格是否触发告警规则
    """
    service = AlertService(db)
    
    if product_id:
        events = service.check_product_alert(product_id)
    else:
        events = service.check_all_alerts()
    
    # 发送通知
    if send_notification:
        for event in events:
            service.send_notification(event, method="log")
    
    return {
        "checked_at": datetime.utcnow().isoformat(),
        "alert_count": len(events),
        "alerts": [e.to_dict() for e in events]
    }


@router.get("/history", summary="获取告警历史")
async def get_alert_history(
    product_id: Optional[int] = Query(None, description="商品ID筛选"),
    days: int = Query(30, description="查询天数", ge=1, le=365),
    limit: int = Query(50, description="返回数量", ge=1, le=200),
    db: Session = Depends(get_db)
):
    """获取告警触发历史"""
    service = AlertService(db)
    history = service.get_alert_history(product_id, days, limit)
    
    return {
        "days": days,
        "total": len(history),
        "history": history
    }


@router.post("/rules/{rule_id}/toggle", response_model=AlertRuleResponse, summary="启停告警规则")
async def toggle_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """切换告警规则的启用状态"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    
    rule.is_active = not rule.is_active
    db.commit()
    db.refresh(rule)
    
    return rule.to_dict()


@router.get("/stats", summary="告警统计")
async def get_alert_stats(
    days: int = Query(30, description="统计天数"),
    db: Session = Depends(get_db)
):
    """获取告警统计数据"""
    from sqlalchemy import func
    from datetime import timedelta
    
    # 总规则数
    total_rules = db.query(AlertRule).count()
    active_rules = db.query(AlertRule).filter(AlertRule.is_active == True).count()
    
    # 触发次数统计
    start_date = datetime.utcnow() - timedelta(days=days)
    triggered_rules = db.query(AlertRule).filter(
        AlertRule.last_triggered_at >= start_date
    ).count()
    
    # 按类型统计
    type_stats = db.query(
        AlertRule.alert_type,
        func.count(AlertRule.id).label("count"),
        func.sum(AlertRule.trigger_count).label("total_triggers")
    ).group_by(AlertRule.alert_type).all()
    
    return {
        "total_rules": total_rules,
        "active_rules": active_rules,
        "triggered_in_period": triggered_rules,
        "type_breakdown": [
            {
                "type": stat[0],
                "rule_count": stat[1],
                "total_triggers": stat[2] or 0
            }
            for stat in type_stats
        ]
    }