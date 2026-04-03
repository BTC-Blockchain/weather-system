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
        深度扫描：不放过任何包含 Shanghai 和 Temperature 的活跃合约
        """
        try:
            # 1. 尝试使用 sampling 端点，这通常返回最活跃的实时交易对
            search_url = "https://clob.polymarket.com/sampling-markets"
            resp = requests.get(search_url, timeout=10)
            data_list = resp.json()
            
            token_map = {}
            all_shanghai_titles = []
            
            # 2. 准备我们要找的“蛛丝马迹”
            # 我们找的是：同时包含 [Shanghai] 和 [Temperature] 的项
            # 或者是 [Shanghai] 和 [今天日期] 的项
            parts = target_date.split(' ')
            month_abbr = parts[0] # "Apr"
            day_num = parts[1].lstrip('0') # "3"

            for mkt in data_list:
                # 把整个对象转为字符串，进行无死角搜索
                raw_content = str(mkt).lower()
                
                # 寻找关键组合：上海 + 温度 + 日期
                if "shanghai" in raw_content and ("temp" in raw_content or "degree" in raw_content):
                    title = mkt.get("title", "Unknown")
                    all_shanghai_titles.append(title)
                    
                    # 如果这刚好是今天的日期
                    if day_num in title:
                        logger.info(f"🎯 深度嗅探成功: {title}")
                        
                        # 3. 提取 Token (注意：这里直接从 mkt['tokens'] 获取)
                        tokens = mkt.get("tokens", [])
                        for tk in tokens:
                            outcome = tk.get("outcome") # 如 "Above 30°C"
                            t_id = tk.get("token_id")
                            token_map[outcome] = t_id
                        
                        # 只要找到一个包含今天日期的上海温度市场就返回
                        return token_map, all_shanghai_titles
            
            return token_map, all_shanghai_titles
        except Exception as e:
            logger.error(f"🚨 深度嗅探失败: {e}")
            return {}, []

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
