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
# 模型历史
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
# 主数据源
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
            raise Exception("主API失败")

        metars = res.json()
        new_data = []

        for item in metars:
            temp = item.get("temp") or item.get("temp_c")
            raw = item.get("rawOb") or item.get("raw_text")
            obs_time = item.get("obsTime") or item.get("observation_time")

            if temp is None or obs_time is None:
                continue

            try:
                if isinstance(obs_time, (int, float)):
                    dt = datetime.utcfromtimestamp(obs_time / 1000)
                else:
                    dt = datetime.strptime(obs_time, "%Y-%m-%dT%H:%M:%SZ")
            except:
                continue

            dt = dt + timedelta(hours=8)

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

    # ===== fallback =====
    backup = init_today_history_backup()
    if backup:
        return backup

    return data

# ======================
# 备用数据源（OGIMET）
# ======================
def init_today_history_backup():
    try:
        now = now_local()

        url = f"https://www.ogimet.com/display_metars2.php?lang=en&lugar=ZSPD&tipo=ALL&ord=REV&nil=NO&fmt=txt&ano={now.year}&mes={now.month}&day={now.day}&hora=00&anof={now.year}&mesf={now.month}&dayf={now.day}&horaf=23&minf=59&send=send"

        text = requests.get(url, timeout=10).text
        lines = text.split("\n")

        new_data = []

        for line in lines:
            if "ZSPD" not in line:
                continue

            t = re.search(r'(\d{2})(\d{2})(\d{2})Z', line)
            temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', line)

            if not t or not temp_match:
                continue

            day, hour, minute = t.groups()
            temp = int(temp_match.group(1).replace("M", "-"))

            dt = datetime(now.year, now.month, int(day), int(hour), int(minute)) + timedelta(hours=8)

            if dt.date() != now.date():
                continue

            new_data.append({
                "metar_time": f"{day}{hour}{minute}",
                "time": dt.strftime("%Y-%m-%d %H:%M"),
                "temp": temp,
                "raw": line.strip()
            })

        new_data = sorted(new_data, key=lambda x: x["time"])

        if len(new_data) > 5:
            save_cache(new_data)
            return new_data

    except:
        pass

    return []

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

        if not t or not temp_match:
            return data, False

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
# 数据完整性
# ======================
def check_data_integrity(data):
    gaps = []
    for i in range(1, len(data)):
        t1 = pd.to_datetime(data[i-1]["time"])
        t2 = pd.to_datetime(data[i]["time"])
        diff = (t2 - t1).total_seconds()/60
        if diff > 60:
            gaps.append((data[i-1]["time"], data[i]["time"], int(diff)))
    return gaps

# ======================
# 自动修复
# ======================
def auto_fix_data(data):
    gaps = check_data_integrity(data)
    if not gaps or len(gaps) > 5:
        return data, False

    return init_today_history(), True

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
st.title("🌡️ METAR监控系统（优化版）")
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

# ===== 见顶概率 =====
st.subheader("见顶概率")
prob = peak_probability(data)
st.metric("概率", f"{prob}%")
st.progress(prob/100)

# ===== 信号优化版 =====
st.subheader("🚨 信号提醒（优化版）")

if len(data) < 5:
    st.info("数据不足")
else:
    temps = [x["temp"] for x in data[-5:]]

    speed1 = temps[-1] - temps[-2]
    speed2 = temps[-2] - temps[-3]
    acc = speed1 - speed2

    today_max = max(x["temp"] for x in data)
    position = temps[-1] / today_max if today_max else 0

    prev_prob = peak_probability(data[:-1]) if len(data) >= 6 else 0

    if prob > 70 and prev_prob > 70 and position > 0.9 and acc < 0:
        st.error("🔴 强卖信号")
        st.audio("https://actions.google.com/sounds/v1/alarms/alarm_clock.ogg", autoplay=True)
    elif prob > 60:
        st.warning("🟡 接近顶部")
    else:
        st.success("🟢 上升趋势")

# ===== 模型表现 =====
pred = predict_max_temp(data)
record_today_result(data, pred)

st.subheader("📊 模型表现")
history = load_history()

if history:
    dfh = pd.DataFrame(history)
    st.dataframe(dfh)
    st.metric("平均误差", f"{dfh['error'].mean():.2f}°C")
    st.line_chart(dfh.set_index("date")[["pred", "actual"]])
else:
    st.info("暂无历史记录")

# ===== 数据表 =====
st.subheader("📋 历史数据")
st.dataframe(pd.DataFrame(data), use_container_width=True)

# ===== 最近METAR =====
st.subheader("📡 最近METAR")
for row in reversed(data[-5:]):
    st.text(f"{row['time']} → {row['raw']}")