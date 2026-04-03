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
        全量雷达模式：不再依赖 API 搜索，直接从活跃池中筛选
        """
        try:
            # 1. 获取较大量的活跃市场（增加到 100，不带 search 参数，避免 API 逻辑干扰）
            params = {
                "active": "true",
                "limit": 100,
                "closed": "false",
                "order": "volume24hr", # 按成交量排序，气温合约通常成交活跃
                "ascending": "false"
            }
            logger.info(f"--- 🛰️ 启动全量雷达扫描 (目标: {target_date}) ---")
            
            resp = requests.get(self.gamma_url, params=params, timeout=10)
            data_list = resp.json()
            
            # 兼容字典格式包裹的列表
            if isinstance(data_list, dict):
                data_list = data_list.get("data") or data_list.get("results") or []

            token_map = {}
            all_sh_titles = []
            
            # 2. 匹配关键词准备
            parts = target_date.split(' ')
            month_abbr = parts[0].lower()   # "apr"
            day_num = parts[1].lstrip('0')  # "3"

            for mkt in data_list:
                # 获取标题并转为小写进行全扫描
                title = (mkt.get("question") or mkt.get("title") or "").strip()
                if not title: continue
                
                title_lc = title.lower()
                
                # 🔍 核心硬核匹配：必须同时包含 "shanghai" 和 "3" (且排除 2021/2023 等过时年份)
                if "shanghai" in title_lc:
                    all_sh_titles.append(title) # 记录下来供 UI 显示
                    
                    # 只有当标题包含月份(apr/april) 且 包含当天的数字 3 时
                    month_match = (month_abbr in title_lc or "april" in title_lc)
                    day_match = re.search(r'\b' + day_num + r'\b', title_lc)
                    
                    # 额外保险：排除历史年份（如果你在 2026 年，就排除 2023/2021）
                    is_history = any(yr in title_lc for yr in ["2021", "2023", "2024", "2025"])
                    
                    if month_match and day_match and not is_history:
                        logger.info(f"🎯 捕获实时上海气温合约: {title}")
                        
                        # 3. 提取数据
                        outcomes = mkt.get("outcomes")
                        prices = mkt.get("outcomePrices")
                        tokens = mkt.get("clobTokenIds")
                        
                        # 解析 JSON 字符串（如果需要）
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
            logger.error(f"🚨 雷达扫描发生故障: {e}")
            return {}, []

    def get_market_price(self, token_data):
        """
        由于 Gamma API 已经自带了价格，这个函数可以作为备用或直接返回已有价格
        """
        if isinstance(token_data, dict):
            return token_data.get("price")
        return None
