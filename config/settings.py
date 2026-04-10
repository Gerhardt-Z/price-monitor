"""项目配置"""

import os
from typing import Optional
from pydantic import BaseSettings


class Settings(BaseSettings):
    """
    项目配置类
    
    优先从环境变量读取，其次使用默认值
    """
    
    # ==================== 基础配置 ====================
    APP_NAME: str = "价格监控系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # ==================== 数据库配置 ====================
    DATABASE_URL: str = "sqlite:///./price_monitor.db"
    # PostgreSQL示例: postgresql://user:password@localhost:5432/price_monitor
    
    # ==================== 爬虫配置 ====================
    CRAWLER_DELAY_MIN: float = 1.0  # 最小请求间隔（秒）
    CRAWLER_DELAY_MAX: float = 3.0  # 最大请求间隔（秒）
    CRAWLER_TIMEOUT: int = 30  # 请求超时时间（秒）
    CRAWLER_MAX_RETRIES: int = 3  # 最大重试次数
    
    # ==================== 调度配置 ====================
    SCHEDULER_INTERVAL_MINUTES: int = 30  # 默认爬取间隔（分钟）
    SCHEDULER_ENABLED: bool = True  # 是否启用调度
    
    # ==================== 邮件配置 ====================
    SMTP_SERVER: str = "smtp.qq.com"
    SMTP_PORT: int = 465
    SMTP_SENDER: str = ""
    SMTP_PASSWORD: str = ""  # 授权码
    SMTP_RECEIVER: str = ""
    
    # ==================== 微信配置（Server酱） ====================
    WECHAT_SEND_KEY: str = ""
    
    # ==================== API配置 ====================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1
    
    # ==================== Streamlit配置 ====================
    STREAMLIT_PORT: int = 8501
    
    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    # ==================== 安全配置 ====================
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @property
    def email_config(self) -> dict:
        """获取邮件配置字典"""
        return {
            "smtp_server": self.SMTP_SERVER,
            "smtp_port": self.SMTP_PORT,
            "sender": self.SMTP_SENDER,
            "password": self.SMTP_PASSWORD,
            "receiver": self.SMTP_RECEIVER,
            "wechat_send_key": self.WECHAT_SEND_KEY,
        }
    
    @property
    def crawler_config(self) -> dict:
        """获取爬虫配置字典"""
        return {
            "delay_range": (self.CRAWLER_DELAY_MIN, self.CRAWLER_DELAY_MAX),
            "timeout": self.CRAWLER_TIMEOUT,
            "max_retries": self.CRAWLER_MAX_RETRIES,
        }


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例（依赖注入用）"""
    return settings