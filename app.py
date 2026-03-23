import streamlit as st
import requests
import pandas as pd
import json
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

st.set_page_config(page_title="天气交易系统", layout="centered")

# 自动刷新
st_autorefresh(interval=30000, key="refresh")

# ======================
# 缓存
# ======================
def load_cache():
    try:
        with open("cache.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_cache(data):
    try:
        with open("cache.json", "w") as f:
            json.dump(data, f)
    except:
        pass

# ======================
# 天气数据（带缓存）
# ======================
def get_today_data():
    data = []

    # ===== 主API =====
    try:
        url = "https://aviationweather.gov/api/data/metar?ids=ZSPD&format=json&hours=24"
        res = requests.get(url, timeout=10)

        if res.status_code == 200:
            raw = res.json()
        else:
            raw = []
    except:
        raw = []

    # ===== 解析 =====
    for item in raw:
        try:
            temp = item.get("temp")
            obs = str(item.get("obsTime", ""))

            if temp is None or len(obs) < 16:
                continue

            time = obs[11:16]

            data.append({
                "time": time,
                "temp": temp
            })
        except:
            continue

    # ===== 成功 → 更新缓存 =====
    if len(data) > 0:
        save_cache(data)
        return data

    # ===== 失败 → 用缓存 =====
    cached = load_cache()
    if len(cached) > 0:
        return cached

    # ===== 兜底 =====
    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=5).text

        import re
        temp_match = re.search(r' (\d{2})/(\d{2}) ', txt)

        if temp_match:
            temp = int(temp_match.group(1))
            now = datetime.utcnow().strftime("%H:%M")

            return [{"time": now, "temp": temp}]
    except:
        pass

    return []

# ======================
# Polymarket
# ======================
def get_polymarket():
    try:
        url = "https://gamma-api.polymarket.com/markets"
        return requests.get(url, timeout=10).json()
    except:
        return []

def find_shanghai_market(markets):
    for m in markets:
        if "Highest temperature in Shanghai" in m.get("question", ""):
            return m
    return None

def parse_outcomes(market):
    outcomes = market.get("outcomes", [])
    result = {}

    for o in outcomes:
        name = o.get("name", "")
        price = o.get("price", 0)

        try:
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
st.title("🌡️ 自动天气交易系统（稳定版）")

data = get_today_data()

if not data:
    st.error("❌ 无可用天气数据（API + 缓存均失败）")
    st.stop()

current_temp = data[-1]["temp"]
max_temp = max(x["temp"] for x in data)

speed = calc_speed(data)
peak = is_peaking(data)

market = get_market_data()

if not market:
    st.warning("⚠️ 未获取到市场数据（稍后重试）")
    market = {}

model = model_probs(current_temp, speed, market.keys()) if market else {}

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
if market:
    st.subheader("📡 市场（Polymarket）")
    for k in market:
        st.write(f"{k}°C → {market[k]*100:.1f}%")

# 模型
if model:
    st.subheader("🧠 模型概率")
    for k in model:
        st.write(f"{k}°C → {model[k]*100:.1f}%")

# 交易
if model:
    st.subheader("💰 交易建议")

    best = None
    best_edge = -999

    for k in model:
        edge = model[k] - market.get(k, 0)
        bet = min(kelly(model[k], market.get(k, 0)) * 10000, 2000)

        if edge > best_edge:
            best_edge = edge
            best = k

        st.write(f"{k}°C → Edge {edge*100:.1f}% | ${bet:.0f}")

    if best_edge > 0.05:
        st.success(f"🔥 建议下注：{best}°C")
    else:
        st.warning("⚠️ 暂无机会")

st.caption("数据源：METAR + Polymarket | 自动刷新30秒 | 含缓存容错")