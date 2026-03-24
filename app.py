import streamlit as st
import requests
import pandas as pd
import json
import re
import math
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

st.set_page_config(page_title="METAR监控系统", layout="centered")

# 自动刷新
st_autorefresh(interval=30000, key="refresh")

# ======================
# 时间工具
# ======================
def utc_to_local(utc_str):
    day = int(utc_str[:2])
    hour = int(utc_str[2:4])
    minute = int(utc_str[4:6])

    now = datetime.utcnow()
    utc_dt = datetime(now.year, now.month, day, hour, minute)
    local_dt = utc_dt + timedelta(hours=8)

    return local_dt

def now_local():
    return datetime.utcnow() + timedelta(hours=8)

# ======================
# 天气中文
# ======================
def weather_to_cn(state):
    mapping = {
        "rain": "🌧️ 下雨",
        "cloudy": "☁️ 多云/阴天",
        "clear": "☀️ 晴天",
        "unknown": "❓ 未知"
    }
    return mapping.get(state, "❓ 未知")

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
    is_new = False

    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=5).text

        lines = txt.strip().split("\n")
        if len(lines) < 2:
            return data, False

        metar = lines[1]

        time_match = re.search(r'(\d{6})Z', metar)
        temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)

        if not time_match or not temp_match:
            return data, False

        metar_time = time_match.group(1)
        temp_str = temp_match.group(1)
        temp = int(temp_str.replace("M", "-"))

        local_dt = utc_to_local(metar_time)
        time_str = local_dt.strftime("%Y-%m-%d %H:%M")

        if len(data) == 0 or data[-1]["metar_time"] != metar_time:
            is_new = True
            data.append({
                "metar_time": metar_time,
                "time": time_str,
                "temp": temp,
                "raw": metar
            })
            save_cache(data)

    except:
        pass

    return data, is_new

# ======================
# 分析模块
# ======================
def calc_speed(data):
    if len(data) < 2:
        return 0
    return (data[-1]["temp"] - data[-2]["temp"]) * 2

def get_hour():
    return now_local().hour

def get_weather_state(metar):
    metar = metar.upper()
    if "RA" in metar:
        return "rain"
    elif "OVC" in metar or "BKN" in metar:
        return "cloudy"
    elif "CLR" in metar or "FEW" in metar or "NSC" in metar:
        return "clear"
    else:
        return "unknown"

# ======================
# ⭐ 核心：稳定版见顶概率模型
# ======================
def peak_probability(data):
    if len(data) < 5:
        return 0

    temps = [x["temp"] for x in data[-5:]]
    t1, t2, t3, t4, t5 = temps

    # 平滑速度
    speed1 = t5 - t4
    speed2 = t4 - t3
    speed3 = t3 - t2
    avg_speed = (speed1 + speed2 + speed3) / 3 * 2

    # 加速度
    acc = speed1 - speed2

    # 趋势一致性
    up_moves = sum([temps[i] > temps[i-1] for i in range(1, 5)])
    trend_consistency = up_moves / 4

    # 位置
    today_max = max(x["temp"] for x in data)
    position = t5 / today_max if today_max > 0 else 0

    # 时间
    hour = get_hour()
    time_factor = 1 / (1 + math.exp(-(hour - 13)))

    score = 0
    score += max(0, (1 - avg_speed / 3)) * 25
    score += max(0, -acc) * 25
    score += (1 - trend_consistency) * 15
    score += position * 15
    score += time_factor * 20

    return min(round(score), 100)

# ======================
# UI
# ======================
st.title("🌡️ METAR监控系统（专业版）")

st.caption(f"页面刷新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}")

data, is_new = get_today_data()

if not data:
    st.warning("⏳ 等待数据积累")
    st.stop()

# 新数据提醒
if is_new:
    st.success("🆕 检测到新的 METAR 数据！")
    st.audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg", autoplay=True)

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

# ======================
# 🔥 见顶概率模块（重点）
# ======================
st.subheader("⚠️ 见顶风险评估")

prob = peak_probability(data)

col1, col2 = st.columns(2)

with col1:
    st.metric("见顶概率", f"{prob}%")

with col2:
    if prob < 30:
        st.success("🔥 强势上升中")
    elif prob < 60:
        st.warning("🟡 接近顶部")
    else:
        st.error("🔴 高风险见顶区")

st.progress(prob / 100)

# ===== 解释 =====
st.subheader("📊 判断依据")

temps = [x["temp"] for x in data[-5:]]

speed = (temps[-1] - temps[-2]) * 2
acc = (temps[-1] - temps[-2]) - (temps[-2] - temps[-3])

st.write(f"升温速度：{speed:.2f} °C/h")

if acc < 0:
    st.write("趋势变化：⚠️ 上升动力减弱（减速）")
else:
    st.write("趋势变化：🔥 上升动力稳定")

hour = get_hour()
st.write(f"时间位置：{hour}:00")

weather = get_weather_state(current["raw"])
st.write(f"天气影响：{weather_to_cn(weather)}")

# 最近趋势
st.subheader("📈 最近趋势（5个数据点）")
df_last = pd.DataFrame(data[-5:])
df_last["time"] = pd.to_datetime(df_last["time"])
st.line_chart(df_last.set_index("time")["temp"])

# 数据表
st.subheader("📋 历史数据")
st.dataframe(pd.DataFrame(data), use_container_width=True)

# METAR
st.subheader("📡 最近METAR")
for row in reversed(data[-5:]):
    st.text(f"{row['time']} → {row['raw']}")

st.caption("数据来源：METAR（ZSPD） | 自动刷新30秒 | 声音提醒 | 专业见顶模型")