"""
Streamlit 前端 - 价格监控看板

运行方式：
    streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ==================== 配置 ====================

API_BASE_URL = st.sidebar.text_input(
    "API地址",
    value="http://localhost:8000",
    help="FastAPI服务地址"
)

st.set_page_config(
    page_title="价格监控系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==================== API调用函数 ====================

def api_get(endpoint: str, params: dict = None) -> dict:
    """调用GET接口"""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"API请求失败: {e}")
        return None


def api_post(endpoint: str, data: dict = None) -> dict:
    """调用POST接口"""
    try:
        response = requests.post(f"{API_BASE_URL}{endpoint}", json=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"API请求失败: {e}")
        return None


# ==================== 页面组件 ====================

def show_sidebar():
    """侧边栏"""
    with st.sidebar:
        st.title("📊 价格监控")
        
        page = st.radio(
            "导航",
            ["🏠 首页", "📦 商品管理", "📈 价格趋势", "🔔 告警规则", "⚙️ 任务管理"],
            index=0
        )
        
        st.divider()
        
        # 系统状态
        health = api_get("/health")
        if health:
            st.success("✅ 系统运行正常")
            st.caption(f"版本: {health.get('version', 'N/A')}")
        else:
            st.error("❌ 无法连接API")
        
        return page


def show_homepage():
    """首页 - 总览"""
    st.title("🏠 价格监控总览")
    
    # 获取统计数据
    products = api_get("/api/v1/products/")
    tasks_stats = api_get("/api/v1/tasks/stats/summary")
    
    # 指标卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_products = len(products) if products else 0
        st.metric("监控商品数", total_products)
    
    with col2:
        active_products = len([p for p in (products or []) if p.get('is_active')])
        st.metric("启用商品", active_products)
    
    with col3:
        if tasks_stats:
            success_rate = tasks_stats.get('crawl_stats', {}).get('success_rate', 0)
            st.metric("爬取成功率", f"{success_rate}%")
        else:
            st.metric("爬取成功率", "N/A")
    
    with col4:
        if tasks_stats:
            total_crawls = tasks_stats.get('crawl_stats', {}).get('total_products', 0)
            st.metric("今日爬取次数", total_crawls)
        else:
            st.metric("今日爬取次数", "N/A")
    
    st.divider()
    
    # 最近价格变动
    st.subheader("📈 最近价格变动")
    
    if products:
        for product in products[:10]:
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.write(f"**{product['name'][:30]}...**")
                st.caption(f"平台: {product['platform']} | 店铺: {product.get('shop_name', 'N/A')}")
            
            with col2:
                price = product.get('current_price')
                if price:
                    st.write(f"¥{price:.2f}")
                else:
                    st.write("暂无价格")
            
            with col3:
                last_crawl = product.get('last_crawl_at')
                if last_crawl:
                    st.caption(f"更新: {last_crawl[:16]}")
                else:
                    st.caption("未爬取")
    else:
        st.info("暂无商品，请先添加商品")


def show_product_management():
    """商品管理页面"""
    st.title("📦 商品管理")
    
    # 添加商品表单
    with st.expander("➕ 添加新商品", expanded=False):
        with st.form("add_product"):
            url = st.text_input("商品链接", placeholder="https://item.jd.com/xxx.html")
            category = st.text_input("分类（可选）", placeholder="手机、电脑...")
            notes = st.text_input("备注（可选）")
            
            submitted = st.form_submit_button("添加商品")
            
            if submitted and url:
                result = api_post("/api/v1/products/", {
                    "url": url,
                    "category": category,
                    "notes": notes
                })
                
                if result:
                    st.success(f"✅ 添加成功: {result['name']}")
                    st.rerun()
    
    st.divider()
    
    # 商品列表
    st.subheader("商品列表")
    
    # 筛选条件
    col1, col2, col3 = st.columns(3)
    with col1:
        platform_filter = st.selectbox("平台", ["全部", "taobao", "jd", "pdd"])
    with col2:
        status_filter = st.selectbox("状态", ["全部", "启用", "禁用"])
    with col3:
        keyword = st.text_input("搜索", placeholder="商品名称")
    
    # 构建查询参数
    params = {}
    if platform_filter != "全部":
        params["platform"] = platform_filter
    if status_filter != "全部":
        params["is_active"] = status_filter == "启用"
    if keyword:
        params["keyword"] = keyword
    
    products = api_get("/api/v1/products/", params)
    
    if products:
        # 转换为DataFrame展示
        df = pd.DataFrame(products)
        
        # 选择显示的列
        display_cols = ["id", "name", "platform", "current_price", "is_active", "last_crawl_at"]
        display_df = df[[col for col in display_cols if col in df.columns]]
        
        # 格式化
        if "current_price" in display_df.columns:
            display_df["current_price"] = display_df["current_price"].apply(
                lambda x: f"¥{x:.2f}" if pd.notna(x) else "暂无"
            )
        
        st.dataframe(display_df, use_container_width=True)
        
        # 操作按钮
        st.subheader("操作")
        
        selected_id = st.selectbox("选择商品ID", [p["id"] for p in products])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 刷新价格"):
                result = api_post(f"/api/v1/products/{selected_id}/refresh")
                if result:
                    st.success("✅ 刷新成功")
                    st.rerun()
        
        with col2:
            if st.button("✏️ 编辑"):
                st.info("编辑功能开发中...")
        
        with col3:
            if st.button("🗑️ 删除", type="primary"):
                # 确认删除
                if st.checkbox("确认删除"):
                    try:
                        response = requests.delete(f"{API_BASE_URL}/api/v1/products/{selected_id}")
                        if response.status_code == 200:
                            st.success("✅ 删除成功")
                            st.rerun()
                    except Exception as e:
                        st.error(f"删除失败: {e}")
    else:
        st.info("暂无商品")


def show_price_trends():
    """价格趋势页面"""
    st.title("📈 价格趋势分析")
    
    # 获取商品列表
    products = api_get("/api/v1/products/")
    
    if not products:
        st.warning("暂无商品数据")
        return
    
    # 选择商品
    product_options = {f"{p['name'][:30]}... (ID:{p['id']})": p["id"] for p in products}
    selected = st.selectbox("选择商品", list(product_options.keys()))
    product_id = product_options[selected]
    
    # 时间范围
    days = st.slider("查看天数", min_value=7, max_value=180, value=30)
    
    # 获取价格趋势
    trend = api_get(f"/api/v1/prices/{product_id}/trend", {"days": days})
    stats = api_get(f"/api/v1/prices/{product_id}/stats", {"days": days})
    
    if trend and trend.get("prices"):
        # 显示统计信息
        if stats:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("当前价格", f"¥{stats['current_price']:.2f}")
            with col2:
                st.metric("最低价", f"¥{stats['min_price']:.2f}")
            with col3:
                st.metric("最高价", f"¥{stats['max_price']:.2f}")
            with col4:
                change = stats['price_change_percent']
                st.metric("价格变动", f"{change:+.2f}%")
        
        st.divider()
        
        # 绘制价格走势图
        fig = go.Figure()
        
        # 实际价格
        fig.add_trace(go.Scatter(
            x=trend["dates"],
            y=trend["prices"],
            mode='lines+markers',
            name='实际价格',
            line=dict(color='#1f77b4', width=2),
            marker=dict(size=4)
        ))
        
        # 7日移动平均
        if trend.get("moving_avg_7"):
            fig.add_trace(go.Scatter(
                x=trend["dates"],
                y=trend["moving_avg_7"],
                mode='lines',
                name='7日均线',
                line=dict(color='#ff7f0e', width=1, dash='dash')
            ))
        
        # 30日移动平均
        if trend.get("moving_avg_30"):
            fig.add_trace(go.Scatter(
                x=trend["dates"],
                y=trend["moving_avg_30"],
                mode='lines',
                name='30日均线',
                line=dict(color='#2ca02c', width=1, dash='dot')
            ))
        
        fig.update_layout(
            title="价格走势",
            xaxis_title="日期",
            yaxis_title="价格 (¥)",
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 价格记录表
        st.subheader("📋 价格记录")
        records = api_get(f"/api/v1/prices/{product_id}/records", {"days": days})
        
        if records:
            df = pd.DataFrame(records)
            st.dataframe(df, use_container_width=True)
        
    else:
        st.info("暂无价格数据，请先刷新价格或等待定时任务执行")


def show_alert_rules():
    """告警规则页面"""
    st.title("🔔 告警规则管理")
    
    # 添加告警规则
    with st.expander("➕ 添加告警规则", expanded=False):
        products = api_get("/api/v1/products/")
        
        if products:
            with st.form("add_alert_rule"):
                product_options = {f"{p['name'][:20]}...": p["id"] for p in products}
                selected_product = st.selectbox("选择商品", list(product_options.keys()))
                
                alert_type = st.selectbox(
                    "告警类型",
                    ["price_drop", "price_rise", "threshold"],
                    format_func=lambda x: {
                        "price_drop": "📉 降价告警",
                        "price_rise": "📈 涨价告警",
                        "threshold": "🎯 价格阈值"
                    }[x]
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    threshold_value = st.number_input("阈值金额 (元)", min_value=0.0, value=50.0)
                with col2:
                    threshold_percent = st.number_input("阈值百分比 (%)", min_value=0.0, value=5.0)
                
                notify_method = st.selectbox("通知方式", ["log", "email", "wechat"])
                
                submitted = st.form_submit_button("添加规则")
                
                if submitted:
                    result = api_post("/api/v1/alerts/rules", {
                        "product_id": product_options[selected_product],
                        "alert_type": alert_type,
                        "threshold_value": threshold_value if threshold_value > 0 else None,
                        "threshold_percent": threshold_percent if threshold_percent > 0 else None,
                        "notify_method": notify_method
                    })
                    
                    if result:
                        st.success("✅ 规则添加成功")
                        st.rerun()
        else:
            st.warning("请先添加商品")
    
    st.divider()
    
    # 告警规则列表
    st.sub告警规则列表")
    
    rules = api_get("/api/v1/alerts/rules")
    
    if rules:
        for rule in rules:
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            
            with col1:
                st.write(f"**{rule['alert_type']}** - 商品ID: {rule['product_id']}")
                st.caption(f"触发次数: {rule['trigger_count']} | 创建: {rule['created_at'][:16]}")
            
            with col2:
                if rule.get('threshold_value'):
                    st.write(f"金额阈值: ¥{rule['threshold_value']}")
                if rule.get('threshold_percent'):
                    st.write(f"百分比阈值: {rule['threshold_percent']}%")
            
            with col3:
                status = "✅ 启用" if rule['is_active'] else "❌ 禁用"
                st.write(status)
            
            with col4:
                if st.button("切换", key=f"toggle_{rule['id']}"):
                    api_post(f"/api/v1/alerts/rules/{rule['id']}/toggle")
                    st.rerun()
    else:
        st.info("暂无告警规则")
    
    # 手动检查告警
    st.divider()
    if st.button("🔍 立即检查告警"):
        result = api_post("/api/v1/alerts/check")
        if result:
            st.success(f"检查完成，触发 {result['alert_count']} 个告警")
            if result['alerts']:
                for alert in result['alerts']:
                    st.warning(f"⚠️ {alert['product_name']}: {alert['alert_type']}")


def show_task_management():
    """任务管理页面"""
    st.title("⚙️ 任务管理")
    
    # 调度器状态
    st.subheader("调度器状态")
    
    schedule_status = api_get("/api/v1/tasks/schedule/status")
    
    if schedule_status:
        col1, col2 = st.columns(2)
        
        with col1:
            if schedule_status.get('is_running'):
                st.success("✅ 调度器运行中")
            else:
                st.error("❌ 调度器未运行")
        
        with col2:
            if st.button("启动调度器"):
                api_post("/api/v1/tasks/schedule/start", {"interval_minutes": 30})
                st.rerun()
            
            if st.button("停止调度器"):
                api_post("/api/v1/tasks/schedule/stop")
                st.rerun()
    
    # 定时任务列表
    if schedule_status and schedule_status.get('jobs'):
        st.subheader("定时任务")
        
        for job in schedule_status['jobs']:
            st.write(f"📌 **{job['name']}** - 下次执行: {job.get('next_run', 'N/A')}")
    
    st.divider()
    
    # 手动执行
    st.subheader("手动执行")
    
    col1, col2 = st.columns(2)
    
    with col1:
        platform = st.selectbox("选择平台", ["全部", "taobao", "jd", "pdd"])
    
    with col2:
        if st.button("🚀 立即执行", type="primary"):
            platform_param = None if platform == "全部" else platform
            result = api_post("/api/v1/tasks/run", {"platform": platform_param})
            if result:
                st.success("✅ 任务已启动")
    
    st.divider()
    
    # 任务历史
    st.subheader("任务历史")
    
    tasks = api_get("/api/v1/tasks/")
    
    if tasks:
        df = pd.DataFrame(tasks)
        st.dataframe(df, use_container_width=True)
        
        # 任务统计
        stats = api_get("/api/v1/tasks/stats/summary")
        
        if stats:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("总任务数", stats.get('total_tasks', 0))
            
            with col2:
                crawl_stats = stats.get('crawl_stats', {})
                st.metric("爬取成功率", f"{crawl_stats.get('success_rate', 0)}%")
            
            with col3:
                avg_duration = stats.get('avg_duration_seconds')
                if avg_duration:
                    st.metric("平均耗时", f"{avg_duration:.1f}秒")
    else:
        st.info("暂无任务记录")


# ==================== 主函数 ====================

def main():
    """主函数"""
    page = show_sidebar()
    
    if page == "🏠 首页":
        show_homepage()
    elif page == "📦 商品管理":
        show_product_management()
    elif page == "📈 价格趋势":
        show_price_trends()
    elif page == "🔔 告警规则":
        show_alert_rules()
    elif page == "⚙️ 任务管理":
        show_task_management()


if __name__ == "__main__":
    main()