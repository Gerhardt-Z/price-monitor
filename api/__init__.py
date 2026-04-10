"""API路由包"""

from fastapi import APIRouter
from .products import router as products_router
from .prices import router as prices_router
from .alerts import router as alerts_router
from .tasks import router as tasks_router

# 创建主路由
router = APIRouter(prefix="/api/v1")

# 注册子路由
router.include_router(products_router)
router.include_router(prices_router)
router.include_router(alerts_router)
router.include_router(tasks_router)


@router.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {"status": "ok", "message": "价格监控系统运行正常"}