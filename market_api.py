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
        自动发现：根据日期模糊搜索上海气温市场
        :param target_date: 传入格式如 "Apr 3"
        :return: (token_map, found_titles) -> 返回匹配到的ID字典和搜到的所有相关标题列表
        """
        try:
            # 1. 扩大搜索范围：获取所有当前活跃的市场
            params = {"next_cursor": "", "active": "true"}
            logger.info(f"--- 启动市场扫描: 目标日期 [{target_date}] ---")
            
            resp = requests.get(self.search_url, params=params, timeout=10)
            all_markets = resp.json()
            
            token_map = {}
            all_shanghai_titles = [] # 用于存储搜到的所有上海市场，供 UI 调试显示
            market_found = False
            
            # 2. 准备模糊匹配的关键词
            # 从 "Apr 3" 中提取 "Apr" 和 "3"
            parts = target_date.split(' ')
            month_abbr = parts[0]  # "Apr"
            day_num = parts[1].lstrip('0')  # 去掉前导0，变成 "3"

            for mkt in all_markets.get("data", []):
                title = mkt.get("title", "")
                
                # 第一层过滤：必须包含 "Shanghai"
                if "Shanghai" in title:
                    all_shanghai_titles.append(title)
                    logger.info(f"🔍 发现上海相关合约: {title}")
                    
                    # 第二层模糊匹配：标题需同时包含月份简写(Apr)和天数(3)
                    # 这样可以兼容 "Apr 3", "April 3rd", "Apr 03" 等多种写法
                    if month_abbr in title and day_num in title:
                        market_found = True
                        logger.info(f"🎯 模糊匹配成功: {title}")
                        
                        # 解析 Outcome 和 Token ID
                        import json
                        outcomes = json.loads(mkt.get("outcomes", "[]"))
                        token_ids = json.loads(mkt.get("clobTokenIds", "[]"))
                        
                        # 将结果存入映射表
                        for i in range(len(outcomes)):
                            token_map[outcomes[i]] = token_ids[i]
                        
                        # 找到第一个匹配的市场后通常即可停止（Polymarket每天通常只有一个上海气温市场）
                        break
            
            if not market_found:
                logger.warning(f"❌ 扫描结束：未能匹配到包含 '{month_abbr}' 和 '{day_num}' 的上海市场")
            
            # 注意：这里返回了两个值，方便 app.py 渲染调试面板
            return token_map, all_shanghai_titles

        except Exception as e:
            logger.error(f"🚨 市场自动搜索发生异常: {e}")
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
