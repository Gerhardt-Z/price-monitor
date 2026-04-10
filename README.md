# 🔍 竞品价格监控系统

一个基于 Python 的价格监控系统，支持自动爬取电商平台商品价格、趋势分析、智能告警。

## ✨ 功能特性

- 📦 **商品管理** - 支持淘宝、京东、拼多多商品监控
- 📈 **价格追踪** - 自动记录价格变化，生成趋势图表
- 🔔 **智能告警** - 降价/涨价/阈值告警，支持邮件和微信通知
- ⚙️ **定时任务** - 自动定时爬取，无需人工干预
- 📊 **数据看板** - Streamlit 可视化界面，直观展示数据

## 🏗️ 项目结构

```
price_monitor/
├── main.py                    # FastAPI 入口
├── requirements.txt           # Python 依赖
├── Dockerfile                 # Docker 配置
├── docker-compose.yml         # Docker Compose 配置
├── .env.example               # 环境变量模板
├── config/
│   └── settings.py            # 项目配置
├── models/
│   ├── database.py            # 数据库配置
│   ├── product.py             # 商品模型
│   ├── price_record.py        # 价格记录模型
│   ├── alert_rule.py          # 告警规则模型
│   └── monitor_task.py        # 监控任务模型
├── services/
│   ├── scraper.py             # 爬虫模块
│   ├── price_analyzer.py      # 价格分析模块
│   ├── alert.py               # 告警服务模块
│   └── scheduler.py           # 定时调度模块
├── api/
│   ├── products.py            # 商品管理 API
│   ├── prices.py              # 价格查询 API
│   ├── alerts.py              # 告警管理 API
│   └── tasks.py               # 任务管理 API
└── dashboard/
    └── app.py                 # Streamlit 前端
```

## 🚀 快速开始

### 方式一：本地运行

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd price_monitor

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置邮件、微信等

# 5. 启动 API 服务
python main.py

# 6. 启动前端看板（新终端）
streamlit run dashboard/app.py
```

### 方式二：Docker 部署

```bash
# 1. 配置环境变量
cp .env.example .env

# 2. 启动所有服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

## 📖 使用指南

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| API 文档 | http://localhost:8000/docs | Swagger UI |
| API 文档 | http://localhost:8000/redoc | ReDoc |
| 前端看板 | http://localhost:8501 | Streamlit |

### 添加商品

**方式一：通过 API**
```bash
curl -X POST "http://localhost:8000/api/v1/products/" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://item.jd.com/100012043978.html"}'
```

**方式二：通过前端**
1. 打开 http://localhost:8501
2. 点击「商品管理」
3. 点击「添加新商品」
4. 输入商品链接

### 设置告警

```bash
curl -X POST "http://localhost:8000/api/v1/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 1,
    "alert_type": "price_drop",
    "threshold_value": 50,
    "notify_method": "email"
  }'
```

### 启动定时任务

```bash
# 启动调度器（默认30分钟一次）
curl -X POST "http://localhost:8000/api/v1/tasks/schedule/start" \
  -H "Content-Type: application/json" \
  -d '{"interval_minutes": 30}'

# 立即执行一次
curl -X POST "http://localhost:8000/api/v1/tasks/run"
```

## 📊 API 接口总览

| 模块 | 接口 | 方法 | 说明 |
|------|------|------|------|
| 商品 | `/api/v1/products/` | GET | 获取商品列表 |
| 商品 | `/api/v1/products/` | POST | 添加商品 |
| 商品 | `/api/v1/products/{id}` | GET | 获取商品详情 |
| 商品 | `/api/v1/products/{id}` | PUT | 更新商品 |
| 商品 | `/api/v1/products/{id}` | DELETE | 删除商品 |
| 商品 | `/api/v1/products/{id}/refresh` | POST | 刷新价格 |
| 价格 | `/api/v1/prices/{id}/records` | GET | 获取价格记录 |
| 价格 | `/api/v1/prices/{id}/stats` | GET | 获取价格统计 |
| 价格 | `/api/v1/prices/{id}/trend` | GET | 获取价格趋势 |
| 告警 | `/api/v1/alerts/rules` | GET | 获取告警规则 |
| 告警 | `/api/v1/alerts/rules` | POST | 创建告警规则 |
| 告警 | `/api/v1/alerts/check` | POST | 手动触发告警检查 |
| 任务 | `/api/v1/tasks/` | GET | 获取任务列表 |
| 任务 | `/api/v1/tasks/run` | POST | 立即执行任务 |
| 任务 | `/api/v1/tasks/schedule/start` | POST | 启动调度器 |

## ⚙️ 环境变量说明

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | `sqlite:///./price_monitor.db` | 数据库连接地址 |
| `SCHEDULER_INTERVAL_MINUTES` | `30` | 定时爬取间隔（分钟） |
| `SCHEDULER_ENABLED` | `true` | 是否启用定时任务 |
| `SMTP_SERVER` | `smtp.qq.com` | 邮件服务器 |
| `SMTP_SENDER` | - | 发件人邮箱 |
| `SMTP_PASSWORD` | - | 邮箱授权码 |
| `WECHAT_SEND_KEY` | - | Server酱 SendKey |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## ⚠️ 注意事项

1. **合规使用**：请遵守目标网站的 robots.txt 和使用条款
2. **爬取频率**：建议间隔 30 分钟以上，避免被封 IP
3. **反爬机制**：电商平台有反爬措施，生产环境建议使用官方 API 或第三方数据服务
4. **数据存储**：生产环境建议使用 PostgreSQL 替代 SQLite

## 📝 开发计划

- [ ] 支持拼多多爬虫
- [ ] 支持抖音电商
- [ ] 增加销量预估功能
- [ ] 支持导出 Excel 报表
- [ ] 增加用户认证系统
- [ ] 支持多租户

## 📄 License

MIT License

---

**如果觉得有用，别忘了点个 ⭐ Star！**