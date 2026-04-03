# engine.py  逻辑层，封装“盈利逻辑”（概率、信号、凯利公式）
import numpy as np

class QuantEngine:
    @staticmethod
    def calculate_combined_prob(ensemble_members, current_max, current_temp, current_hour):
        """
        核心概率算法：结合【盘前集合预报】与【日内实时监控】
        """
        # 1. 如果没有集合数据，使用正态分布兜底；如果有，则以集合数据为基准
        if not ensemble_members:
            # 兜底方案：基于常识的日内分布
            base_preds = np.random.normal(current_temp + 1.0, 1.5, 1000)
        else:
            base_preds = np.array(ensemble_members)

        # 2. 贝叶斯修正：如果当前已经达到的最高温超过了某些模型的预测，那些模型失效
        # 最终最高温预测 = max(当前实测最高温, 模型预测值)
        final_preds = np.maximum(current_max, base_preds)
        
        # 3. 时间衰减因子：如果过了 15:00，温度进一步大幅上升的概率降低
        if current_hour > 15.0:
            # 这种精细化的调整是盈利的关键
            final_preds = np.where(final_preds > current_max, current_max + (final_preds - current_max)*0.3, final_preds)

        return final_preds

    @staticmethod
    def get_kelly_signals(true_probs, market_prices, capital=10000):
        """
        凯利公式信号生成器
        true_probs: {'29°C': 0.6, ...}
        market_prices: {'29°C': 0.45, ...} (从Polymarket获取的价格)
        """
        signals = []
        for bucket, p_true in true_probs.items():
            p_mkt = market_prices.get(bucket, 0.5)
            # 计算期望值 EV = (胜率 * 净赔率) - 败率
            ev = (p_true * (1 - p_mkt)) - ((1 - p_true) * p_mkt)
            
            if ev > 0.05: # 只做 EV > 5% 的交易
                # 凯利比例 = (bp - q) / b = (p_true - p_mkt) / (1 - p_mkt)
                f_star = (p_true - p_mkt) / (1 - p_mkt)
                bet_amount = capital * f_star * 0.25 # 0.25 是安全系数 (Fractional Kelly)
                
                signals.append({
                    "bucket": bucket,
                    "ev": ev,
                    "bet": bet_amount,
                    "desc": "✅ 正期望收益，建议买入"
                })
        return signals