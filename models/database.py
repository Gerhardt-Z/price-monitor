"""数据库配置"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 数据库URL（从环境变量读取，默认使用SQLite）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./price_monitor.db"
)

# SQLite特殊配置
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # 自动重连
    echo=False,  # 是否打印SQL（调试时设为True）
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
Base = declarative_base()


def get_db():
    """
    获取数据库会话（依赖注入用）
    
    Yields:
        Session: SQLAlchemy会话对象
        
    Example:
        @app.get("/products")
        def get_products(db: Session = Depends(get_db)):
            return db.query(Product).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化数据库（创建所有表）
    
    Example:
        from models.database import init_db
        init_db()
    """
    from . import product, price_record, alert_rule, monitor_task  # noqa
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库初始化完成")