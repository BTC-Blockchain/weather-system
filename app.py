import streamlit as st
import requests
import pandas as pd
import json
import re
import math
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

st.set_page_config(page_title="METAR监控系统", layout="centered")
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
# 历史记录（验证）
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
    now = now_local()
    today = now.strftime("%Y-%m-%d")

    if now.hour < 18:
        return

    if any(x["date"] == today for x in history):
        return

    if len(data) < 5:
        return

    actual = max(x["temp"] for x in data)

    history.append({
        "date": today,
        "pred": pred,
        "actual": actual,
        "error": abs(pred - actual)
    })

    save_history(history)

# ======================
# 初始化历史数据（修复版）
# ======================
def init_today_history():
    data = load_cache()

    if len(data) > 10:
        return data

    try:
        url = "https://aviationweather.gov/api/data/metar"
        params = {"ids": "ZSPD", "format": "json", "hours": 24}

        res = requests.get(url, params=params, timeout=10)
        if res.status_code != 200:
            return data

        metars = res.json()
        new_data = []

        for item in metars:
            temp = item.get("temp")
            raw = item.get("rawOb")
            obs_time = item.get("obsTime")

            if temp is None or obs_time is None:
                continue

            dt = datetime.utcfromtimestamp(obs_time / 1000) + timedelta(hours=8)

            if dt.date() != now_local().date():
                continue

            new_data.append({
                "metar_time": dt.strftime("%d%H%M"),
                "time": dt.strftime("%Y-%m-%d %H:%M"),
                "temp": int(temp),
                "raw": raw
            })

        new_data = sorted(new_data, key=lambda x: x["time"])

        if new_data:
            save_cache(new_data)
            return new_data

    except:
        pass

    return data

# ======================
# 实时数据
# ======================
def get_today_data():
    data = load_cache()
    is_new = False

    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=5).text

        lines = txt.strip().split("\n")
        metar = lines[1]

        t = re.search(r'(\d{6})Z', metar)
        temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)

        if not t or not temp_match:
            return data, False

        metar_time = t.group(1)
        temp = int(temp_match.group(1).replace("M", "-"))

        dt = utc_to_local(metar_time)
        time_str = dt.strftime("%Y-%m-%d %H:%M")

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
# 数据完整性检测
# ======================
def check_data_integrity(data):
    if len(data) < 2:
        return []

    gaps = []
    for i in range(1, len(data)):
        t1 = pd.to_datetime(data[i-1]["time"])
        t2 = pd.to_datetime(data[i]["time"])
        diff = (t2 - t1).total_seconds() / 60

        if diff > 60:
            gaps.append((data[i-1]["time"], data[i]["time"], int(diff)))

    return gaps

# ======================
# 自动修复（核心）
# ======================
def auto_fix_data(data):
    gaps = check_data_integrity(data)

    if not gaps or len(gaps) > 5:
        return data, False

    try:
        url = "https://aviationweather.gov/api/data/metar"
        params = {"ids": "ZSPD", "format": "json", "hours": 24}

        res = requests.get(url, params=params, timeout=10)
        if res.status_code != 200:
            return data, False

        metars = res.json()
        new_data = []

        for item in metars:
            temp = item.get("temp")
            raw = item.get("rawOb")
            obs_time = item.get("obsTime")

            if temp is None or obs_time is None:
                continue

            dt = datetime.utcfromtimestamp(obs_time / 1000) + timedelta(hours=8)

            if dt.date() != now_local().date():
                continue

            new_data.append({
                "metar_time": dt.strftime("%d%H%M"),
                "time": dt.strftime("%Y-%m-%d %H:%M"),
                "temp": int(temp),
                "raw": raw
            })

        new_data = sorted(new_data, key=lambda x: x["time"])

        if len(new_data) > len(data):
            save_cache(new_data)
            return new_data, True

    except:
        pass

    return data, False

# ======================
# 模型
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

    up = sum([temps[i] > temps[i-1] for i in range(1, 5)])
    consistency = up / 4

    today_max = max(x["temp"] for x in data)
    position = temps[-1] / today_max if today_max else 0

    hour = now_local().hour
    time_factor = 1 / (1 + math.exp(-(hour - 13)))

    score = 0
    score += max(0, (1 - avg_speed/3)) * 25
    score += max(0, -acc) * 25
    score += (1 - consistency) * 15
    score += position * 15
    score += time_factor * 20

    return min(round(score), 100)

def predict_max_temp(data):
    if len(data) < 3:
        return data[-1]["temp"]

    current = data[-1]["temp"]
    speed = (data[-1]["temp"] - data[-2]["temp"]) * 2

    if speed > 1:
        return current + 2
    elif speed > 0:
        return current + 1
    else:
        return current

# ======================
# UI
# ======================
st.title("🌡️ METAR监控系统（稳定版）")
st.caption(f"刷新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}")

data = init_today_history()
data, is_new = get_today_data()
data, fixed = auto_fix_data(data)

if not data:
    st.warning("等待数据")
    st.stop()

if is_new:
    st.success("🆕 新数据")
    st.audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg", autoplay=True)

if fixed:
    st.warning("🛠️ 数据已自动修复")

current = data[-1]
max_temp = max(x["temp"] for x in data)

st.subheader("当前")
st.metric("温度", f"{current['temp']}°C")
st.metric("今日最高", f"{max_temp}°C")
st.write(current["time"])

st.subheader("温度曲线")
df = pd.DataFrame(data)
df["time"] = pd.to_datetime(df["time"])
st.line_chart(df.set_index("time")["temp"])

# 数据完整性
st.subheader("数据完整性")
gaps = check_data_integrity(data)

if not gaps:
    st.success("数据完整")
else:
    st.error(f"缺失 {len(gaps)} 处")
    for g in gaps:
        st.write(f"{g[0]} → {g[1]} ({g[2]}分钟)")

# 见顶概率
st.subheader("见顶概率")
prob = peak_probability(data)
st.metric("概率", f"{prob}%")
st.progress(prob/100)

# 模型验证
pred = predict_max_temp(data)
record_today_result(data, pred)

st.subheader("模型表现")
history = load_history()

if history:
    dfh = pd.DataFrame(history)
    st.dataframe(dfh)
    st.metric("平均误差", f"{dfh['error'].mean():.2f}°C")
    st.line_chart(dfh.set_index("date")[["pred", "actual"]])
else:
    st.info("暂无历史记录（需到晚上才记录）")