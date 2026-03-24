import streamlit as st
import requests
import pandas as pd
import json
import re
import math
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

st.set_page_config(page_title="METAR监控系统", layout="wide")
st_autorefresh(interval=30000, key="refresh")

# ======================
# 时间
# ======================
def now_local():
    return datetime.utcnow() + timedelta(hours=8)

def utc_to_local(utc_str):
    day = int(utc_str[:2])
    hour = int(utc_str[2:4])
    minute = int(utc_str[4:6])
    now = datetime.utcnow()
    dt = datetime(now.year, now.month, day, hour, minute)
    return dt + timedelta(hours=8)

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
    with open("cache.json", "w") as f:
        json.dump(data, f)

# ======================
# 历史
# ======================
def load_history():
    try:
        with open("history.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_history(data):
    with open("history.json", "w") as f:
        json.dump(data, f)

# ======================
# 天气解析
# ======================
def parse_weather_features(metar):
    metar = metar.upper()

    rain = 1 if "RA" in metar else 0

    cloud = 0
    if "OVC" in metar:
        cloud = 1
    elif "BKN" in metar:
        cloud = 0.7
    elif "SCT" in metar:
        cloud = 0.4
    elif "FEW" in metar:
        cloud = 0.2

    wind_match = re.search(r'(\d{2})KT', metar)
    wind = int(wind_match.group(1)) if wind_match else 0

    return {"rain": rain, "cloud": cloud, "wind": wind}

def get_weather_state(metar):
    metar = metar.upper()
    if "RA" in metar:
        return "🌧️ 下雨"
    elif "OVC" in metar or "BKN" in metar:
        return "☁️ 阴天"
    elif "CLR" in metar or "FEW" in metar:
        return "☀️ 晴天"
    else:
        return "❓ 未知"

# ======================
# 数据初始化（简化版保留稳定）
# ======================
def get_today_data():
    data = load_cache()
    is_new = False

    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=5).text
        metar = txt.strip().split("\n")[1]

        t = re.search(r'(\d{6})Z', metar)
        temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)

        if t and temp_match:
            metar_time = t.group(1)
            temp = int(temp_match.group(1).replace("M", "-"))
            dt = utc_to_local(metar_time)

            if len(data) == 0 or data[-1]["metar_time"] != metar_time:
                is_new = True
                data.append({
                    "metar_time": metar_time,
                    "time": dt.strftime("%Y-%m-%d %H:%M"),
                    "temp": temp,
                    "raw": metar
                })
                save_cache(data)
    except:
        pass

    return data, is_new

# ======================
# 模型（含强制见顶）
# ======================
def peak_probability(data):
    if len(data) < 5:
        return 0

    # ===== 强制见顶 =====
    if len(data) >= 3:
        t1 = data[-1]["temp"]
        t2 = data[-2]["temp"]
        if t1 < t2:
            return 95

    temps = [x["temp"] for x in data[-5:]]

    speed1 = temps[-1] - temps[-2]
    speed2 = temps[-2] - temps[-3]
    acc = speed1 - speed2

    today_max = max(x["temp"] for x in data)
    position = temps[-1] / today_max if today_max else 0

    weather = parse_weather_features(data[-1]["raw"])

    score = 0
    score += max(0, -acc) * 30
    score += position * 20
    score += weather["rain"] * 20
    score += weather["cloud"] * 15
    score += min(weather["wind"]/10, 1) * 15

    return min(round(score), 100)

# ======================
# UI
# ======================
st.title("🌡️ METAR监控系统（终极版）")
st.caption(f"刷新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}")

data, is_new = get_today_data()

if not data:
    st.warning("等待数据")
    st.stop()

current = data[-1]
max_temp = max(x["temp"] for x in data)

# ===== 三栏 =====
col1, col2, col3 = st.columns([1,1.2,1])

# ================= 左
with col1:
    prob = peak_probability(data)

    st.subheader("见顶概率")
    st.metric("概率", f"{prob}%")
    st.progress(prob/100)

    st.subheader("📊 概率解释")

    if len(data) >= 2:
        temps = [x["temp"] for x in data]

        t1 = pd.to_datetime(data[-1]["time"])
        t2 = pd.to_datetime(data[-2]["time"])
        minutes = (t1 - t2).total_seconds()/60
        speed = (temps[-1]-temps[-2])/minutes*60 if minutes>0 else 0

        if temps[-1] < temps[-2]:
            st.write("🔻 已下降（已见顶）")
        else:
            st.write("📈 仍在变化中")

        st.write(f"📈 速度：{speed:.2f} °C/小时")

        weather = parse_weather_features(current["raw"])
        st.write("🌦️ 天气因素")
        st.write(f"🌧️ {'有降雨' if weather['rain'] else '无降雨'}")
        st.write(f"☁️ 云量：{weather['cloud']}")
        st.write(f"💨 风速：{weather['wind']}KT")

    st.subheader("🚨 信号提醒")

    reasons = []
    if len(data) >= 2:
        if data[-1]["temp"] < data[-2]["temp"]:
            reasons.append("温度下降")

    if prob >= 90:
        st.error("🔴 强卖")
        st.write("原因："+" + ".join(reasons))
    elif prob > 60:
        st.warning("🟡 接近顶部")
    else:
        st.success("🟢 上升趋势")

# ================= 中
with col2:
    st.subheader("当前")
    st.metric("温度", f"{current['temp']}°C")
    st.metric("今日最高", f"{max_temp}°C")
    st.write(current["time"])
    st.write(get_weather_state(current["raw"]))

    st.subheader("温度曲线")
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    st.line_chart(df.set_index("time")["temp"])

# ================= 右
with col3:
    st.subheader("📋 历史数据")
    df_table = pd.DataFrame(data)
    df_table["time"] = pd.to_datetime(df_table["time"])
    df_table = df_table.sort_values(by="time", ascending=False)

    st.dataframe(df_table)

    st.subheader("📡 最近METAR")
    for row in reversed(data[-5:]):
        st.code(row["raw"])

st.caption("数据来源：METAR（ZSPD） | 自动刷新30秒 | 声音提醒 | 见顶模型 | Design by Kylin")