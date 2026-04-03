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
        自动发现：根据日期模糊搜索上海气温市场（修复全称/缩写兼容性）
        :param target_date: 传入格式如 "Apr 3"
        :return: (token_map, found_titles) -> 返回匹配到的ID字典和搜到的所有相关标题列表
        """
        try:
            # 1. 扩大搜索范围：获取所有当前活跃的市场，增加 limit 确保不被截断
            params = {"limit": 100, "active": "true"}
            logger.info(f"--- 启动市场扫描: 目标日期 [{target_date}] ---")
            
            resp = requests.get(self.search_url, params=params, timeout=10)
            all_markets = resp.json()
            
            token_map = {}
            all_shanghai_titles = []  # 用于存储搜到的所有上海市场，供 UI 调试显示
            market_found = False
            
            # 2. 准备模糊匹配的关键词
            # 从 "Apr 3" 中提取 "Apr" 和 "3"
            parts = target_date.split(' ')
            month_abbr = parts[0]   # 例如 "Apr"
            day_num = parts[1].lstrip('0')    # 例如 "3"

            # 建立月份映射表，解决 Apr -> April 的匹配问题
            month_full_map = {
                "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April",
                "May": "May", "Jun": "June", "Jul": "July", "Aug": "August",
                "Sep": "September", "Oct": "October", "Nov": "November", "Dec": "December"
            }
            month_full = month_full_map.get(month_abbr, month_abbr)

            for mkt in all_markets.get("data", []):
                title = mkt.get("title", "")
                
                # 第一层过滤：必须包含 "Shanghai"
                if "Shanghai" in title:
                    all_shanghai_titles.append(title)
                    logger.info(f"🔍 发现上海相关合约: {title}")
                    
                    # 第二层模糊匹配逻辑优化：
                    # A. 月份匹配：标题中包含简写 "Apr" 或 全称 "April"
                    month_match = (month_abbr in title or month_full in title)
                    
                    # B. 日期精确匹配：使用正则表达式确保匹配到独立的数字 3
                    # \b 代表单词边界，防止 "3" 匹配到 "13", "23" 或 "30"
                    day_match = re.search(r'\b' + day_num + r'\b', title)
                    
                    if month_match and day_match:
                        market_found = True
                        logger.info(f"🎯 模糊匹配成功 (全称/缩写兼容): {title}")
                        
                        # 解析 Outcome 和 Token ID
                        import json
                        outcomes = json.loads(mkt.get("outcomes", "[]"))
                        token_ids = json.loads(mkt.get("clobTokenIds", "[]"))
                        
                        # 将结果存入映射表
                        for i in range(len(outcomes)):
                            token_map[outcomes[i]] = token_ids[i]
                        
                        # 找到第一个匹配的市场后停止扫描
                        break
            
            if not market_found:
                logger.warning(f"❌ 扫描结束：未能匹配到日期格式，系统生成为 '{month_abbr}/{month_full} {day_num}'")
            
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
