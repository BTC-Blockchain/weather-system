import streamlit as st
import requests
import pandas as pd
import json
import re
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
# METAR数据
# ======================
def get_today_data():
    data = load_cache()

    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=5).text
        metar = txt.split("\n")[1]

        time_match = re.search(r'(\d{6})Z', metar)
        temp_match = re.search(r' (\d{2})/(\d{2}) ', metar)

        if not time_match or not temp_match:
            return data

        metar_time = time_match.group(1)
        temp = int(temp_match.group(1))
        hhmm = metar_time[2:4] + ":" + metar_time[4:6]

        if len(data) > 0 and data[-1]["metar_time"] == metar_time:
            return data

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
# Polymarket（Event模式）
# ======================
def get_events():
    try:
        url = "https://gamma-api.polymarket.com/events?search=shanghai"
        res = requests.get(url, timeout=10)

        if res.status_code == 200:
            return res.json()
    except:
        pass

    return []

def find_weather_event(events):
    for e in events:
        title = e.get("title", "").lower()

        if "shanghai" in title and "temperature" in title:
            return e

    return None

def find_today_market(markets):
    now = datetime.utcnow()

    candidates = []

    for m in markets:
        end = m.get("endDate", "")
        active = m.get("active", False)

        if not active or not end:
            continue

        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))

            if end_dt > now:
                candidates.append((end_dt, m))
        except:
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]

# ======================
# 解析市场
# ======================
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

# ======================
# 模型
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
    st.warning("⏳ 等待METAR数据积累")
    st.stop()

current_temp = data[-1]["temp"]
max_temp = max(x["temp"] for x in data)

speed = calc_speed(data)
peak = is_peaking(data)

# ===== 获取市场 =====
events = get_events()
event = find_weather_event(events)

if not event:
    st.error("❌ 未找到上海温度事件（API问题）")
    st.stop()

markets = event.get("markets", [])
market = find_today_market(markets)

st.subheader("📅 当前市场")

if not market:
    st.error("❌ 未找到今日市场")
    st.stop()

st.success("✅ 已匹配今日市场")
st.write(market.get("question"))

# ===== 数据 =====
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

# ===== 市场概率 =====
market_probs = parse_outcomes(market)

st.subheader("📡 市场概率")
for k in market_probs:
    st.write(f"{k}°C → {market_probs[k]*100:.1f}%")

# ===== 模型 =====
model = model_probs(current_temp, speed, market_probs.keys())

st.subheader("🧠 模型概率")
for k in model:
    st.write(f"{k}°C → {model[k]*100:.1f}%")

# ===== 交易 =====
st.subheader("💰 交易建议 + 套利信号")

best = None
best_edge = -999

for k in model:
    edge = model[k] - market_probs.get(k, 0)
    bet = min(kelly(model[k], market_probs.get(k, 0)) * 10000, 2000)

    if edge > best_edge:
        best_edge = edge
        best = k

    signal = ""
    if edge > 0.12:
        signal = "🔥🔥 强套利"
    elif edge > 0.08:
        signal = "🔥 套利"

    st.write(f"{k}°C → Edge {edge*100:.1f}% | ${bet:.0f} {signal}")

# ===== 总结 =====
st.subheader("🚨 今日信号")

if best_edge > 0.12:
    st.error(f"🔥🔥 强套利机会：{best}°C（Edge {best_edge*100:.1f}%）")
elif best_edge > 0.08:
    st.warning(f"🔥 套利机会：{best}°C（Edge {best_edge*100:.1f}%）")
elif best_edge > 0.05:
    st.info(f"⚠️ 弱优势：{best}°C")
else:
    st.success("✅ 无明显套利机会")

st.caption("数据源：METAR（ZSPD）+ Polymarket | 自动刷新30秒")