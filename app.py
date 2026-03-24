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
    with open("cache.json", "w") as f:
        json.dump(data, f)

# ======================
# 历史记录（模型验证）
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

def record_today_result(data, pred):
    history = load_history()
    today_str = now_local().strftime("%Y-%m-%d")

    if any(x["date"] == today_str for x in history):
        return

    if len(data) < 5:
        return

    actual_max = max(x["temp"] for x in data)

    history.append({
        "date": today_str,
        "pred": pred,
        "actual": actual_max,
        "error": abs(pred - actual_max)
    })

    save_history(history)

# ======================
# 初始化历史METAR（关键）
# ======================
def init_today_history():
    data = load_cache()

    if len(data) > 5:
        return data

    try:
        now = datetime.utcnow()
        start = now.replace(hour=0, minute=0, second=0)

        url = "https://aviationweather.gov/adds/dataserver_current/httpparam"

        params = {
            "dataSource": "metars",
            "requestType": "retrieve",
            "format": "json",
            "stationString": "ZSPD",
            "startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endTime": now.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        res = requests.get(url, params=params, timeout=10).json()

        if "METAR" not in res:
            return data

        new_data = []

        for item in res["METAR"]:
            raw = item.get("raw_text", "")
            temp = item.get("temp_c", None)
            obs_time = item.get("observation_time", "")

            if temp is None or not obs_time:
                continue

            dt = datetime.strptime(obs_time, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)

            new_data.append({
                "metar_time": dt.strftime("%d%H%M"),
                "time": dt.strftime("%Y-%m-%d %H:%M"),
                "temp": int(temp),
                "raw": raw
            })

        new_data = sorted(new_data, key=lambda x: x["time"])

        save_cache(new_data)
        return new_data

    except:
        return data

# ======================
# 实时更新
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
# 见顶概率模型
# ======================
def peak_probability(data):
    if len(data) < 5:
        return 0

    temps = [x["temp"] for x in data[-5:]]

    speed1 = temps[-1] - temps[-2]
    speed2 = temps[-2] - temps[-3]
    speed3 = temps[-3] - temps[-4]

    avg_speed = (speed1 + speed2 + speed3) / 3 * 2
    acc = speed1 - speed2

    up_moves = sum([temps[i] > temps[i-1] for i in range(1, 5)])
    trend_consistency = up_moves / 4

    today_max = max(x["temp"] for x in data)
    position = temps[-1] / today_max if today_max > 0 else 0

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
# 预测最高温（用于验证）
# ======================
def predict_max_temp(data):
    if len(data) < 3:
        return data[-1]["temp"]

    current = data[-1]["temp"]
    speed = calc_speed(data)

    if speed > 1:
        return current + 2
    elif speed > 0:
        return current + 1
    else:
        return current

# ======================
# UI
# ======================
st.title("🌡️ METAR监控系统（验证版）")
st.caption(f"页面刷新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}")

# 初始化历史
data = init_today_history()
data, is_new = get_today_data()

if not data:
    st.warning("⏳ 等待数据")
    st.stop()

if is_new:
    st.success("🆕 新数据")
    st.audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg", autoplay=True)

current = data[-1]
max_temp = max(x["temp"] for x in data)

# 当前
st.subheader("🌡️ 当前")
st.metric("当前温度", f"{current['temp']}°C")
st.metric("今日最高温", f"{max_temp}°C")
st.write(f"更新时间：{current['time']}")

# 曲线
st.subheader("📈 温度曲线")
df = pd.DataFrame(data)
df["time"] = pd.to_datetime(df["time"])
st.line_chart(df.set_index("time")["temp"])

# ===== 见顶概率 =====
st.subheader("⚠️ 见顶风险")

prob = peak_probability(data)
st.metric("见顶概率", f"{prob}%")
st.progress(prob / 100)

# ===== 判断依据（修复版）=====
st.subheader("📊 判断依据")

if len(data) < 5:
    st.warning("数据不足（至少5条）")
else:
    temps = [x["temp"] for x in data[-5:]]

    speed = (temps[-1] - temps[-2]) * 2
    acc = (temps[-1] - temps[-2]) - (temps[-2] - temps[-3])

    st.write(f"升温速度：{speed:.2f} °C/h")

    if acc < 0:
        st.write("趋势：⚠️ 减速")
    else:
        st.write("趋势：🔥 稳定")

    st.write(f"时间：{get_hour()}点")
    st.write(f"天气：{weather_to_cn(get_weather_state(current['raw']))}")

# ===== 模型验证 =====
pred = predict_max_temp(data)
record_today_result(data, pred)

st.subheader("📊 模型历史表现")

history = load_history()

if history:
    df_hist = pd.DataFrame(history)
    st.dataframe(df_hist)

    st.metric("平均误差", f"{df_hist['error'].mean():.2f}°C")
    st.line_chart(df_hist.set_index("date")[["pred", "actual"]])
else:
    st.info("暂无历史数据")