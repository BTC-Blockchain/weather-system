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
        try:
            # 增加 limit 到 200，并尝试不带任何过滤条件
            params = {"limit": 200}
            resp = requests.get(self.search_url, params=params, timeout=10)
            all_data = resp.json().get("data", [])
            
            all_shanghai_raw = [] # 记录所有包含 Shanghai 的原始对象
            
            for mkt in all_data:
                # 检查所有可能的文本字段：title, description, question
                raw_text = str(mkt).lower()
                if "shanghai" in raw_text:
                    all_shanghai_raw.append(mkt)
            
            # 我们不在这里做匹配逻辑，直接把原始数据扔回 app.py 观察
            return all_shanghai_raw
        except Exception as e:
            return []

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
