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
        全量扫描模式：不再依赖 API 搜索，直接从活跃池中筛选最新的气温合约
        """
        try:
            # 1. 扩大范围：抓取 200 个活跃市场，按成交量降序排列
            # 气温合约通常成交非常活跃，按 volume24hr 排序能让它排在前面
            params = {
                "active": "true",
                "limit": 200,
                "closed": "false",
                "order": "volume24hr", 
                "ascending": "false"
            }
            logger.info(f"--- 🛰️ 启动全量扫描 (目标日期: {target_date}) ---")
            
            resp = requests.get(self.gamma_url, params=params, timeout=10)
            result = resp.json()
            
            # 结构兼容性处理
            data_list = result if isinstance(result, list) else result.get("data", [])
            
            token_map = {}
            all_sh_titles = []
            
            # 2. 匹配关键词准备 (例如 "Apr", "3")
            parts = target_date.split(' ')
            month_abbr = parts[0].lower()   # "apr"
            day_num = parts[1].lstrip('0')  # "3"

            for mkt in data_list:
                # 获取标题（Gamma 优先看 question 字段）
                title = (mkt.get("question") or mkt.get("title") or "").strip()
                if not title: continue
                
                title_lc = title.lower()
                
                # 🔍 核心逻辑：必须包含 "shanghai" 且排除历史年份
                if "shanghai" in title_lc:
                    # 排除 2021/2023/2024 等历史干扰项
                    is_history = any(yr in title_lc for yr in ["2021", "2023", "2024", "2025"])
                    if is_history: continue
                    
                    all_sh_titles.append(title)
                    
                    # 模糊匹配：包含 (Apr 或 April) 且 包含数字 3
                    month_match = (month_abbr in title_lc or "april" in title_lc)
                    day_match = re.search(r'\b' + day_num + r'\b', title_lc)
                    
                    if month_match and day_match:
                        logger.info(f"🎯 成功锁定实时合约: {title}")
                        
                        # 3. 提取数据（处理可能的字符串格式 JSON）
                        def get_field(key):
                            val = mkt.get(key, [])
                            return json.loads(val) if isinstance(val, str) else val

                        outcomes = get_field("outcomes")
                        prices = get_field("outcomePrices")
                        tokens = get_field("clobTokenIds")
                        
                        for i in range(len(outcomes)):
                            label = outcomes[i]
                            # 提取价格（字符串转浮点）
                            try:
                                p = float(prices[i]) if i < len(prices) else 0.0
                            except: p = 0.0
                            
                            t_id = tokens[i] if i < len(tokens) else ""
                            token_map[label] = {"token_id": t_id, "price": p}
                        
                        return token_map, all_sh_titles
            
            return {}, all_sh_titles

        except Exception as e:
            logger.error(f"🚨 扫描器崩溃: {e}")
            return {}, []

    def get_market_price(self, token_data):
        """
        由于 Gamma API 已经自带了价格，这个函数可以作为备用或直接返回已有价格
        """
        if isinstance(token_data, dict):
            return token_data.get("price")
        return None
