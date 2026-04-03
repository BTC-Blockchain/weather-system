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
        全兼容模式：支持 List 和 Dict 两种返回格式
        """
        try:
            params = {
                "active": "true",
                "limit": 50,
                "search": "Shanghai"
            }
            resp = requests.get(self.gamma_url, params=params, timeout=10)
            result = resp.json()
            
            # 【核心适配逻辑】
            data_list = []
            if isinstance(result, list):
                # 报错原因就在这里：既然是 list，直接赋值即可
                data_list = result
                logger.info(f"✅ 识别到列表格式，包含 {len(data_list)} 条记录")
            elif isinstance(result, dict):
                # 如果是字典，尝试所有可能的嵌套路径
                data_list = result.get("data") or result.get("results") or result.get("markets") or []
                logger.info(f"✅ 识别到字典格式，提取出 {len(data_list)} 条记录")
            
            if not data_list:
                logger.warning("⚠️ 扫描完成，但未发现任何数据列表。")
                return {}, []

            token_map = {}
            all_sh_titles = []
            
            # 日期匹配准备 (Apr, 3)
            parts = target_date.split(' ')
            month_abbr = parts[0].lower()   
            day_num = parts[1].lstrip('0') 

            for mkt in data_list:
                # 获取标题：Gamma API 优先看 question 字段
                title = mkt.get("question") or mkt.get("title") or ""
                all_sh_titles.append(title)
                
                title_lower = title.lower()
                # 只要包含上海，且包含月份(apr/april)和日期数字
                if "shanghai" in title_lower:
                    month_match = (month_abbr in title_lower or "april" in title_lower)
                    day_match = re.search(r'\b' + day_num + r'\b', title)
                    
                    if month_match and day_match:
                        logger.info(f"🎯 匹配成功: {title}")
                        
                        # 提取 Outcome 和 Price
                        outcomes = mkt.get("outcomes") or []
                        prices = mkt.get("outcomePrices") or []
                        tokens = mkt.get("clobTokenIds") or []
                        
                        # 如果 API 返回的是 JSON 字符串，则解析它
                        if isinstance(outcomes, str): outcomes = json.loads(outcomes)
                        if isinstance(prices, str): prices = json.loads(prices)
                        if isinstance(tokens, str): tokens = json.loads(tokens)

                        for i in range(len(outcomes)):
                            label = outcomes[i]
                            p = float(prices[i]) if i < len(prices) else 0.0
                            t_id = tokens[i] if i < len(tokens) else ""
                            
                            token_map[label] = {"token_id": t_id, "price": p}
                        
                        return token_map, all_sh_titles
            
            return {}, all_sh_titles

        except Exception as e:
            logger.error(f"🚨 最终尝试失败: {e}")
            return {}, []

    def get_market_price(self, token_data):
        """
        由于 Gamma API 已经自带了价格，这个函数可以作为备用或直接返回已有价格
        """
        if isinstance(token_data, dict):
            return token_data.get("price")
        return None
