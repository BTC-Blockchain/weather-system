import streamlit as st
import requests
import pandas as pd
import json
import re
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

st.set_page_config(page_title="METAR天气预测系统", layout="centered")

# 自动刷新
st_autorefresh(interval=30000, key="refresh")

# ======================
# 时间工具（关键新增）
# ======================
def utc_to_local(utc_str):
    # 例：241030 → 24日10:30 UTC
    day = int(utc_str[:2])
    hour = int(utc_str[2:4])
    minute = int(utc_str[4:6])

    now = datetime.utcnow()

    utc_dt = datetime(now.year, now.month, day, hour, minute)
    local_dt = utc_dt + timedelta(hours=8)

    return local_dt

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
# METAR数据（升级时间）
# ======================
def get_today_data():
    data = load_cache()

    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=5).text

        lines = txt.strip().split("\n")
        if len(lines) < 2:
            return data

        metar = lines[1]

        time_match = re.search(r'(\d{6})Z', metar)
        temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)

        if not time_match or not temp_match:
            return data

        metar_time = time_match.group(1)

        temp_str = temp_match.group(1)
        temp = int(temp_str.replace("M", "-"))

        # ✅ 转本地时间（关键）
        local_dt = utc_to_local(metar_time)

        time_str = local_dt.strftime("%Y-%m-%d %H:%M")

        if len(data) > 0 and data[-1]["metar_time"] == metar_time:
            return data

        data.append({
            "metar_time": metar_time,
            "time": time_str,
            "temp": temp,
            "raw": metar
        })

        save_cache(data)

    except:
        pass

    return data

# ======================
# 分析模块
# ======================
def calc_speed(data):
    if len(data) < 2:
        return 0
    return (data[-1]["temp"] - data[-2]["temp"]) * 2

def is_peak(data):
    if len(data) < 3:
        return False
    t1 = data[-3]["temp"]
    t2 = data[-2]["temp"]
    t3 = data[-1]["temp"]
    return (t3 <= t2) and (t2 >= t1)

def get_hour():
    return datetime.utcnow().hour + 8

def get_weather_state(metar):
    metar = metar.upper()

    if "RA" in metar:
        return "rain"
    elif "OVC" in metar or "BKN" in metar:
        return "cloudy"
    elif "CLR" in metar or "FEW" in metar:
        return "clear"
    else:
        return "unknown"

def trend_strength(data):
    if len(data) < 4:
        return 0
    temps = [x["temp"] for x in data[-4:]]
    return sum([temps[i] > temps[i-1] for i in range(1, 4)])

def predict_max_temp_v2(data):
    current = data[-1]["temp"]
    speed = calc_speed(data)
    peak = is_peak(data)
    hour = get_hour()
    trend = trend_strength(data)
    weather = get_weather_state(data[-1]["raw"])

    if peak:
        return current

    if hour < 10:
        time_bonus = 2
    elif hour < 14:
        time_bonus = 1
    else:
        time_bonus = 0

    trend_bonus = trend * 0.5

    if speed > 2:
        speed_bonus = 2
    elif speed > 1:
        speed_bonus = 1
    else:
        speed_bonus = 0

    weather_penalty = 0
    if weather == "rain":
        weather_penalty = -2
    elif weather == "cloudy":
        weather_penalty = -1

    pred = current + time_bonus + speed_bonus + trend_bonus + weather_penalty

    return round(pred)

def generate_probs_v2(pred):
    probs = {}
    for t in range(pred - 3, pred + 4):
        diff = abs(t - pred)

        if diff == 0:
            p = 0.35
        elif diff == 1:
            p = 0.25
        elif diff == 2:
            p = 0.15
        else:
            p = 0.05

        probs[t] = p

    total = sum(probs.values())
    for k in probs:
        probs[k] /= total

    return probs

# ======================
# UI
# ======================
st.title("🌡️ METAR天气预测系统（专业时间版）")

data = get_today_data()

if not data:
    st.warning("⏳ 等待数据积累")
    st.stop()

current = data[-1]
max_temp = max(x["temp"] for x in data)

# 当前
st.subheader("🌡️ 当前天气")
st.metric("当前温度", f"{current['temp']}°C")
st.metric("今日最高温", f"{max_temp}°C")
st.write(f"更新时间：{current['time']}")

# 曲线
st.subheader("📈 温度曲线")
df = pd.DataFrame(data)
df["time"] = pd.to_datetime(df["time"])
df = df.sort_values("time")
st.line_chart(df.set_index("time")["temp"])

# 趋势
st.subheader("📊 趋势分析")
speed = calc_speed(data)
st.metric("升温速度", f"{speed:.2f} °C/h")

if is_peak(data):
    st.error("⚠️ 已见顶")
else:
    st.success("🔥 上升中")

# 天气
weather = get_weather_state(current["raw"])
st.write(f"天气状态：{weather}")

# 预测
st.subheader("🧠 今日最高温预测")
pred = predict_max_temp_v2(data)
st.metric("预测最高温", f"{pred}°C")

# 概率
st.subheader("📊 概率分布")
probs = generate_probs_v2(pred)

for t in sorted(probs.keys()):
    st.write(f"{t}°C → {probs[t]*100:.1f}%")

df_prob = pd.DataFrame({
    "temp": list(probs.keys()),
    "prob": list(probs.values())
})
st.bar_chart(df_prob.set_index("temp"))

# 数据表
st.subheader("📋 历史数据（含完整时间）")
st.dataframe(pd.DataFrame(data), use_container_width=True)

# METAR
st.subheader("📡 最近METAR（含时间）")
for row in reversed(data[-5:]):
    st.text(f"{row['time']} → {row['raw']}")

st.caption("数据来源：METAR（ZSPD） | 时间已转换为本地时间（UTC+8）")