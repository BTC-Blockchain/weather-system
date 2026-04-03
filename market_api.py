# market_api.py
import requests
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PolymarketAPI:
    def __init__(self):
        self.book_url = "https://clob.polymarket.com/book"
        self.search_url = "https://clob.polymarket.com/markets"

    def get_shanghai_temp_markets(self, target_date):
        """
        性能建议：此函数在 app.py 中应配合 st.cache_data 使用
        自动发现：根据日期搜索上海气温市场
        """
        try:
            # 这里的 active=true 过滤掉已结束的市场
            params = {"next_cursor": "", "active": "true"}
            logger.info(f"正在从 Polymarket 搜索包含关键词: 'Shanghai' 和 '{target_date}' 的市场...")
            
            resp = requests.get(self.search_url, params=params, timeout=10)
            all_markets = resp.json()
            
            token_map = {}
            market_found = False
            
            for mkt in all_markets.get("data", []):
                title = mkt.get("title", "")
                # 调试信息：打印发现的所有上海相关市场
                if "Shanghai" in title:
                    logger.info(f"发现候选市场: {title}")
                
                # 匹配逻辑：必须同时包含上海和日期
                if "Shanghai" in title and target_date in title:
                    market_found = True
                    logger.info(f"🎯 成功匹配目标市场: {title}")
                    
                    # Polymarket 存储的是字符串形式的 JSON
                    import json
                    outcomes = json.loads(mkt.get("outcomes", "[]"))
                    token_ids = json.loads(mkt.get("clobTokenIds", "[]"))
                    
                    for i in range(len(outcomes)):
                        token_map[outcomes[i]] = token_ids[i]
            
            if not market_found:
                logger.warning(f"未找到匹配日期 {target_date} 的上海市场。")
                
            return token_map
        except Exception as e:
            logger.error(f"市场自动搜索发生错误: {e}")
            return {}

    def get_market_price(self, token_id):
        """获取指定 Token 的最优卖价 (Ask)"""
        try:
            resp = requests.get(self.book_url, params={"token_id": token_id}, timeout=5)
            data = resp.json()
            if data.get("asks"):
                return float(data["asks"][0]["price"])
            return None
        except Exception as e:
            logger.error(f"获取 Token {token_id} 价格失败: {e}")
            return None