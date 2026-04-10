"""
任务管理API

提供爬取任务的管理和调度控制
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from models.database import get_db
from models.monitor_task import MonitorTask
from services.scheduler import get_scheduler, run_once

router = APIRouter(prefix="/tasks", tags=["任务管理"])


# ==================== 请求/响应模型 ====================

class TaskResponse(BaseModel):
    """任务响应"""
    id: int
    task_name: str
    platform: str
    status: str
    total_products: int
    success_count: int
    fail_count: int
    start_time: Optional[str]
    end_time: Optional[str]
    duration: Optional[int]
    created_at: Optional[str]


class ScheduleConfig(BaseModel):
    """调度配置"""
    interval_minutes: int = Field(30, description="间隔分钟数", ge=5, le=1440)
    platform: Optional[str] = Field(None, description="平台筛选")


class RunOnceRequest(BaseModel):
    """立即执行请求"""
    platform: Optional[str] = Field(None, description="平台筛选: taobao/jd/pdd")


# ==================== API接口 ====================

@router.get("/", response_model=List[TaskResponse], summary="获取任务列表")
async def get_tasks(
    status: Optional[str] = Query(None, description="状态筛选: pending/running/completed/failed"),
    platform: Optional[str] = Query(None, description="平台筛选"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取爬取任务列表"""
    query = db.query(MonitorTask)
    
    if status:
        query = query.filter(MonitorTask.status == status)
    if platform:
        query = query.filter(MonitorTask.platform == platform)
    
    tasks = query.order_by(MonitorTask.created_at.desc()).limit(limit).all()
    return [t.to_dict() for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse, summary="获取任务详情")
async def get_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """获取单个任务详情"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()


@router.post("/run", summary="立即执行爬取任务")
async def run_task_now(
    data: RunOnceRequest,
    db: Session = Depends(get_db)
):
    """
    立即执行一次爬取任务
    
    - **platform**: 指定平台，不传则爬取所有平台
    """
    try:
        # 异步执行任务
        import threading
        thread = threading.Thread(
            target=run_once,
            kwargs={"platform": data.platform}
        )
        thread.start()
        
        return {
            "message": "任务已启动",
            "platform": data.platform or "all",
            "started_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")


@router.get("/schedule/status", summary="获取调度状态")
async def get_schedule_status():
    """获取调度器运行状态和任务列表"""
    scheduler = get_scheduler()
    
    return {
        "is_running": scheduler.is_running,
        "jobs": scheduler.get_jobs()
    }


@router.post("/schedule/start", summary="启动调度器")
async def start_schedule(
    config: ScheduleConfig
):
    """
    启动定时调度
    
    - **interval_minutes**: 爬取间隔（分钟）
    - **platform**: 平台筛选
    """
    try:
        scheduler = get_scheduler()
        scheduler.start()
        scheduler.add_interval_job(
            interval_minutes=config.interval_minutes,
            platform=config.platform
        )
        
        return {
            "message": "调度器已启动",
            "interval_minutes": config.interval_minutes,
            "platform": config.platform or "all"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动调度器失败: {str(e)}")


@router.post("/schedule/stop", summary="停止调度器")
async def stop_schedule():
    """停止定时调度"""
    try:
        scheduler = get_scheduler()
        scheduler.shutdown()
        
        return {"message": "调度器已停止"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止调度器失败: {str(e)}")


@router.delete("/schedule/{job_id}", summary="移除定时任务")
async def remove_schedule_job(
    job_id: str
):
    """移除指定的定时任务"""
    try:
        scheduler = get_scheduler()
        scheduler.remove_job(job_id)
        
        return {"message": f"任务 {job_id} 已移除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"移除任务失败: {str(e)}")


@router.get("/stats/summary", summary="任务统计")
async def get_task_stats(
    days: int = Query(7, description="统计天数"),
    db: Session = Depends(get_db)
):
    """获取任务执行统计"""
    from datetime import timedelta
    from sqlalchemy import func
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # 总任务数
    total_tasks = db.query(MonitorTask).filter(
        MonitorTask.created_at >= start_date
    ).count()
    
    # 按状态统计
    status_stats = db.query(
        MonitorTask.status,
        func.count(MonitorTask.id).label("count")
    ).filter(
        MonitorTask.created_at >= start_date
    ).group_by(MonitorTask.status).all()
    
    # 成功率
    completed = db.query(MonitorTask).filter(
        MonitorTask.created_at >= start_date,
        MonitorTask.status == "completed"
    ).all()
    
    total_success = sum(t.success_count for t in completed)
    total_fail = sum(t.fail_count for t in completed)
    total_products = total_success + total_fail
    
    # 平均耗时
    avg_duration = db.query(
        func.avg(MonitorTask.duration)
    ).filter(
        MonitorTask.created_at >= start_date,
        MonitorTask.status == "completed"
    ).scalar()
    
    return {
        "period_days": days,
        "total_tasks": total_tasks,
        "status_breakdown": {stat[0]: stat[1] for stat in status_stats},
        "crawl_stats": {
            "total_products": total_products,
            "success_count": total_success,
            "fail_count": total_fail,
            "success_rate": round(total_success / total_products * 100, 2) if total_products > 0 else 0
        },
        "avg_duration_seconds": round(avg_duration, 2) if avg_duration else None
    }