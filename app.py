import streamlit as st
import requests
import pandas as pd
import json
import re
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

st.set_page_config(page_title="METAR监控系统", layout="wide")
st_autorefresh(interval=30000, key="refresh")

# ======================
# 时间
# ======================
def now_local():
    return datetime.utcnow() + timedelta(hours=8)

def utc_to_local(day, hour, minute):
    now = datetime.utcnow()
    dt = datetime(now.year, now.month, int(day), int(hour), int(minute))
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
# ⭐ 历史数据（双源）
# ======================
def init_today_history():
    # 主API
    try:
        url = "https://aviationweather.gov/api/data/metar"
        params = {"ids": "ZSPD", "format": "json", "hours": 24}
        res = requests.get(url, params=params, timeout=8)
        metars = res.json()

        data = []
        for m in metars:
            temp = m.get("temp") or m.get("temp_c")
            raw = m.get("rawOb") or m.get("raw_text")
            obs = m.get("obsTime") or m.get("observation_time")

            if temp and obs:
                dt = datetime.strptime(obs, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                if dt.date() == now_local().date():
                    data.append({
                        "metar_time": dt.strftime("%d%H%M"),
                        "time": dt.strftime("%Y-%m-%d %H:%M"),
                        "temp": int(temp),
                        "raw": raw
                    })

        if len(data) > 5:
            data = sorted(data, key=lambda x: x["time"])
            save_cache(data)
            return data
    except:
        pass

    # 备用 ogimet
    try:
        now = now_local()
        url = f"https://www.ogimet.com/display_metars2.php?lang=en&lugar=ZSPD&tipo=ALL&ord=REV&nil=NO&fmt=txt&ano={now.year}&mes={now.month}&day={now.day}&hora=00&anof={now.year}&mesf={now.month}&dayf={now.day}&horaf=23&minf=59"

        text = requests.get(url, timeout=8).text
        lines = text.split("\n")

        data = []
        for line in lines:
            if "ZSPD" not in line:
                continue

            t = re.search(r'(\d{2})(\d{2})(\d{2})Z', line)
            temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', line)

            if not t or not temp_match:
                continue

            day, hour, minute = t.groups()
            temp = int(temp_match.group(1).replace("M", "-"))
            dt = utc_to_local(day, hour, minute)

            if dt.date() == now.date():
                data.append({
                    "metar_time": f"{day}{hour}{minute}",
                    "time": dt.strftime("%Y-%m-%d %H:%M"),
                    "temp": temp,
                    "raw": line.strip()
                })

        if len(data) > 5:
            data = sorted(data, key=lambda x: x["time"])
            save_cache(data)
            return data
    except:
        pass

    return load_cache()

# ======================
# 实时更新
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

            if len(data) == 0 or data[-1]["metar_time"] != metar_time:
                is_new = True
                data.append({
                    "metar_time": metar_time,
                    "time": now_local().strftime("%Y-%m-%d %H:%M"),
                    "temp": temp,
                    "raw": metar
                })
                save_cache(data)
    except:
        pass

    return data, is_new

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

    position = temps[-1] / max(temps)

    score = 0
    score += max(0, -acc) * 30
    score += position * 50

    return min(round(score), 100)

# ======================
# 启动
# ======================
data = init_today_history()
data, is_new = get_today_data()

if not data:
    st.error("❌ 无法获取数据（API异常）")
    st.stop()

current = data[-1]
max_temp = max(x["temp"] for x in data)

# ======================
# 标题
# ======================
st.markdown(f"""
<div style='text-align:center'>
<h1>🌡️ METAR监控系统</h1>
<div style='color:gray'>实时气象监控 · 见顶概率分析</div>
<div style='font-size:12px;color:#999'>更新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}</div>
<div style='font-size:12px;color:#aaa'>数据来源：METAR(ZSPD) ｜自动刷新｜Design by Kylin</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# 声音提示
if is_new:
    st.success("🟢 新数据已更新")
    st.audio("https://actions.google.com/sounds/v1/alarms/beep_short.ogg", autoplay=True)

# ======================
# 三栏
# ======================
col1, col2, col3 = st.columns([1,1.2,1])

# 左
with col1:
    prob = peak_probability(data)
    st.subheader("见顶概率")
    st.metric("概率", f"{prob}%")
    st.progress(prob/100)

    st.subheader("📊 概率解释")
    if len(data) >= 2:
        if data[-1]["temp"] < data[-2]["temp"]:
            st.write("🔻 已下降（已见顶）")
        else:
            st.write("📈 上升中")

    st.subheader("🚨 信号提醒")
    if prob >= 90:
        st.error("🔴 强卖")
    elif prob > 60:
        st.warning("🟡 接近顶部")
    else:
        st.success("🟢 上升趋势")

# 中
with col2:
    st.subheader("当前")
    st.metric("温度", f"{current['temp']}°C")
    st.metric("今日最高", f"{max_temp}°C")
    st.write(current["time"])

    st.subheader("温度曲线")
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    st.line_chart(df.set_index("time")["temp"])

    st.info("📌 夜间无数据属正常")

    # 数据完整性
    st.subheader("🧩 数据完整性")
    gaps = []
    for i in range(1, len(data)):
        t1 = pd.to_datetime(data[i-1]["time"])
        t2 = pd.to_datetime(data[i]["time"])
        if (t2 - t1).total_seconds()/60 > 60:
            gaps.append(1)

    if not gaps:
        st.success("数据完整")
    else:
        st.error(f"缺失 {len(gaps)} 处")

# 右
with col3:
    st.subheader("📋 历史数据")
    st.dataframe(pd.DataFrame(data))

    st.subheader("📡 最近METAR")
    for row in reversed(data[-5:]):
        st.code(row["raw"])