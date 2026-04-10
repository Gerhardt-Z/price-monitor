"""
调度服务模块 - 定时执行爬取任务

功能：
- 定时爬取商品价格
- 任务调度和管理
- 任务执行日志
- 失败重试机制
"""

import logging
from typing import List, Optional, Callable
from datetime import datetime, timedelta
from threading import Thread

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from models.database import SessionLocal
from models.product import Product
from models.price_record import PriceRecord
from models.monitor_task import MonitorTask
from services.scraper import ScraperFactory, ProductInfo

logger = logging.getLogger(__name__)


class PriceMonitorScheduler:
    """
    价格监控调度器
    
    Example:
        scheduler = PriceMonitorScheduler()
        scheduler.start()
        scheduler.add_interval_job(interval_minutes=30)
    """
    
    def __init__(self):
        """初始化调度器"""
        self.scheduler = BackgroundScheduler()
        self.is_running = False
    
    def start(self):
        """启动调度器"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("调度器已启动")
    
    def shutdown(self):
        """关闭调度器"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("调度器已关闭")
    
    def add_interval_job(
        self,
        interval_minutes: int = 30,
        platform: Optional[str] = None,
        max_products: Optional[int] = None
    ):
        """
        添加定时任务
        
        Args:
            interval_minutes: 间隔分钟数
            platform: 平台过滤（taobao/jd/pdd/None表示全部）
            max_products: 最大商品数限制
        """
        job_id = f"price_monitor_{platform or 'all'}"
        
        self.scheduler.add_job(
            func=self._run_crawl_task,
            trigger=IntervalTrigger(minutes=interval_minutes),
            args=[platform, max_products],
            id=job_id,
            name=f"价格监控-{platform or '全部'}",
            replace_existing=True
        )
        
        logger.info(f"已添加定时任务: {job_id}, 间隔{interval_minutes}分钟")
    
    def add_cron_job(
        self,
        cron_expression: str,
        platform: Optional[str] = None
    ):
        """
        添加Cron定时任务
        
        Args:
            cron_expression: Cron表达式，如 "0 */2 * * *" 表示每2小时
            platform: 平台过滤
        """
        # 解析cron表达式
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Cron表达式格式错误，应为5位: 分 时 日 月 周")
        
        job_id = f"price_monitor_cron_{platform or 'all'}"
        
        self.scheduler.add_job(
            func=self._run_crawl_task,
            trigger=CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            ),
            args=[platform],
            id=job_id,
            name=f"价格监控Cron-{platform or '全部'}",
            replace_existing=True
        )
        
        logger.info(f"已添加Cron任务: {job_id}, 表达式: {cron_expression}")
    
    def remove_job(self, job_id: str):
        """移除任务"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"已移除任务: {job_id}")
        except Exception as e:
            logger.error(f"移除任务失败: {e}")
    
    def get_jobs(self) -> List[dict]:
        """获取所有任务"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })
        return jobs
    
    def _run_crawl_task(
        self,
        platform: Optional[str] = None,
        max_products: Optional[int] = None
    ):
        """
        执行爬取任务
        
        Args:
            platform: 平台过滤
            max_products: 最大商品数
        """
        db = SessionLocal()
        task = None
        
        try:
            # 创建任务记录
            task = MonitorTask(
                task_name=f"定时爬取-{platform or '全部'}",
                platform=platform or "all",
                status="running",
                start_time=datetime.utcnow()
            )
            db.add(task)
            db.commit()
            
            # 获取要监控的商品
            query = db.query(Product).filter(Product.is_active == True)
            if platform:
                query = query.filter(Product.platform == platform)
            if max_products:
                query = query.limit(max_products)
            
            products = query.all()
            task.total_products = len(products)
            db.commit()
            
            logger.info(f"开始爬取 {len(products)} 个商品")
            
            # 爬取每个商品
            success_count = 0
            fail_count = 0
            errors = []
            
            for product in products:
                try:
                    info = self._crawl_product(product)
                    if info:
                        self._save_price_record(db, product, info)
                        success_count += 1
                    else:
                        fail_count += 1
                        errors.append(f"爬取失败: {product.name}")
                except Exception as e:
                    fail_count += 1
                    errors.append(f"{product.name}: {str(e)}")
                    logger.error(f"爬取异常 {product.name}: {e}")
            
            # 更新任务状态
            task.status = "completed"
            task.success_count = success_count
            task.fail_count = fail_count
            task.end_time = datetime.utcnow()
            task.duration = int((task.end_time - task.start_time).total_seconds())
            task.error_log = "\n".join(errors) if errors else None
            db.commit()
            
            logger.info(f"爬取完成: 成功{success_count}, 失败{fail_count}")
            
        except Exception as e:
            logger.error(f"任务执行异常: {e}")
            if task:
                task.status = "failed"
                task.end_time = datetime.utcnow()
                task.error_log = str(e)
                db.commit()
        finally:
            db.close()
    
    def _crawl_product(self, product: Product) -> Optional[ProductInfo]:
        """
        爬取单个商品
        
        Args:
            product: 商品对象
            
        Returns:
            商品信息
        """
        scraper = ScraperFactory.get_scraper(product.url)
        if not scraper:
            logger.warning(f"不支持的平台: {product.url}")
            return None
        
        return scraper.scrape(product.url)
    
    def _save_price_record(
        self,
        db: Session,
        product: Product,
        info: ProductInfo
    ):
        """
        保存价格记录
        
        Args:
            db: 数据库会话
            product: 商品对象
            info: 爬取到的商品信息
        """
        # 创建价格记录
        record = PriceRecord(
            product_id=product.id,
            price=info.price,
            original_price=info.original_price,
            crawl_time=info.crawl_time,
            source="crawler",
            platform=info.platform
        )
        db.add(record)
        
        # 更新商品当前价格
        product.current_price = info.price
        product.last_crawl_at = info.crawl_time
        
        db.commit()


# 全局调度器实例
_scheduler_instance = None


def get_scheduler() -> PriceMonitorScheduler:
    """获取调度器单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = PriceMonitorScheduler()
    return _scheduler_instance


def start_scheduler(interval_minutes: int = 30):
    """
    启动调度器的便捷函数
    
    Args:
        interval_minutes: 爬取间隔（分钟）
    """
    scheduler = get_scheduler()
    scheduler.start()
    scheduler.add_interval_job(interval_minutes=interval_minutes)
    logger.info(f"调度器已启动，每{interval_minutes}分钟爬取一次")


def run_once(platform: Optional[str] = None):
    """
    立即执行一次爬取任务
    
    Args:
        platform: 平台过滤
    """
    scheduler = get_scheduler()
    scheduler._run_crawl_task(platform=platform)