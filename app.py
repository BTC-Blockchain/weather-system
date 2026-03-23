import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

st.set_page_config(page_title="天气交易系统", layout="centered")

# 自动刷新
st_autorefresh(interval=30000, key="refresh")

# ======================
# METAR 历史数据
# ======================
def get_today_metar():
    try:
        url = "https://aviationweather.gov/api/data/metar?ids=ZSPD&format=json&hours=24"
        return requests.get(url, timeout=10).json()
    except:
        return []

def filter_today(data):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    result = []
    for x in data:
        obs = str(x.get("obsTime", ""))
        if today in obs:
            result.append(x)
    return result

def parse_metar_list(data):
    result = []
    for item in data:
        try:
            temp = item.get("temp")
            obs = str(item.get("obsTime", ""))
            if temp is None or len(obs) < 16:
                continue
            time = obs[11:16]
            result.append({"time": time, "temp": temp})
        except:
            continue

    result.sort(key=lambda x: x["time"])
    return result

def get_today_data():
    raw = get_today_metar()
    today = filter_today(raw)
    return parse_metar_list(today)

# ======================
# Polymarket 数据
# ======================
def get_polymarket():
    try:
        url = "https://gamma-api.polymarket.com/markets"
        return requests.get(url, timeout=10).json()
    except:
        return []

def find_shanghai_market(markets):
    for m in markets:
        q = m.get("question", "")
        if "Highest temperature in Shanghai" in q:
            return m
    return None

def parse_outcomes(market):
    outcomes = market.get("outcomes", [])
    result = {}

    for o in outcomes:
        name = o.get("name", "")
        price = o.get("price", 0)

        try:
            # 提取数字（支持 ≥ ≤ 情况）
            num = ''.join(filter(str.isdigit, name))
            if num:
                result[num] = float(price)
        except:
            continue

    return result

def get_market_data():
    markets = get_polymarket()
    m = find_shanghai_market(markets)
    if not m:
        return {}
    return parse_outcomes(m)

# ======================
# 分析
# ======================
def calc_speed(data):
    if len(data) < 2:
        return 0
    return (data[-1]["temp"] - data[-2]["temp"]) * 2

def is_peaking(data):
    if len(data) < 3:
        return False
    return (data[-1]["temp"] - data[-2]["temp"]) < (data[-2]["temp"] - data[-3]["temp"])

def kelly(p, m):
    if m <= 0:
        return 0
    b = (1/m) - 1
    q = 1 - p
    f = (b*p - q) / b
    return max(f * 0.3, 0)

def model_probs(temp, speed, keys):
    result = {}
    for k in keys:
        t = int(k)
        diff = abs(t - temp)
        prob = max(0.1, 1 - diff * 0.3)

        if speed > 1 and t > temp:
            prob += 0.2

        result[k] = min(prob, 0.9)

    total = sum(result.values())
    for k in result:
        result[k] /= total

    return result

# ======================
# UI
# ======================
st.title("🌡️ 自动天气交易系统（实盘版）")

data = get_today_data()

if not data:
    st.error("❌ 未获取到天气数据")
    st.stop()

current_temp = data[-1]["temp"]
max_temp = max(x["temp"] for x in data)

speed = calc_speed(data)
peak = is_peaking(data)

market = get_market_data()

if not market:
    st.error("❌ 未获取到市场数据")
    st.stop()

model = model_probs(current_temp, speed, market.keys())

# 当前
st.subheader("🌡️ 当前数据")
st.metric("当前温度", f"{current_temp}°C")
st.metric("今日最高温", f"{max_temp}°C")

# 曲线
st.subheader("📈 温度曲线")
df = pd.DataFrame(data)
st.line_chart(df.set_index("time")["temp"])

# 趋势
st.subheader("📊 趋势分析")
st.metric("升温速度", f"{speed:.2f} °C/h")

if peak:
    st.warning("⚠️ 接近峰值")
else:
    st.success("🔥 仍在上升")

# 市场
st.subheader("📡 市场（Polymarket）")
for k in market:
    st.write(f"{k}°C → {market[k]*100:.1f}%")

# 模型
st.subheader("🧠 模型概率")
for k in model:
    st.write(f"{k}°C → {model[k]*100:.1f}%")

# 交易
st.subheader("💰 交易建议")

best = None
best_edge = -999

for k in model:
    edge = model[k] - market[k]
    bet = min(kelly(model[k], market[k]) * 10000, 2000)

    if edge > best_edge:
        best_edge = edge
        best = k

    st.write(f"{k}°C → Edge {edge*100:.1f}% | ${bet:.0f}")

if best_edge > 0.05:
    st.success(f"🔥 建议下注：{best}°C")
else:
    st.warning("⚠️ 暂无机会")

st.caption("数据源：METAR + Polymarket | 自动刷新30秒")