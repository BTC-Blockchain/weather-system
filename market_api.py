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
            # 这里的 sampling-markets 通常返回的是列表
            search_url = "https://clob.polymarket.com/sampling-markets"
            resp = requests.get(search_url, timeout=10)
            data_list = resp.json()
            
            all_shanghai_raw = [] 
            
            # 强制遍历所有返回的数据
            for mkt in data_list:
                # 深度搜索：在整个 JSON 字符串里找关键词
                if "shanghai" in str(mkt).lower():
                    all_shanghai_raw.append(mkt)
            
            # 返回所有搜到的原始对象，让 app.py 去展示
            return all_shanghai_raw, [] # 返回两个值保持格式统一
        except Exception as e:
            logger.error(f"侦听模式出错: {e}")
            return [], []

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
