"""
FastAPI 主入口

启动价格监控系统的API服务
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import settings
from models.database import init_db
from api import router as api_router
from services.scheduler import get_scheduler

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        # logging.FileHandler(settings.LOG_FILE),  # 生产环境启用
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    - 启动时：初始化数据库、启动调度器
    - 关闭时：停止调度器
    """
    # 启动时执行
    logger.info("🚀 价格监控系统启动中...")
    
    # 初始化数据库
    init_db()
    logger.info("✅ 数据库初始化完成")
    
    # 启动调度器
    if settings.SCHEDULER_ENABLED:
        scheduler = get_scheduler()
        scheduler.start()
        scheduler.add_interval_job(
            interval_minutes=settings.SCHEDULER_INTERVAL_MINUTES
        )
        logger.info(f"✅ 调度器已启动，每{settings.SCHEDULER_INTERVAL_MINUTES}分钟执行一次")
    
    logger.info(f"🎉 {settings.APP_NAME} v{settings.APP_VERSION} 启动完成")
    
    yield  # 应用运行期间
    
    # 关闭时执行
    logger.info("👋 价格监控系统关闭中...")
    
    if settings.SCHEDULER_ENABLED:
        scheduler = get_scheduler()
        scheduler.shutdown()
        logger.info("✅ 调度器已停止")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    🔍 **竞品价格监控系统 API**
    
    功能特性：
    - 商品管理（增删改查）
    - 价格记录与趋势分析
    - 智能告警规则
    - 定时爬取任务
    
    快速开始：
    1. 添加商品：POST /api/v1/products/
    2. 查看价格：GET /api/v1/prices/{product_id}/records
    3. 设置告警：POST /api/v1/alerts/rules
    """,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)


# ==================== 全局异常处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误",
            "message": str(exc) if settings.DEBUG else "请稍后重试"
        }
    )


# ==================== 根路由 ====================

@app.get("/", tags=["系统"])
async def root():
    """系统首页"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
        "message": "欢迎使用竞品价格监控系统！"
    }


@app.get("/health", tags=["系统"])
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "scheduler_enabled": settings.SCHEDULER_ENABLED
    }


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        workers=settings.API_WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )