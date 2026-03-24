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
# ⭐ 初始化历史数据（关键）
# ======================
def init_today_history():
    try:
        url = "https://aviationweather.gov/api/data/metar"
        params = {"ids": "ZSPD", "format": "json", "hours": 24}

        res = requests.get(url, params=params, timeout=10)
        metars = res.json()

        data = []
        for m in metars:
            temp = m.get("temp") or m.get("temp_c")
            raw = m.get("rawOb") or m.get("raw_text")
            obs = m.get("obsTime") or m.get("observation_time")

            if temp and obs:
                try:
                    dt = datetime.strptime(obs, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                except:
                    continue

                if dt.date() == now_local().date():
                    data.append({
                        "metar_time": dt.strftime("%d%H%M"),
                        "time": dt.strftime("%Y-%m-%d %H:%M"),
                        "temp": int(temp),
                        "raw": raw
                    })

        data = sorted(data, key=lambda x: x["time"])

        if data:
            save_cache(data)
            return data
    except:
        pass

    return load_cache()

# ======================
# 实时数据
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
    if "RA" in metar:
        return "🌧️ 下雨"
    elif "OVC" in metar or "BKN" in metar:
        return "☁️ 阴天"
    elif "FEW" in metar or "CLR" in metar:
        return "☀️ 晴天"
    return "❓ 未知"

# ======================
# 模型
# ======================
def peak_probability(data):
    if len(data) < 5:
        return 0

    if data[-1]["temp"] < data[-2]["temp"]:
        return 95

    temps = [x["temp"] for x in data[-5:]]
    acc = (temps[-1] - temps[-2]) - (temps[-2] - temps[-3])

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
# 启动（关键顺序）
# ======================
data = init_today_history()
data, is_new = get_today_data()

if not data:
    st.warning("等待数据")
    st.stop()

current = data[-1]
max_temp = max(x["temp"] for x in data)

# ======================
# 标题
# ======================
st.markdown(
    f"""
    <div style='text-align: center; padding: 10px 0;'>
        <h1>🌡️ METAR监控系统</h1>
        <div style='font-size:14px;color:gray;'>实时气象监控 · 见顶概率分析 · 信号决策系统</div>
        <div style='font-size:12px;color:#999;'>更新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}</div>
        <div style='font-size:12px;color:#aaa;'>数据来源：METAR(ZSPD) ｜自动刷新｜Design by Kylin</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("<hr>", unsafe_allow_html=True)

# 声音提示
if is_new:
    st.success("🟢 新数据已更新")
    st.audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg", autoplay=True)

# ======================
# 三栏布局
# ======================
col1, col2, col3 = st.columns([1,1.2,1])

# 左
with col1:
    prob = peak_probability(data)
    st.subheader("见顶概率")
    st.metric("概率", f"{prob}%")
    st.progress(prob/100)

# 中
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

    st.info("📌 夜间无METAR数据属正常")

    # 数据完整性
    st.subheader("🧩 数据完整性")
    if len(data) > 5:
        st.success("数据正常")

# 右
with col3:
    st.subheader("📋 历史数据")
    st.dataframe(pd.DataFrame(data))

    st.subheader("📡 最近METAR")
    for row in reversed(data[-5:]):
        st.code(row["raw"])