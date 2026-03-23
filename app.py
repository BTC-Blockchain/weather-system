import streamlit as st
import requests
import pandas as pd
import json
import re
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

st.set_page_config(page_title="天气交易系统", layout="centered")

# 自动刷新（30秒）
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
# METAR实时累积（核心）
# ======================
def get_today_data():
    data = load_cache()

    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=5).text

        metar = txt.split("\n")[1]

        # 提取时间 & 温度
        time_match = re.search(r'(\d{6})Z', metar)
        temp_match = re.search(r' (\d{2})/(\d{2}) ', metar)

        if not time_match or not temp_match:
            return data

        metar_time = time_match.group(1)  # 如 230830
        temp = int(temp_match.group(1))

        # 转 HH:MM
        hhmm = metar_time[2:4] + ":" + metar_time[4:6]

        # 去重（关键）
        if len(data) > 0 and data[-1]["metar_time"] == metar_time:
            return data

        # 新数据写入
        data.append({
            "metar_time": metar_time,
            "time": hhmm,
            "temp": temp
        })

        save_cache(data)

    except:
        pass

    return data

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
st.title("🌡️ 自动天气交易系统（最终稳定版）")

data = get_today_data()

if not data:
    st.warning("⏳ 等待METAR数据积累（刚启动时正常）")
    st.stop()

current_temp = data[-1]["temp"]
max_temp = max(x["temp"] for x in data)

speed = calc_speed(data)
peak = is_peaking(data)

market = get_market_data()

# 当前
st.subheader("🌡️ 当前数据")
st.metric("当前温度", f"{current_temp}°C")
st.metric("今日最高温", f"{max_temp}°C")

# 曲线
st.subheader("📈 温度曲线（实时累积）")
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

    model = model_probs(current_temp, speed, market.keys())

    st.subheader("🧠 模型概率")
    for k in model:
        st.write(f"{k}°C → {model[k]*100:.1f}%")

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
else:
    st.warning("⚠️ 市场数据加载中...")

st.caption("数据源：METAR（ZSPD）+ Polymarket | 自动刷新30秒")