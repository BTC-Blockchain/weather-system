import requests
import logging
import json
import re

logger = logging.getLogger(__name__)

class PolymarketAPI:
    def __init__(self):
        # 注意：这是网页端使用的 Gamma API，数据最全
        self.gamma_url = "https://gamma-api.polymarket.com/markets"

    def get_shanghai_temp_markets(self, target_date):
        """
        通过 Gamma API 获取网页端实时可见的市场数据
        """
        try:
            # 1. 构造搜索参数：直接在 API 层面搜索 Shanghai
            params = {
                "active": "true",
                "limit": 50,
                "search": "Shanghai",
                "order": "activeStartTime",
                "ascending": "false"
            }
            logger.info(f"--- 正在通过 Gamma API 检索: {target_date} ---")
            
            resp = requests.get(self.gamma_url, params=params, timeout=10)
            data_list = resp.json()
            
            token_map = {}
            all_sh_titles = []
            
            # 2. 准备匹配关键词 (例如 "April", "3")
            month_abbr = target_date.split(' ')[0] # "Apr"
            day_num = target_date.split(' ')[1].lstrip('0') # "3"

            for mkt in data_list:
                title = mkt.get("question", mkt.get("title", ""))
                all_sh_titles.append(title)
                
                # 模糊匹配日期和温度关键词
                # 检查标题是否包含 (Apr 或 April) 且 包含数字 (3)
                if ("shanghai" in title.lower() and 
                    (month_abbr.lower() in title.lower() or "april" in title.lower()) and 
                    (f" {day_num}" in title or f" {day_num}?" in title)):
                    
                    logger.info(f"🎯 成功定位网页端市场: {title}")
                    
                    # 3. 提取 Outcome 和 Price (Gamma API 的结构不同)
                    # 注意：Gamma API 通常直接在 outcomes 字段里提供实时价格
                    outcomes = json.loads(mkt.get("outcomes", "[]"))
                    outcome_prices = json.loads(mkt.get("outcomePrices", "[]"))
                    clob_token_ids = json.loads(mkt.get("clobTokenIds", "[]"))
                    
                    for i in range(len(outcomes)):
                        label = outcomes[i]
                        # 尝试获取价格，如果获取不到则设为 None
                        price = float(outcome_prices[i]) if i < len(outcome_prices) else None
                        t_id = clob_token_ids[i] if i < len(clob_token_ids) else None
                        
                        # 重点：这里我们直接存下 Label 到 ID 的映射
                        token_map[label] = {
                            "token_id": t_id,
                            "price": price  # Gamma API 直接给出了价格，甚至不需要再调一次接口！
                        }
                    
                    return token_map, all_sh_titles
            
            return {}, all_sh_titles
        except Exception as e:
            logger.error(f"Gamma API 访问失败: {e}")
            return {}, []

    def get_market_price(self, token_data):
        """
        由于 Gamma API 已经自带了价格，这个函数可以作为备用或直接返回已有价格
        """
        if isinstance(token_data, dict):
            return token_data.get("price")
        return None
