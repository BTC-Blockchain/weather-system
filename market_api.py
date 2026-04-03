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
        try:
            params = {
                "active": "true",
                "limit": 50,
                "search": "Shanghai"
            }
            resp = requests.get(self.gamma_url, params=params, timeout=10)
            result = resp.json()
            
            # 【核心探测点】：看看这个字典到底有哪些键
            logger.info(f"🔍 API 响应字典键名: {list(result.keys())}")
            
            # 兼容性适配：尝试所有可能的路径
            data_list = []
            if isinstance(result, list):
                data_list = result
            elif isinstance(result, dict):
                # 尝试常见的 Gamma API 嵌套路径
                data_list = result.get("data") or result.get("results") or result.get("markets") or []
            
            if not data_list:
                # 如果还是找不到，把整个字典的前 200 个字符打出来看看
                logger.warning(f"⚠️ 无法在字典中定位数据列表。原始预览: {str(result)[:200]}")
                return {}, []

            # ... 后面的循环逻辑保持不变 ...

            token_map = {}
            all_sh_titles = []
            
            # 2. 准备匹配关键词
            parts = target_date.split(' ')
            month_abbr = parts[0]   # "Apr"
            day_num = parts[1].lstrip('0') # "3"

            for mkt in data_list:
                # 获取标题（Gamma 使用 question 字段）
                title = mkt.get("question") or mkt.get("title") or ""
                all_sh_titles.append(title)
                
                # 模糊匹配：上海 + 月份(Apr/April) + 日期(3)
                title_lower = title.lower()
                month_match = (month_abbr.lower() in title_lower or "april" in title_lower)
                day_match = re.search(r'\b' + day_num + r'\b', title) # 精确匹配数字 3
                
                if "shanghai" in title_lower and month_match and day_match:
                    logger.info(f"🎯 匹配成功: {title}")
                    
                    # 3. 提取价格和 ID (处理字符串格式的 JSON)
                    def safe_json_load(field):
                        val = mkt.get(field, "[]")
                        return json.loads(val) if isinstance(val, str) else val

                    outcomes = safe_json_load("outcomes")
                    outcome_prices = safe_json_load("outcomePrices")
                    clob_token_ids = safe_json_load("clobTokenIds")
                    
                    for i in range(len(outcomes)):
                        label = outcomes[i]
                        # 转换价格为浮点数
                        try:
                            price = float(outcome_prices[i]) if i < len(outcome_prices) else None
                        except:
                            price = None
                            
                        t_id = clob_token_ids[i] if i < len(clob_token_ids) else None
                        
                        token_map[label] = {
                            "token_id": t_id,
                            "price": price
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
